"""对话接口：WebSocket 实时对话（流式）+ HTTP 兜底

职责全景：
1. 入口：WS /api/chat/ws（商城客服窗，逐 token 流式）+ POST /api/chat（兜底）
2. 前置：JWT 鉴权（current_user）→ 输入校验（空/超长）→
   LLM 可用性检测 → QA 缓存命中（高频问题秒回，不做任何推理）
3. 上下文构建（_build_messages）：四层记忆注入
   【用户偏好】→【历史对话记忆】→【本次会话前情摘要】→ 最近 3 轮历史
4. 编排执行：LangGraph workflow（confirm_action → supervisor → 子 Agent → 合规）
5. 响应：WS 流式清洗 <think>/<tool_call> 后逐字推送；HTTP 一次性返回
6. 后台记忆管线（_persist_turn）：Redis 历史 + PostgreSQL 落库 +
   滚动摘要 + 偏好提取 + 向量记忆，全部异步不阻塞回复
7. 兜底：LLM 不可用/超时/异常 → 规则话术（FALLBACK_REPLIES）

性能说明：
- _agent_semaphore 限制工作流并发（保护本地 LLM 不被压垮）
- 记忆读写在线程池执行 + 1-2s 超时，超时降级为"仅当前消息"上下文
- QA 缓存键是用户问题原文（语义命中阈值 0.93），
  提案/确认类回复不缓存，防止跨会话串用
"""
import asyncio
import concurrent.futures
import logging
import re
import socket
import threading
import time
import traceback

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger as _loguru
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db
from app.config.settings import settings
from app.core.db import AsyncSessionLocal
from app.core.redis_client import cache_answer, get_cached_answer
from app.core.ws_manager import manager as ws_manager
from app.dialogue.intent import IntentClassifier
from app.dialogue.memory import SessionMemory
from app.models.schemas import ChatRequest, ChatResponse
from app.models.tables import Conversation

logger = logging.getLogger(__name__)
perf_logger = _loguru.bind(name="perf")
router = APIRouter()
memory = SessionMemory()
intent_classifier = IntentClassifier()

# Agent 工作流并发上限（保护本地/远端 LLM 不被压垮）
_agent_semaphore = asyncio.Semaphore(settings.agent_max_concurrency)

# 后台线程池：处理 Redis/PostgreSQL/记忆任务，不阻塞响应返回
_memory_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="mem")

# 记忆任务中的 LLM 调用（摘要/偏好提取）限流，防止挤占在线推理
_memory_llm_sem = threading.BoundedSemaphore(2)

# 传给工作流的历史消息条数上限（控制上下文长度，降低LLM推理延迟）
_MAX_CONTEXT_TURNS = 3
# 用户输入最大字符数
_MAX_INPUT_LENGTH = 500

# ── 输入安全校验 ──

def _validate_input(message: str) -> str | None:
    """校验用户输入，返回错误信息（None 表示通过）

    规则：空消息拦截；单条消息 ≤500 字（防超长提示词拖慢 CPU 推理）
    """
    if not message or not message.strip():
        return "请输入您的问题。"
    if len(message) > _MAX_INPUT_LENGTH:
        return f"输入内容过长，请控制在 {_MAX_INPUT_LENGTH} 字以内。"
    return None


# ── LLM 可用性预检 ──

def _llm_reachable() -> bool:
    """LLM 可用性预检

    本地模式：TCP 探测 llama.cpp 端口（0.5s 超时，快速失败）；
    云端模式：仅检查 API Key 是否配置。
    """
    host = settings.local_llm_host if settings.llm_provider == "local" else None
    port = settings.local_llm_port if settings.llm_provider == "local" else None
    if not host:
        return bool(settings.llm_api_key)
    try:
        s = socket.create_connection((host, port), timeout=0.5)
        s.close()
        return True
    except (TimeoutError, ConnectionRefusedError, OSError):
        return False


