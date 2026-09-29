"""分类 CRUD 测试。"""

from tests.conftest import csrf_token


def _create_category(c, name="工具", icon="🧰"):
    token = csrf_token(c, "/admin/categories")
    return c.post(
        "/admin/categories",
        data={"csrf_token": token, "name": name, "icon": icon},
        follow_redirects=False,
    )


def test_category_crud(login, client):
    c = login(client)
    assert _create_category(c).status_code == 303
    page = c.get("/admin/categories")
    assert "工具" in page.text

    # 重复名称：拦截并提示
    r = _create_category(c, name="工具")
    assert r.status_code == 303
    assert "已存在" in c.get("/admin/categories").text

    # 更新
    token = csrf_token(c, "/admin/categories")
    r = c.post("/admin/categories/1", data={"csrf_token": token, "name": "效率工具", "icon": "⚡"},
               follow_redirects=False)
    assert r.status_code == 303
    assert "效率工具" in c.get("/admin/categories").text


def test_category_delete_cascades_links(login, client):
    c = login(client)
    _create_category(c)
    token = csrf_token(c, "/admin/links")
    c.post("/admin/links", data={"csrf_token": token, "category_id": "1", "title": "豆包",
                                 "url": "https://www.doubao.com"}, follow_redirects=False)
    assert len(c.get("/api/links").json()["links"]) == 1

    token = csrf_token(c, "/admin/categories")
    r = c.post("/admin/categories/1/delete", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303
    assert c.get("/api/links").json()["links"] == []
    assert c.get("/api/categories").json()["categories"] == []


def test_category_move(login, client):
    c = login(client)
    _create_category(c, name="A")
    _create_category(c, name="B")
    _create_category(c, name="C")

    token = csrf_token(c, "/admin/categories")
    c.post("/admin/categories/2/move", data={"csrf_token": token, "direction": "up"},
           follow_redirects=False)
    order = [x["name"] for x in c.get("/api/categories").json()["categories"]]
    assert order == ["B", "A", "C"]
