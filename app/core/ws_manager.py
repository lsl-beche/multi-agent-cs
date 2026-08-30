"""WebSocket 连接管理器：记录用户/管理员连接，支持跨通道消息转发

架构：
  user_connections  — session_id → [WebSocket]（一个用户一个连接）
  admin_connections — session_id → [WebSocket]（一个工单一个管理员连接）
  global_admin_connections — [WebSocket]（管理员全局监听，接收系统通知）

消息格式：
  {"type": "agent_message", "session_id": "...", "content": "..."}  — 管理员发给用户
  {"type": "chunk"|"done", ...}                                      — 系统/LLM 发给用户
  {"type": "new_ticket", "ticket": {...}}                            — 系统推送给全部管理员
"""
import asyncio
import logging

from fastapi import WebSocket

from app.core import metrics

logger = logging.getLogger(__name__)


class ConnectionManager:
    """单例管理器，生命周期与应用进程一致"""

    def __init__(self) -> None:
        # session_id → user WebSocket
        self.user_connections: dict[str, WebSocket] = {}
        # session_id → list of admin WebSocket
        self.admin_connections: dict[str, list[WebSocket]] = {}
        # 管理员全局监听列表（接收新工单等系统通知）
        self.global_admin_connections: list[WebSocket] = []

    # ── 用户连接 ──

    async def connect_user(self, session_id: str, ws: WebSocket) -> None:
        """注册用户 WebSocket"""
        self.user_connections[session_id] = ws
        metrics.WS_USERS_ONLINE.set(len(self.user_connections))
        metrics.ACTIVE_CHATS.set(len(self.user_connections))
        logger.debug("User connected: session=%s", session_id)

    def disconnect_user(self, session_id: str) -> None:
        """移除用户 WebSocket"""
        self.user_connections.pop(session_id, None)
        metrics.WS_USERS_ONLINE.set(len(self.user_connections))
        metrics.ACTIVE_CHATS.set(len(self.user_connections))
        logger.debug("User disconnected: session=%s", session_id)

    async def send_to_user(self, session_id: str, data: dict) -> bool:
        """向指定 session 的用户推送消息，返回是否成功"""
        ws = self.user_connections.get(session_id)
        if ws is None:
            return False
        try:
            await ws.send_json(data)
            return True
        except Exception:
            self.disconnect_user(session_id)
            return False

    # ── 管理员连接 ──

    async def connect_admin(self, session_id: str, ws: WebSocket) -> None:
        """注册管理员 WebSocket（监听某个转人工 session）"""
        self.admin_connections.setdefault(session_id, []).append(ws)
        logger.debug("Admin connected: session=%s", session_id)

    def disconnect_admin(self, session_id: str, ws: WebSocket) -> None:
        """移除管理员 WebSocket"""
        if session_id in self.admin_connections:
            self.admin_connections[session_id] = [
                c for c in self.admin_connections[session_id] if c != ws
            ]
            if not self.admin_connections[session_id]:
                del self.admin_connections[session_id]
        logger.debug("Admin disconnected: session=%s", session_id)

    async def send_to_admins(self, session_id: str, data: dict) -> int:
        """向监听指定 session 的所有管理员推送，返回成功数"""
        sent = 0
        clients = self.admin_connections.get(session_id, [])
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_admin(session_id, ws)
        return sent

    # ── 全局管理员监听 ──

    async def connect_global_admin(self, ws: WebSocket) -> None:
        """管理员连接到全局通知频道"""
        self.global_admin_connections.append(ws)
        metrics.WS_ADMINS_ONLINE.set(len(self.global_admin_connections))
        logger.debug("Global admin connected, total=%d", len(self.global_admin_connections))

    def disconnect_global_admin(self, ws: WebSocket) -> None:
        """管理员断开全局通知频道"""
        if ws in self.global_admin_connections:
            self.global_admin_connections.remove(ws)
        metrics.WS_ADMINS_ONLINE.set(len(self.global_admin_connections))
        logger.debug("Global admin disconnected, total=%d", len(self.global_admin_connections))

    async def broadcast_to_global_admins(self, data: dict) -> int:
        """向所有全局监听管理员广播消息，返回成功发送数"""
        sent = 0
        dead: list[WebSocket] = []
        for ws in self.global_admin_connections:
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_global_admin(ws)
        return sent

    def broadcast_to_global_admins_sync(self, data: dict) -> None:
        """同步版本：从非异步线程向全局管理员广播"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast_to_global_admins(data), loop)
        except RuntimeError:
            pass  # 无事件循环时静默跳过

    # ── 统计 ──

    def get_stats(self) -> dict:
        """获取实时统计数据"""
        return {
            "users_online": len(self.user_connections),
            "admin_online": len(self.global_admin_connections),
            "active_chats": len(self.user_connections),
            "admin_monitored_sessions": sum(len(v) for v in self.admin_connections.values()),
        }

    def get_pending_sessions(self) -> list[str]:
        """获取所有已创建用户连接但无管理员连接的 session_id（等待人工接入）"""
        return [sid for sid in self.user_connections]

    def is_user_online(self, session_id: str) -> bool:
        """检查用户是否在线"""
        return session_id in self.user_connections


# 全局单例
manager = ConnectionManager()