def _chat_rate_ok(user_id: str) -> bool:
    """聊天接口单用户限流：Redis 固定窗口（1 分钟）

    user_id 为空（匿名/未识别）时放行，由 IP 级限流兜底。
    """
    if not user_id:
        return True
    try:
        from app.core.redis_client import get_redis
        r = get_redis()
        key = f"csagent:chat_rl:{user_id}"
        n = r.incr(key)
        if n == 1:
            r.expire(key, 60)
        if n > settings.chat_rate_limit_per_minute:
            from app.core.metrics import CHAT_RATE_BLOCKED
            CHAT_RATE_BLOCKED.inc()
            return False
        return True
    except Exception:
        return True


def _build_messages(session_id: str, user_id: str, current_message: str) -> list:
    """构建完整消息列表：四层记忆 + 最近几轮 + 当前消息

    注入顺序（先系统级记忆，再对话历史，最后当前问题）：
    1. 【用户偏好】：跨会话个性化（来自 preferences.py，30 天 TTL）
    2. 【历史对话记忆】：该用户此前相似的问答片段（vector_memory 语义召回）
    3. 【本次会话前情摘要】：早期轮次压缩的摘要（memory.py 滚动摘要）
    4. 最近 3 轮历史：取自 Redis；Redis 为空时从 PostgreSQL 恢复并回填

    注：该函数在线程池执行（最多 2s），超时降级为只带当前消息，
    保证慢记忆不拖垮对话首响。
    """
    try:
        history = memory.load(session_id)
        if not history:
            # Redis 过期时从 PostgreSQL 恢复（跨天记忆）
            from app.dialogue.persistence import load_history
            history = load_history(session_id)
            for h in history:
                memory.append(session_id, h["role"], h["content"])
    except Exception:
        history = []

    messages: list = []

            # 1) 用户偏好（跨会话长期记忆）
    try:
        from app.dialogue.preferences import build_preference_prompt
        pref = build_preference_prompt(user_id)
        if pref:
            messages.append(SystemMessage(content=f"【用户偏好】{pref}，回复时请贴合其偏好。"))
    except Exception:
        pass

            # 2) 向量记忆（跨会话相关历史问答）
    try:
        from app.dialogue.vector_memory import recall
        memories = recall(user_id, current_message)
        if memories:
            block = "\n".join(f"- {m}" for m in memories)
            messages.append(SystemMessage(content=f"【历史对话记忆】用户此前问过类似问题：\n{block}"))
    except Exception:
        pass

            # 3) 滚动摘要（本会话早期轮次）
    try:
        summary = memory.get_summary(session_id)
        if summary:
            messages.append(SystemMessage(content=f"【本次会话前情摘要】{summary}"))
    except Exception:
        pass

    # 4) 最近 3 轮历史（_MAX_CONTEXT_TURNS*2 = 6 条消息）
    for h in history[-_MAX_CONTEXT_TURNS * 2:]:
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        elif h["role"] == "assistant":
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=current_message))
    return messages


# 滚动摘要：保留最近6条消息，更早的折入摘要
_SUMMARY_WINDOW = 6


def _maybe_update_summary(session_id: str) -> None:
    """把超出窗口的旧消息折入滚动摘要（后台调用）

    窗口 _SUMMARY_WINDOW=6：仅保留最近 6 条作上下文，
    更早的消息按"已折叠计数"增量折叠（每条只折叠一次，幂等）。
    摘要由 LLM 生成（≤150 字），合并到旧摘要，后续注入前情摘要。
    """
    history = memory.load(session_id)
    if len(history) <= _SUMMARY_WINDOW + 2:
        return
    foldable = history[:-_SUMMARY_WINDOW]
    folded = memory.get_folded(session_id)
    new_parts = foldable[folded:]
    if not new_parts:
        return
    old = memory.get_summary(session_id)
    text = "\n".join(
        f"{'用户' if h['role'] == 'user' else '客服'}：{h['content'][:150]}"
        for h in new_parts
    )
    from app.core.llm import get_llm
    llm = get_llm(max_tokens=200, streaming=False)
    resp = llm.invoke([
        SystemMessage(content="你是对话摘要助手，把对话压缩成简洁中文摘要，保留关键事实、用户偏好与未完成事项，不超过150字。"),
        HumanMessage(content=f"已有摘要：{old or '无'}\n\n需折叠的对话：\n{text}"),
    ])
    new_summary = (resp.content or "").strip()
    if new_summary:
        memory.set_summary(session_id, new_summary)
        memory.set_folded(session_id, len(foldable))


