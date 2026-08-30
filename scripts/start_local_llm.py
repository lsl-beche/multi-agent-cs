"""启动本地小型LLM服务（llama.cpp + GGUF模型，OpenAI兼容接口，免API Key）

用法：
    python scripts/start_local_llm.py
    python scripts/start_local_llm.py --port 8002 --ctx 8192

启动后：
    - OpenAI兼容接口: http://127.0.0.1:8001/v1/chat/completions
    - 无需API Key（客户端可填任意非空字符串）
    - CSagent 对接: .env 中设置 LLM_PROVIDER=local 即可
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="启动本地LLM服务")
    parser.add_argument("--model", default=settings.local_llm_model_path, help="GGUF模型路径")
    parser.add_argument("--host", default=settings.local_llm_host)
    parser.add_argument("--port", type=int, default=settings.local_llm_port)
    parser.add_argument("--ctx", type=int, default=settings.local_llm_ctx, help="上下文长度")
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"模型文件不存在: {model_path}")
        print("请先下载GGUF模型到 models/ 目录（参考 README「本地LLM」一节）")
        sys.exit(1)

    print(f"正在加载模型: {model_path} (CPU推理, 上下文 {args.ctx})")
    print(f"服务地址: http://{args.host}:{args.port}/v1  (免API Key)")
    print("对话模板: 自动检测GGUF内嵌模板（支持工具调用/tool calling）")

    cmd = [
        sys.executable, "-m", "llama_cpp.server",
        "--model", str(model_path),
        "--host", args.host,
        "--port", str(args.port),
        "--n_ctx", str(args.ctx),
        # 生成线程默认4（物理核数，8逻辑核含超线程实测反而更慢）；
        # 批量线程取4（物理核数），CPU prefill实测略快
        "--n_threads_batch", "4",
        # 服务启动级禁思考：Qwen3 在请求级 extra_body 传 enable_thinking 无效，
        # 必须作为 llama_cpp.server 的启动参数（模型加载时注入聊天模板）
        "--chat_template_kwargs", '{"enable_thinking": false}',
    ]
    # 注意：不指定 --chat_format，让llama.cpp自动读取GGUF内嵌的Jinja模板，
    # Qwen2.5模板原生支持OpenAI tools参数（Agent工具调用的前提）
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
