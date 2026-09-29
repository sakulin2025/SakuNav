"""认证与会话测试。"""

from tests.conftest import csrf_token


def test_login_success_and_admin_page(login, client):
    c = login(client)
    r = c.get("/admin")
    assert r.status_code == 200
    assert "概览" in r.text


def test_login_wrong_password(client):
    token = csrf_token(client, "/login")
    r = client.post(
        "/login",
        data={"csrf_token": token, "username": "admin", "password": "wrong-pass"},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_admin_requires_login(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login")


def test_public_api_requires_login_when_private(login, client, app):
    """私有模式下未登录访问公开 JSON 返回 401。"""
    from fastapi.testclient import TestClient

    c = login(client)
    token = csrf_token(c, "/admin/settings")
    c.post("/admin/settings", data={"csrf_token": token, "title": "SakuNav", "public_access": ""})
    anon = TestClient(app)  # 全新匿名会话
    assert anon.get("/api/links").status_code == 401
    assert c.get("/api/links").status_code == 200


def test_logout(login, client):
    c = login(client)
    token = csrf_token(c, "/admin")
    r = c.post("/logout", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303
    assert c.get("/admin", follow_redirects=False).status_code == 303


def test_csrf_rejected_without_token(login, client):
    c = login(client)
    r = c.post("/admin/settings", data={"title": "x"}, follow_redirects=False)
    assert r.status_code == 400
