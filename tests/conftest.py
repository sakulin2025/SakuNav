"""pytest 公共夹具：隔离数据库、预置管理员、CSRF 提取、登录助手。"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _fresh_settings(tmp_path: Path, root: Path = ROOT):
    from sakunav.config import Settings

    settings = Settings()
    settings.data_dir = tmp_path / "data"
    settings.db_path = tmp_path / "data" / "test.db"
    settings.extra_themes_dir = tmp_path / "data" / "themes"
    settings.extra_plugins_dir = tmp_path / "data" / "plugins"
    settings.secret_key = "test-secret-key"
    settings.admin_username = "admin"
    settings.admin_password = "test-pass-123"
    settings.themes_dir = root / "themes"
    settings.plugins_dir = root / "plugins"
    return settings


@pytest.fixture()
def app(tmp_path):
    from sakunav.main import create_app

    return create_app(_fresh_settings(tmp_path))


@pytest.fixture()
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


def csrf_token(client, url: str = "/login") -> str:
    """从页面 HTML 提取 CSRF 令牌（会话内保持不变）。"""
    r = client.get(url, follow_redirects=False)
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    assert m, f"页面 {url} 中未找到 CSRF 令牌"
    return m.group(1)


@pytest.fixture()
def login(client):
    """返回已登录的 TestClient。"""

    def _login(c=None):
        c = c or client
        token = csrf_token(c, "/login")
        r = c.post(
            "/login",
            data={"csrf_token": token, "username": "admin", "password": "test-pass-123"},
            follow_redirects=False,
        )
        assert r.status_code == 303, f"登录失败：{r.status_code} {r.text[:200]}"
        return c

    return _login