def _persist_turn(session_id: str, user_id: str, user_msg: str, assistant_msg: str) -> None:
    """后台记忆管线：Redis 历史 + PostgreSQL 落库 + 摘要 + 偏好 + 向量记忆

    顺序：
    1. memory.append 两次（用户/客服消息写 Redis 会话）
    2. persistence.save_turn（PostgreSQL 全量落库）
    3. _maybe_update_summary（折叠旧轮次）
    4. update_preferences（每 6 条触发一次 LLM 抽取偏好）
    5. vector_memory.remember（历史问答向量化）

    每个步骤都 try/except 隔离：任一失败都不影响其他记忆与主对话。
    """
    from app.core.metrics import MEMORY_TASKS
    MEMORY_TASKS.labels(result="submit").inc()
    if not session_id or not user_msg:
        return
    try:
        memory.append(session_id, "user", user_msg)
        memory.append(session_id, "assistant", assistant_msg)
    except Exception:
        pass
    try:
        from app.dialogue.persistence import save_turn
        save_turn(session_id, user_id, user_msg, assistant_msg)
    except Exception:
        pass
    try:
        with _memory_llm_sem:
            _maybe_update_summary(session_id)
    except Exception:
        pass
    try:
        history = memory.load(session_id)
        if len(history) >= 6 and len(history) % 6 == 0:
            with _memory_llm_sem:
                from app.dialogue.preferences import update_preferences
                update_preferences(user_id, session_id)
    except Exception:
        pass
    try:
        from app.dialogue.vector_memory import remember
        remember(user_id, session_id, user_msg, assistant_msg)
    except Exception:
        pass
    MEMORY_TASKS.labels(result="done").inc()


def _cacheable(message: str, answer: str, intent: str | None = None, need_human: bool = False) -> bool:
    """判定是否可写入 QA 缓存

    不缓存的情况：
    - 转人工/投诉/包含"人工"（内容与上下文相关，不宜复用）
    - 纯确认类短消息（"确认/好的"——避免跨会话串用提案结果）
    - 提案类回复（含"提案/请回复确认"——同因，防止待办动作丢失）
    - 答案过短（<5 字，无复用价值）
    """
    if need_human or intent in ("complaint", "human_service"):
        return False
    if any(k in message for k in ("人工", "转人工", "投诉", "真人")):
        return False
    # 通用确认/短消息不缓存（避免跨会话串用，如“确认”命中别的会话的提案结果）
    if message.strip() in {"确认", "好的", "可以", "不用了", "取消", "继续", "同意", "算了", "没问题"}:
        return False
    if len(message.strip()) <= 2:
        return False
    # 提案类回复不缓存（含“提案/请回复确认”），避免跨会话串用导致待确认动作丢失
    if "提案" in answer or "请回复" in answer or "回复“确认”" in answer:
        return False
    return bool(answer and len(answer) >= 5)


