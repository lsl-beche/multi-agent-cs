"""客服对话流水线：记忆构建、Agent 编排、缓存与持久化"""
import asyncio
import concurrent.futures
import logging
import re
import socket
import threading
import time
import traceback

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger as _loguru

from app.config.settings import settings
from app.core.redis_client import cache_answer, get_cached_answer
from app.dialogue.intent import IntentClassifier
from app.dialogue.memory import SessionMemory

logger = logging.getLogger(__name__)
perf_logger = _loguru.bind(name="perf")
memory = SessionMemory()
intent_classifier = IntentClassifier()

_agent_semaphore = asyncio.Semaphore(settings.agent_max_concurrency)
_memory_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="mem")
_memory_llm_sem = threading.BoundedSemaphore(2)

_MAX_CONTEXT_TURNS = 3
_MAX_INPUT_LENGTH = 500
_SUMMARY_WINDOW = 6

FALLBACK_REPLIES: dict[str, str] = {
    "query_order": "您好！要查询订单状态，请提供您的订单编号，我将为您查询。\n\n您也可以在「我的订单」页面自助查看所有订单的实时状态。",
    "track_logistics": "您好！物流信息查询需要您提供订单号。\n\n通常情况下，我们会在下单后 24 小时内发货，国内快递约 2-5 天送达。",
    "return_goods": "茗韵茶庄支持 7 天无理由退换货（未拆封、不影响二次销售）。\n\n如需退货，请在「我的订单」中点击对应订单的「申请售后」按钮。",
    "exchange_goods": "换货流程：\n1. 在「我的订单」中申请换货\n2. 将商品寄回\n3. 仓库收到后 1-2 个工作日内发出新商品",
    "product_consult": "茗韵茶庄专注品质好茶，我们的茶叶均来自核心原产地。\n\n茶叶保存小贴士：密封、避光、防潮、防异味。",
    "price_inquiry": "我们的茶叶价格因品种、等级、包装而异，您可以在商品页查看实时价格。",
    "promotion_consult": "目前有以下优惠活动：\n• 新用户首单 9 折优惠\n• 满 200 元包邮\n• 会员积分可抵扣现金",
    "payment_issue": "遇到支付问题时，请先检查网络后重试，必要时更换支付方式。",
    "app_usage": "如页面无法加载，请刷新或清除缓存；也可以输入「转人工」联系客服。",
    "complaint": "非常抱歉给您带来不好的体验！我已记录您的反馈，正在为您转接人工客服优先处理。",
    "human_service": "正在为您转接人工客服，请稍候。\n\n人工客服工作时间 9:00-22:00。",
    "chitchat": "感谢您的留言！茗韵茶庄，一叶知春秋，一盏品人生。",
}


def validate_input(message: str) -> str | None:
    if not message or not message.strip():
        return "请输入您的问题。"
    if len(message) > _MAX_INPUT_LENGTH:
        return f"输入内容过长，请控制在 {_MAX_INPUT_LENGTH} 字以内。"
    return None


def llm_reachable() -> bool:
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


def chat_rate_ok(user_id: str) -> bool:
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


def build_messages(session_id: str, user_id: str, current_message: str) -> list:
    try:
        history = memory.load(session_id)
        if not history:
            from app.dialogue.persistence import load_history
            history = load_history(session_id)
            for h in history:
                memory.append(session_id, h["role"], h["content"])
    except Exception:
        history = []
    messages: list = []
    try:
        from app.dialogue.preferences import build_preference_prompt
        pref = build_preference_prompt(user_id)
        if pref:
            messages.append(SystemMessage(content=f"【用户偏好】{pref}，回复时请贴合其偏好。"))
    except Exception:
        pass
    try:
        from app.dialogue.vector_memory import recall
        memories = recall(user_id, current_message)
        if memories:
            messages.append(SystemMessage(content=f"【历史对话记忆】{chr(10).join(f'- {m}' for m in memories)}"))
    except Exception:
        pass
    try:
        summary = memory.get_summary(session_id)
        if summary:
            messages.append(SystemMessage(content=f"【本次会话前情摘要】{summary}"))
    except Exception:
        pass
    for h in history[-_MAX_CONTEXT_TURNS * 2:]:
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        elif h["role"] == "assistant":
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=current_message))
    return messages


def maybe_update_summary(session_id: str) -> None:
    history = memory.load(session_id)
    if len(history) <= _SUMMARY_WINDOW + 2:
        return
    foldable = history[:-_SUMMARY_WINDOW]
    folded = memory.get_folded(session_id)
    new_parts = foldable[folded:]
    if not new_parts:
        return
    old = memory.get_summary(session_id)
    text = "\n".join(f"{'用户' if h['role'] == 'user' else '客服'}：{h['content'][:150]}" for h in new_parts)
    try:
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
    except Exception:
        pass


