"""API 集成冒烟：依赖运行中的后端（未运行则跳过，供本地/CI 服务启动后执行）"""
import json
import urllib.request

import pytest


@pytest.fixture(scope="module")
def base():
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
    except Exception:
        pytest.skip("后端未运行，跳过集成冒烟")
    return "http://127.0.0.1:8000"


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return json.loads(r.read())


def test_health(base):
    data = _get(base, "/api/health")
    assert data["status"] == "ok"
    assert "postgres" in data["deps"] and "redis" in data["deps"]


def test_privacy(base):
    data = _get(base, "/api/privacy")
    assert "memory_enabled" in data["data"]
    assert "erase_endpoint" in data["data"]


def test_products_list(base):
    data = _get(base, "/api/products?page=1&page_size=5")
    assert data["code"] == 0
    assert data["data"]["total"] >= 0
