"""写操作确认闭环：待确认动作的 Redis 存储

为何需要闭环：取消订单/退款/改地址都是"有副作用"的写操作，
不能让模型一次对话就执行——必须显式让用户确认（安全设计）。

完整链路：
1. Agent 的规则分支调用 propose_* 工具 → set_pending 写入待办
   （key=csagent:pending_action:<session_id>，TTL 10 分钟）
2. 用户回复"确认/好的/可以" → workflow.confirm_action 节点 get_pending
3. 执行对应 execute_* 工具 → clear_pending 清除 → 用户看到执行结果
4. 用户回复"不用了/算了" → 直接 clear_pending（放弃操作）

边界处理：
- 待办按 session_id 隔离，多会话互不干扰
- TTL 10 分钟自动过期，防止"陈年提案"被误执行
- Redis 异常时静默降级（get 返回 None，提案丢失但不阻断对话）
"""
import json
import logging
import time

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

_PREFIX = "csagent:pending_action:"
_TTL = 600  # 10分钟


def set_pending(session_id: str, action: str, params: dict) -> bool:
    """写入待确认动作，返回是否成功"""
    if not session_id:
        return False
    try:
        payload = {
            "action": action,
            "params": params,
            "created_at": int(time.time()),
        }
        get_redis().setex(_PREFIX + session_id, _TTL, json.dumps(payload, ensure_ascii=False))
        return True
    except Exception:
        logger.exception("set_pending failed: session=%s", session_id)
        return False


def get_pending(session_id: str) -> dict | None:
    """读取待确认动作，无则返回 None"""
    if not session_id:
        return None
    try:
        raw = get_redis().get(_PREFIX + session_id)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


def pop_pending(session_id: str) -> dict | None:
    """原子取出并删除待确认动作（Redis GETDEL）

    修复并发缺陷：旧流程"get_pending → 校验 → clear_pending"存在
    check-then-act 竞态，同会话并发两条"确认"会重复执行副作用。
    GETDEL 在 Redis 侧原子完成取出+删除，并发下仅一个请求能拿到。
    """
    if not session_id:
        return None
    try:
        raw = get_redis().getdel(_PREFIX + session_id)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


def clear_pending(session_id: str) -> None:
    """清除待确认动作"""
    if not session_id:
        return
    try:
        get_redis().delete(_PREFIX + session_id)
    except Exception:
        pass
