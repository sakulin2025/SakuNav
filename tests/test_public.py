"""公开导航页与公开 API 测试。"""

from tests.conftest import csrf_token


def _seed(c):
    token = csrf_token(c, "/admin/categories")
    c.post("/admin/categories", data={"csrf_token": token, "name": "工具"}, follow_redirects=False)
    token = csrf_token(c, "/admin/links")
    c.post("/admin/links", data={"csrf_token": token, "category_id": "1", "title": "豆包",
                                 "url": "https://www.doubao.com", "description": "AI 助手"},
           follow_redirects=False)


def test_home_renders_with_default_theme(login, client):
    c = login(client)
    _seed(c)
    html = c.get("/").text
    assert html.startswith("<!doctype html>")
    assert 'data-theme="default"' in html
    assert "豆包" in html
    assert "AI 助手" in html


def test_home_empty_state(client):
    html = client.get("/").text
    assert "这里还空空如也" in html


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_public_api(client):
    r = client.get("/api/links")
    assert r.status_code == 200
    r = client.get("/api/categories")
    assert r.status_code == 200
    r = client.get("/api/site")
    assert r.status_code == 200
    assert r.json()["site"]["title"] == "SakuNav"


def test_search_disabled_hides_box(login, client):
    c = login(client)
    _seed(c)
    token = csrf_token(c, "/admin/settings")
    c.post("/admin/settings", data={"csrf_token": token, "title": "SakuNav", "search_enabled": ""},
           follow_redirects=False)
    assert 'id="nav-search-input"' not in c.get("/").text


def test_site_title_customization(login, client):
    c = login(client)
    token = csrf_token(c, "/admin/settings")
    c.post("/admin/settings", data={"csrf_token": token, "title": "我的导航", "description": "自用"},
           follow_redirects=False)
    html = c.get("/").text
    assert "我的导航" in html
    assert "自用" in html
