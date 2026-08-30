"""生成随机生产密钥并写入 .env（安全：密钥不入 Git，.env 已在 .gitignore）

用法：
    python scripts/generate_secrets.py              # 生成并写入 .env
    python scripts/generate_secrets.py --show       # 只打印，不写文件
"""
import argparse
import secrets
from pathlib import Path


def new_secret(n=48) -> str:
    return secrets.token_hex(n)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true", help="只打印不写入")
    args = parser.parse_args()
    jwt_secret = new_secret(32)
    api_secret = new_secret(32)
    gateway_secret = new_secret(32)
    if args.show:
        print(f"JWT_SECRET_KEY={jwt_secret}")
        print(f"API_SECRET_KEY={api_secret}")
        print(f"PAYMENT_GATEWAY_SECRET={gateway_secret}")
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    text = env_path.read_text(encoding="utf-8")
    replacements = {
        "JWT_SECRET_KEY=": jwt_secret,
        "API_SECRET_KEY=": api_secret,
        "PAYMENT_GATEWAY_SECRET=": gateway_secret,
    }
    lines = text.splitlines()
    out = []
    for line in lines:
        replaced = False
        for prefix, value in replacements.items():
            if line.startswith(prefix):
                out.append(f"{prefix}{value}")
                replaced = True
                break
        if not replaced:
            out.append(line)
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("已写入 .env：JWT/API/支付网关密钥（共 3 项）")


if __name__ == "__main__":
    main()