def persist_turn(session_id: str, user_id: str, user_msg: str, assistant_msg: str) -> None:
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
            maybe_update_summary(session_id)
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


def cacheable(message: str, answer: str, intent: str | None = None, need_human: bool = False) -> bool:
    if need_human or intent in ("complaint", "human_service"):
        return False
    if any(k in message for k in ("人工", "转人工", "投诉", "真人")):
        return False
    if message.strip() in {"确认", "好的", "可以", "不用了", "取消", "继续", "同意", "算了", "没问题"}:
        return False
    return not (len(message.strip()) <= 2 or len(answer) < 5)


async def fallback_reply(message: str) -> dict:
    t0 = time.perf_counter()
    result = intent_classifier.classify(message)
    intent = result.name
    answer = FALLBACK_REPLIES.get(intent, FALLBACK_REPLIES["product_consult"])
    need_human = intent in ("complaint", "human_service")
    perf_logger.info(f"[_fallback_reply] classify={(time.perf_counter() - t0) * 1000:.0f}ms intent={intent}")
    return {"answer": answer, "intent": intent, "need_human": need_human}


async def run_agent(session_id: str, user_id: str, message: str) -> dict:
    t_start = time.perf_counter()
    cached = get_cached_answer(message)
    if cached is not None:
        return {"answer": cached, "intent": "", "need_human": False, "cached": True}
    if not llm_reachable():
        return await fallback_reply(message)
    try:
        from app.agents.graphs.workflow import get_workflow
        workflow = get_workflow()
        loop = asyncio.get_running_loop()
        try:
            messages = await asyncio.wait_for(
                loop.run_in_executor(_memory_executor, build_messages, session_id, user_id, message),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            messages = [HumanMessage(content=message)]
        async with _agent_semaphore:
            result = await asyncio.wait_for(
                workflow.ainvoke({"messages": messages, "session_id": session_id, "user_id": user_id, "slots": {}}),
                timeout=90.0,
            )
        answer = result["messages"][-1].content if result.get("messages") else "抱歉，暂时无法回复。"
        _memory_executor.submit(persist_turn, session_id, user_id, message, answer)
        if cacheable(message, answer, result.get("intent"), result.get("need_human")):
            _memory_executor.submit(cache_answer, message, answer)
        return {"answer": answer, "intent": result.get("intent"), "need_human": result.get("need_human", False)}
    except asyncio.TimeoutError:
        return {"answer": "抱歉，当前回复较慢，请稍后再试。", "intent": "", "need_human": False}
    except Exception:
        perf_logger.error(f"[_run_agent] ERROR after {(time.perf_counter() - t_start) * 1000:.0f}ms: {traceback.format_exc()}")
        return await fallback_reply(message)


def _clean_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


async def stream_agent(session_id: str, user_id: str, message: str):
    """逐 token 流式执行 Agent，产出 (kind, content) 事件。

    kind: "chunk" 表示文本增量；"done" 表示最终完整回复。
    """
    from app.agents.graphs.workflow import get_workflow

    messages = await asyncio.get_running_loop().run_in_executor(
        _memory_executor, build_messages, session_id, user_id, message
    )
    workflow = get_workflow()
    root_run_id: str | None = None
    full_answer = ""
    stream_buf = ""
    sent_len = 0
    in_think = False
    tool_call_seen = False
    final_content = ""

    async for event in workflow.astream_events(
        {"messages": messages, "session_id": session_id, "user_id": user_id, "slots": {}},
        version="v2",
    ):
        if root_run_id is None:
            root_run_id = event.get("run_id", "")
        kind = event["event"]

        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if not hasattr(chunk, "content") or not chunk.content:
                continue
            token = chunk.content
            if not isinstance(token, str):
                continue
            full_answer += token
            stream_buf += token

            if in_think:
                if "</think>" in stream_buf:
                    in_think = False
                    stream_buf = _clean_think(stream_buf)
                    sent_len = len(stream_buf)
                    if stream_buf.strip() and not tool_call_seen:
                        yield ("chunk", stream_buf)
                continue
            if "<think" in stream_buf:
                in_think = True
                continue
            visible = stream_buf[sent_len:]
            if visible and not tool_call_seen:
                yield ("chunk", visible)
                sent_len = len(stream_buf)

        elif kind == "on_chain_end" and event.get("run_id") == root_run_id:
            output = event["data"].get("output", {})
            msgs = output.get("messages", [])
            if msgs:
                final = msgs[-1]
                final_content = getattr(final, "content", "") or ""

    final_content = _clean_think(final_content or full_answer)
    if not final_content and full_answer:
        final_content = _clean_think(full_answer)
    if final_content and not tool_call_seen and stream_buf != final_content:
        # 兜底：某些事件路径没有完整流式输出时一次性推送
        yield ("chunk", final_content)
    yield ("done", final_content)