async def _run_agent(session_id: str, user_id: str, message: str) -> dict:
    """Supervisor 编排多 Agent 工作流：意图路由 → 专业 Agent → 合规审查 → 回复

    执行顺序：
    1. QA 缓存命中 → 直接秒回（不做任何编排）
    2. LLM 不可用 → 规则兜底（FALLBACK_REPLIES）
    3. 构建上下文（线程池，2s 超时降级）
    4. 信号量限流 + workflow.ainvoke（90s 超时）
    5. 后台记忆管线 + QA 缓存写入
    """
    t_start = time.perf_counter()

    # QA 缓存命中：高频重复问题秒回，跳过完整工作流
    cached = get_cached_answer(message)
    if cached is not None:
        perf_logger.info(f"[_run_agent] QA cache HIT: {(time.perf_counter() - t_start) * 1000:.0f}ms")
        return {"answer": cached, "intent": "", "need_human": False, "cached": True}

    if not _llm_reachable():
        return await _fallback_reply(message)

    try:
        from app.agents.graphs.workflow import get_workflow

        t0 = time.perf_counter()
        workflow = get_workflow()
        perf_logger.info(f"[_run_agent] get_workflow: {(time.perf_counter() - t0) * 1000:.0f}ms")

        t0 = time.perf_counter()
        try:
            loop = asyncio.get_running_loop()
            messages = await asyncio.wait_for(
                loop.run_in_executor(_memory_executor, _build_messages, session_id, user_id, message),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            perf_logger.warning("[_run_agent] build_messages TIMEOUT, using minimal context")
            messages = [HumanMessage(content=message)]
        perf_logger.info(f"[_run_agent] build_messages({len(messages)}条): {(time.perf_counter() - t0) * 1000:.0f}ms")

        t0 = time.perf_counter()
        async with _agent_semaphore:
            result = await asyncio.wait_for(
                workflow.ainvoke({"messages": messages, "session_id": session_id, "user_id": user_id, "slots": {}}),
                timeout=90.0,
            )
        t_workflow = time.perf_counter() - t0
        perf_logger.info(f"[_run_agent] workflow.ainvoke: {t_workflow * 1000:.0f}ms, intent={result.get('intent', '?')}")

        answer = result["messages"][-1].content if result.get("messages") else "抱歉，暂时无法回复。"

        # 后台写入记忆管线（Redis + PostgreSQL + 摘要 + 偏好 + 向量）
        _memory_executor.submit(_persist_turn, session_id, user_id, message, answer)
        # 后台写入 QA 缓存（人工/投诉类除外）
        if _cacheable(message, answer, result.get("intent"), result.get("need_human")):
            _memory_executor.submit(cache_answer, message, answer)

        perf_logger.info(f"[_run_agent] TOTAL: {(time.perf_counter() - t_start) * 1000:.0f}ms, answer_len={len(answer)}")
        return {
            "answer": answer,
            "intent": result.get("intent"),
            "need_human": result.get("need_human", False),
        }
    except asyncio.TimeoutError:
        perf_logger.warning(f"[_run_agent] TIMEOUT after {(time.perf_counter() - t_start) * 1000:.0f}ms")
        return {"answer": "抱歉，当前回复较慢，请稍后再试。", "intent": "", "need_human": False}
    except Exception:
        perf_logger.error(f"[_run_agent] ERROR after {(time.perf_counter() - t_start) * 1000:.0f}ms: {traceback.format_exc()}")
        return await _fallback_reply(message)


# 规则兜底回复（LLM不可用时使用）
FALLBACK_REPLIES: dict[str, str] = {
    "query_order": (
        "您好！要查询订单状态，请提供您的订单编号，我将为您查询。\n\n"
        "您也可以在「我的订单」页面自助查看所有订单的实时状态。"
    ),
    "track_logistics": (
        "您好！物流信息查询需要您提供订单号。\n\n"
        "通常情况下，我们会在下单后 24 小时内发货，国内快递约 2-5 天送达。"
    ),
    "return_goods": (
        "茗韵茶庄支持 7 天无理由退换货（未拆封、不影响二次销售）。\n\n"
        "如需退货，请在「我的订单」中点击对应订单的「申请售后」按钮，客服将在 24 小时内审核。"
    ),
    "exchange_goods": (
        "换货流程：\n"
        "1. 在「我的订单」中申请换货\n"
        "2. 将商品寄回（运费由我们承担，如属我们的问题）\n"
        "3. 仓库收到后 1-2 个工作日内为您发出新商品"
    ),
    "product_consult": (
        "茗韵茶庄专注品质好茶，我们的茶叶均来自核心原产地，坚持传统工艺制作。\n\n"
        "茶叶保存小贴士：密封、避光、防潮、防异味，绿茶建议冷藏保存哦！\n\n"
        "如需了解具体茶品，可以告诉我您喜欢什么类型的茶（绿茶/红茶/乌龙茶/普洱茶/白茶/花茶），我为您推荐！"
    ),
    "price_inquiry": (
        "我们的茶叶价格因品种、等级、包装而异，从几十元的口粮茶到上千元的礼盒装都有。\n\n"
        "您可以在商品页查看实时价格，也可以告诉我您的预算和偏好，我为您精准推荐。"
    ),
    "promotion_consult": (
        "目前我们有以下优惠活动：\n"
        "• 新用户首单 9 折优惠\n"
        "• 满 200 元包邮\n"
        "• 会员积分可抵扣现金\n\n"
        "更多活动请关注商城首页公告！"
    ),
    "payment_issue": (
        "如果遇到支付问题，建议您：\n"
        "1. 检查网络连接后重试\n"
        "2. 更换支付方式（微信/支付宝）\n"
        "3. 确认银行卡余额充足\n\n"
        "如问题持续，可联系人工客服处理。"
    ),
    "app_usage": (
        "您在使用中遇到了什么问题？\n"
        "• 如页面无法加载，请尝试刷新或清除浏览器缓存\n"
        "• 如显示异常，建议使用 Chrome 浏览器访问\n\n"
        "输入「转人工」可联系人工客服获得一对一帮助。"
    ),
    "complaint": (
        "非常抱歉给您带来不好的体验！我已记录您的反馈，现在为您转接人工客服优先处理。\n\n"
        "人工客服工作时间 9:00-22:00，请稍候。"
    ),
    "human_service": (
        "正在为您转接人工客服，请稍候...\n\n"
        "人工客服工作时间 9:00-22:00。非工作时间留言将在次日优先处理。"
    ),
    "chitchat": (
        "感谢您的留言！茗韵茶庄，一叶知春秋，一盏品人生。\n\n"
        "有什么关于茶叶或订单的问题可以随时问我哦~"
    ),
}


async def _fallback_reply(message: str) -> dict:
    """LLM 不可用时的规则兜底回复

    用途：保证 LLM 故障/超时/编排异常时用户依然得到可用答案。
    流程：意图分类（命中则用对应模板）→ 返回 12 类固定话术之一。
    """
    t0 = time.perf_counter()
    result = intent_classifier.classify(message)
    t_cls = time.perf_counter() - t0
    intent = result.name
    answer = FALLBACK_REPLIES.get(intent, FALLBACK_REPLIES["product_consult"])
    need_human = intent in ("complaint", "human_service")
    perf_logger.info(f"[_fallback_reply] classify={t_cls * 1000:.0f}ms, intent={intent}({result.confidence:.2f}), human={need_human}")
    return {"answer": answer, "intent": intent, "need_human": need_human}


# ── 聊天历史接口 ──

@router.get("/history")
async def get_chat_history(
    session_id: str,
    user: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取指定 session 的对话历史

    优先 Redis（快）；为空时回退 PostgreSQL（跨天恢复）。
    """
    conv = (await db.execute(
        select(Conversation).where(Conversation.session_id == session_id)
    )).scalar_one_or_none()
    if conv and conv.user_id and conv.user_id != str(user.get("sub", "")):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    history = await asyncio.to_thread(memory.load, session_id)
    if not history:
        try:
            from app.dialogue.persistence import load_history
            history = await asyncio.to_thread(load_history, session_id)
        except Exception:
            pass
    return {
        "code": 0,
        "data": {
            "session_id": session_id,
            "messages": history,
        },
    }


# ── 满意度评价接口 ──

@router.post("/csat")
async def submit_csat(
    session_id: str,
    rating: int,
    comment: str = "",
    user: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """提交对话满意度评价（1-5分）"""
    if not 1 <= rating <= 5:
        return {"code": 400, "detail": "评分须在 1-5 之间"}

    from app.models.tables import CsatScore

    try:
        score = CsatScore(
            session_id=session_id,
            user_id=str(user.get("sub", "")),
            rating=rating,
            comment=comment[:500] if comment else None,
            agent_type="ai",
        )
        db.add(score)
        await db.commit()
        return {"code": 0, "data": {"session_id": session_id, "rating": rating}}
    except Exception as e:
        return {"code": 500, "detail": str(e)}


async def _safe_ws_send(ws: WebSocket, data: dict) -> bool:
    """安全发送 WebSocket 消息，连接关闭时静默返回 False"""
    try:
        await ws.send_json(data)
        return True
    except Exception:
        return False


def _strip_think_buf(text: str) -> str:
    """清除流式缓冲中的 <think> 标签（可能在非完整标签状态）"""
    if "<think>" in text or "<think" in text:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """HTTP对话接口（WebSocket不可用时的兜底通道）"""
    err = _validate_input(req.message)
    if err:
        return ChatResponse(session_id=req.session_id, answer=err, intent="", need_human=False)
    user_id = str(user.get("sub", ""))
    conv = (await db.execute(
        select(Conversation).where(Conversation.session_id == req.session_id)
    )).scalar_one_or_none()
    if conv and conv.user_id and conv.user_id != user_id:
        return ChatResponse(session_id=req.session_id, answer="无权访问该会话", intent="", need_human=True)
    if not _chat_rate_ok(user_id):
        return ChatResponse(session_id=req.session_id, answer="消息发送过于频繁，请稍后再试。", intent="", need_human=False)
    result = await _run_agent(req.session_id, user_id, req.message)
    return ChatResponse(session_id=req.session_id, **result)


@router.websocket("/ws")
async def chat_ws(ws: WebSocket, token: str = "") -> None:
    """WebSocket实时对话：逐token流式推送

    认证：通过 query param 传入 JWT token（ws://host/api/chat/ws?token=xxx）。
    客户端消息格式：{"session_id": "...", "user_id": "...", "message": "..."}
    服务端推送格式：{"type": "chunk"|"done"|"error", "content"?: "token", ...}
    前端收到 chunk 后逐字追加到当前消息气泡，收到 done 表示本轮回答结束。
    """
    # WebSocket 鉴权：生产环境强制要求 token，开发环境提供 token 时也强制校验
    token_user: dict | None = None
    if token:
        try:
            import jwt as jwt_lib
            token_user = jwt_lib.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            if token_user.get("type") != "access":
                await ws.close(code=4001, reason="令牌类型错误")
                return
        except Exception:
            await ws.close(code=4001, reason="认证失败")
            return
    if settings.app_env == "production" and not token:
        await ws.close(code=4001, reason="需要认证")
        return

    await ws.accept()
    current_session: str | None = None
    try:
        while True:
            data = await ws.receive_json()
            try:
                session_id = data["session_id"]
                current_session = session_id
                user_id = str(token_user.get("sub", "")) if token_user else str(data.get("user_id", ""))
                message = data["message"]

                # 会话归属校验：已绑定用户的会话禁止跨用户读写
                try:
                    async with AsyncSessionLocal() as db:
                        conv = (await db.execute(
                            select(Conversation).where(Conversation.session_id == session_id)
                        )).scalar_one_or_none()
                        if conv and conv.user_id and conv.user_id != user_id:
                            await _safe_ws_send(ws, {"type": "error", "detail": "无权访问该会话"})
                            continue
                except Exception:
                    pass

                # 单用户聊天限流（用户级配额）
                if not _chat_rate_ok(user_id):
                    await _safe_ws_send(ws, {"type": "error", "detail": "消息发送过于频繁，请稍后再试。"})
                    continue

                # 注册用户 WebSocket（用于人工客服消息推送）
                await ws_manager.connect_user(session_id, ws)

                # 转发用户消息给监听该 session 的管理员（实时人工接管链路）
                await ws_manager.send_to_admins(session_id, {"type": "user_message", "content": message})

                # 输入安全校验
                err = _validate_input(message)
                if err:
                    await _safe_ws_send(ws, {"type": "error", "detail": err})
                    continue

                # LLM不可用时走规则兜底
                if not _llm_reachable():
                    result = await _fallback_reply(message)
                    await _safe_ws_send(ws, {"type": "chunk", "content": result["answer"]})
                    await _safe_ws_send(ws, {"type": "done", "intent": result["intent"], "need_human": result["need_human"]})
                    continue

                # QA 缓存命中：重复/相似问题秒回，跳过完整工作流
                cached = get_cached_answer(message)
                if cached is not None:
                    await _safe_ws_send(ws, {"type": "chunk", "content": cached})
                    await _safe_ws_send(ws, {"type": "done", "cached": True})
                    continue

                from app.agents.graphs.workflow import get_workflow

                workflow = get_workflow()
                messages = _build_messages(session_id, user_id, message)
                input_state = {"messages": messages, "session_id": session_id, "user_id": user_id, "slots": {}}

                try:
                    full_answer = ""
                    root_run_id: str | None = None
                    streamed = False       # 是否已逐token推送过
                    tool_call_seen = False  # 流式中是否检测到 <tool_call>（需丢弃本轮输出，用最终干净回复替代）
                    _stream_buf = ""       # 流式缓冲：用于过滤 <think> 块
                    _in_think = False      # 当前是否在 <think> 标签内
                    _sent_len = 0          # 已推送给前端的干净文本长度

                    # astream_events v2：逐token流式推送 + 捕获最终状态
                    async for event in workflow.astream_events(input_state, version="v2"):
                        if root_run_id is None:
                            root_run_id = event.get("run_id", "")

                        kind = event["event"]
                        if kind == "on_chat_model_stream":
                            chunk = event["data"]["chunk"]
                            if hasattr(chunk, "content") and chunk.content:
                                token = chunk.content
                                if isinstance(token, str) and token:
                                    full_answer += token
                                    _stream_buf += token
                                    if _in_think:
                                        # 正在 think 块内：等待 </think> 结束
                                        if "</think>" in _stream_buf:
                                            _in_think = False
                                            _stream_buf = _stream_buf[_stream_buf.index("</think>") + len("</think>"):]
                                            _sent_len = 0
                                        else:
                                            continue
                                    # 检测 think 标签开头（含未完成前缀 <th...），命中则整块丢弃
                                    if "<think" in _stream_buf or _stream_buf[_sent_len:].startswith("<"):
                                        _in_think = True
                                        continue
                                    # 发送缓冲中未推送的干净内容
                                    visible = _stream_buf[_sent_len:]
                                    if visible and not tool_call_seen:
                                        streamed = True
                                        await _safe_ws_send(ws, {"type": "chunk", "content": visible})
                                    _sent_len = len(_stream_buf)
                        # 捕获根图完成的最终输出（非LLM路径如handoff/compliance阻断）
                        elif kind == "on_chain_end" and event.get("run_id") == root_run_id:
                            output = event["data"].get("output", {})
                            if not streamed or tool_call_seen:
                                msgs = output.get("messages", [])
                                if msgs:
                                    final_msg = msgs[-1]
                                    final_content = final_msg.content if hasattr(final_msg, "content") else str(final_msg)
                                    if tool_call_seen:
                                        # 用干净最终回复覆盖被 tool_call 污染的流式输出
                                        await _safe_ws_send(ws, {"type": "chunk", "content": final_content})
                                    full_answer = final_content
                                    streamed = True

                    # 未流式过的路径（handoff/compliance/规则兜底/think未闭合等）：一次性推送完整回复
                    if not streamed and full_answer:
                        import re
                        clean_all = re.sub(r"<think>.*?</think>", "", full_answer, flags=re.DOTALL).strip()
                        await _safe_ws_send(ws, {"type": "chunk", "content": clean_all or full_answer})

                    if full_answer:
                        # 清洗可能残留的 tool_call / think 标记再存入记忆与缓存
                        import re
                        clean = re.sub(r"<tool_call>\s*\{.*?\}\s*</tool_call>", "", full_answer, flags=re.DOTALL).strip()
                        clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()
                        _memory_executor.submit(_persist_turn, session_id, user_id, message, clean or full_answer)
                        # 后台写入 QA 缓存（人工/投诉类除外）
                        if _cacheable(message, clean or full_answer):
                            _memory_executor.submit(cache_answer, message, clean or full_answer)
                    # tool_call_seen 时告知前端用 clean 内容替换流式气泡
                    done_payload: dict = {"type": "done"}
                    if tool_call_seen and full_answer:
                        done_payload["replace"] = clean or full_answer
                    await _safe_ws_send(ws, done_payload)
                    # 转发 AI 回复给监听该 session 的管理员
                    await ws_manager.send_to_admins(session_id, {"type": "ai_message", "content": clean or full_answer})

                except asyncio.TimeoutError:
                    await _safe_ws_send(ws, {"type": "error", "detail": "回复超时，请稍后再试"})
                except Exception:
                    logger.error("Stream failed, fallback to ainvoke: %s", traceback.format_exc())
                    # 流式失败降级为一次性返回
                    result = await _run_agent(session_id, user_id, message)
                    await _safe_ws_send(ws, {"type": "chunk", "content": result["answer"]})
                    await _safe_ws_send(ws, {"type": "done", "intent": result["intent"], "need_human": result["need_human"]})

            except Exception as exc:
                await _safe_ws_send(ws, {"type": "error", "detail": str(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        if current_session:
            ws_manager.disconnect_user(current_session)
