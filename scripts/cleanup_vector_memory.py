"""清理过期的对话向量记忆（可放入定时任务/CI）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dialogue.vector_memory import cleanup_expired

if __name__ == "__main__":
    n = cleanup_expired()
    print(f"已清理过期向量记忆：{n} 条")
