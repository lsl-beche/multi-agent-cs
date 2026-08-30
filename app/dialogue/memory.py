"""会话级短期记忆：Redis 持久化 + 本地内存兜底

职责：
1. load/append：保存该会话最近对话（role/content/ts），单次 SET 高效写入
2. 滚动摘要：旧轮次被 LLM 压缩成摘要（get_summary/set_summary），
   注入后续上下文，避免 20 条上限导致早期信息丢失
3. 折叠计数（get_folded/set_folded）：记录"已折进摘要"的消息数，
   保证每条旧消息只被摘要一次（幂等，不重复浪费 LLM 调用）

存储设计：
- Redis 键 csagent:session:<sid>，TTL 24 小时，最多 20 条
- Redis 不可用时降级到进程内 _local_store（仅开发调试用）
- PostgreSQL 全量落库在 persistence.py（跨天恢复），两者互补
"""
import json
import time

from app.core.redis_client import get_redis

_PREFIX = "csagent:session:"
_SUMMARY_PREFIX = "csagent:session:summary:"
_FOLD_PREFIX = "csagent:session:folded:"
_TTL = 60 * 60 * 24  # 会话保留24小时
_MAX_HISTORY = 20  # 最多保留20条，控制LLM上下文长度

# 本地兜底（Redis不可用时，仅开发调试用）
_local_store: dict[str, list[dict]] = {}
_local_summary: dict[str, str] = {}


class SessionMemory:
    def load(self, session_id: str) -> list[dict]:
        """加载会话历史 [{role, content, ts}, ...]

        role 取值：user（用户）/ assistant（客服 AI）/ agent（人工客服）
        ts：unix 时间戳（前端展示时间用）
        """
        try:
            raw = get_redis().get(_PREFIX + session_id)
            return json.loads(raw) if raw else []
        except Exception:
            return _local_store.get(session_id, [])[:]

    def append(self, session_id: str, role: str, content: str) -> None:
        """追加一条消息到会话历史

        实现细节：先 GET 现有历史 → 追加 → 截断到 20 条 → SETEX。
        仅一次 SET 操作（而非 load+set 两次往返），降低 Redis 延迟。
        """
        # 先尝试从 Redis 加载现有历史
        history = None
        try:
            raw = get_redis().get(_PREFIX + session_id)
            history = json.loads(raw) if raw else []
        except Exception:
            history = _local_store.get(session_id, [])[:]

        history.append({"role": role, "content": content, "ts": int(time.time())})
        history = history[-_MAX_HISTORY:]

        try:
            get_redis().setex(_PREFIX + session_id, _TTL, json.dumps(history, ensure_ascii=False))
        except Exception:
            _local_store[session_id] = history

    def clear(self, session_id: str) -> None:
        """清空会话历史与滚动摘要"""
        try:
            r = get_redis()
            r.delete(_PREFIX + session_id)
            r.delete(_SUMMARY_PREFIX + session_id)
        except Exception:
            _local_store.pop(session_id, None)
            _local_summary.pop(session_id, None)

    # ── 滚动摘要（长期记忆之一：压缩旧轮次） ──

    def get_summary(self, session_id: str) -> str:
        """读取会话滚动摘要"""
        try:
            raw = get_redis().get(_SUMMARY_PREFIX + session_id)
            return raw or ""
        except Exception:
            return _local_summary.get(session_id, "")

    def set_summary(self, session_id: str, text: str) -> None:
        """写入会话滚动摘要"""
        try:
            get_redis().setex(_SUMMARY_PREFIX + session_id, _TTL, text or "")
        except Exception:
            _local_summary[session_id] = text or ""

    def get_folded(self, session_id: str) -> int:
        """已折叠进摘要的消息条数"""
        try:
            raw = get_redis().get(_FOLD_PREFIX + session_id)
            return int(raw) if raw else 0
        except Exception:
            return 0

    def set_folded(self, session_id: str, n: int) -> None:
        try:
            get_redis().setex(_FOLD_PREFIX + session_id, _TTL, str(n))
        except Exception:
            pass
