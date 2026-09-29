"""链接 CRUD 与 URL 校验测试。"""

from tests.conftest import csrf_token


def _seed_category(c):
    token = csrf_token(c, "/admin/categories")
    c.post("/admin/categories", data={"csrf_token": token, "name": "工具"}, follow_redirects=False)


def test_link_create_with_autocomplete(login, client):
    c = login(client)
    _seed_category(c)
    token = csrf_token(c, "/admin/links")
    r = c.post("/admin/links", data={"csrf_token": token, "category_id": "1", "title": "豆包",
                                     "url": "www.doubao.com"}, follow_redirects=False)
    assert r.status_code == 303
    links = c.get("/api/links").json()["links"]
    assert len(links) == 1
    assert links[0]["url"] == "https://www.doubao.com"
    assert links[0]["title"] == "豆包"


def test_link_rejects_unsafe_url(login, client):
    c = login(client)
    _seed_category(c)
    token = csrf_token(c, "/admin/links")
    c.post("/admin/links", data={"csrf_token": token, "category_id": "1", "title": "x",
                                 "url": "javascript:alert(1)"}, follow_redirects=False)
    assert c.get("/api/links").json()["links"] == []


def test_link_update(login, client):
    c = login(client)
    _seed_category(c)
    token = csrf_token(c, "/admin/links")
    c.post("/admin/links", data={"csrf_token": token, "category_id": "1", "title": "豆包",
                                 "url": "https://www.doubao.com"}, follow_redirects=False)
    token = csrf_token(c, "/admin/links")
    r = c.post("/admin/links/1", data={"csrf_token": token, "category_id": "1", "title": "豆包官网",
                                       "url": "https://www.doubao.com"}, follow_redirects=False)
    assert r.status_code == 303
    assert c.get("/api/links").json()["links"][0]["title"] == "豆包官网"


def test_link_delete(login, client):
    c = login(client)
    _seed_category(c)
    token = csrf_token(c, "/admin/links")
    c.post("/admin/links", data={"csrf_token": token, "category_id": "1", "title": "豆包",
                                 "url": "https://www.doubao.com"}, follow_redirects=False)
    token = csrf_token(c, "/admin/links")
    r = c.post("/admin/links/1/delete", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303
    assert c.get("/api/links").json()["links"] == []


def test_link_move(login, client):
    c = login(client)
    _seed_category(c)
    for i, title in enumerate(("A", "B", "C")):
        token = csrf_token(c, "/admin/links")
        c.post("/admin/links", data={"csrf_token": token, "category_id": "1", "title": title,
                                     "url": f"https://example.com/{i}"}, follow_redirects=False)
    token = csrf_token(c, "/admin/links")
    c.post("/admin/links/2/move", data={"csrf_token": token, "direction": "up"}, follow_redirects=False)
    order = [x["title"] for x in c.get("/api/links").json()["links"]]
    assert order == ["B", "A", "C"]


def test_public_page_search_data(login, client):
    c = login(client)
    _seed_category(c)
    token = csrf_token(c, "/admin/links")
    c.post("/admin/links", data={"csrf_token": token, "category_id": "1", "title": "豆包",
                                 "url": "https://www.doubao.com", "description": "AI 助手"},
           follow_redirects=False)
    html = c.get("/").text
    assert "data-search" in html
    assert "豆包" in html
