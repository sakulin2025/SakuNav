"""管理端 JSON API 测试。"""

from fastapi.testclient import TestClient

from tests.conftest import csrf_token


def test_api_requires_login(client):
    """管理端 API 未登录返回 401；公开只读 API 在公开模式下可直接访问。"""
    assert client.get("/api/settings").status_code == 401
    assert client.post("/api/links", json={}).status_code == 401
    assert client.post("/api/password", json={}).status_code == 401
    # 公开只读 API
    assert client.get("/api/links").status_code == 200
    assert client.get("/api/categories").status_code == 200


def test_api_links_crud(login, client):
    c = login(client)
    r = c.post("/api/categories", json={"name": "工具", "icon": "🧰"})
    assert r.status_code == 201
    cid = r.json()["id"]

    r = c.post("/api/links", json={"category_id": cid, "title": "豆包", "url": "https://www.doubao.com"})
    assert r.status_code == 201
    lid = r.json()["id"]
    assert r.json()["url"] == "https://www.doubao.com"

    r = c.put(f"/api/links/{lid}", json={"category_id": cid, "title": "豆包2", "url": "https://www.doubao.com"})
    assert r.json()["title"] == "豆包2"

    assert c.delete(f"/api/links/{lid}").status_code == 204
    assert c.get("/api/links").json()["links"] == []


def test_api_bad_url_rejected(login, client):
    c = login(client)
    r = c.post("/api/links", json={"category_id": 1, "title": "x", "url": "javascript:alert(1)"})
    assert r.status_code == 400


def test_api_category_duplicate(login, client):
    c = login(client)
    assert c.post("/api/categories", json={"name": "A"}).status_code == 201
    assert c.post("/api/categories", json={"name": "A"}).status_code == 409


def test_api_settings_update(login, client):
    c = login(client)
    r = c.put("/api/settings", json={"site.title": "新标题", "site.public_access": False})
    assert r.status_code == 200
    assert c.get("/api/settings").json()["site.title"] == "新标题"
    assert c.get("/api/settings").json()["site.public_access"] is False


def test_api_theme_activate(login, client):
    c = login(client)
    r = c.post("/api/themes/activate", json={"name": "dark"})
    assert r.status_code == 200
    assert c.get("/api/themes").json()["active"] == "dark"
    assert c.post("/api/themes/activate", json={"name": "不存在"}).status_code == 404


def test_api_plugin_toggle(login, client):
    c = login(client)
    r = c.post("/api/plugins/hello/toggle", json={"enabled": True})
    assert r.status_code == 200
    assert c.get("/api/plugins").json()["plugins"][0]["enabled"] is True
    c.post("/api/plugins/hello/toggle", json={"enabled": False})


def test_api_password_change(login, client, app):
    c = login(client)
    assert c.post("/api/password", json={"current": "test-pass-123", "new": "new-pass-4567"}).status_code == 200

    # 旧密码失效，新密码可登录
    c2 = TestClient(app)
    token = csrf_token(c2, "/login")
    r = c2.post("/login", data={"csrf_token": token, "username": "admin", "password": "test-pass-123"},
                follow_redirects=False)
    assert r.status_code == 400
    token = csrf_token(c2, "/login")
    r = c2.post("/login", data={"csrf_token": token, "username": "admin", "password": "new-pass-4567"},
                follow_redirects=False)
    assert r.status_code == 303
