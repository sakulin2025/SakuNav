"""插件系统测试：启停、钩子注入、管理端扩展、数据类钩子。"""

from tests.conftest import csrf_token


def _toggle(c, name, enabled):
    token = csrf_token(c, "/admin/plugins")
    return c.post(f"/admin/plugins/{name}/toggle",
                  data={"csrf_token": token, "enabled": "1" if enabled else "0"},
                  follow_redirects=False)


def test_hello_plugin_hooks(login, client):
    c = login(client)
    assert "欢迎使用 SakuNav" not in c.get("/").text

    assert _toggle(c, "hello", True).status_code == 303
    html = c.get("/").text
    assert "欢迎使用 SakuNav" in html          # footer_html 钩子
    assert "Hello 示例" in c.get("/admin").text   # admin_nav 钩子

    # 插件自定义管理页（受登录保护）
    r = c.get("/admin/plugins/hello")
    assert r.status_code == 200
    assert "Hello 插件面板" in r.text

    # 停用后立即失效
    assert _toggle(c, "hello", False).status_code == 303
    assert "欢迎使用 SakuNav" not in c.get("/").text


def test_hello_plugin_route_requires_login(login, client, app):
    """插件自定义管理页：启用后未登录访问返回 401。"""
    from fastapi.testclient import TestClient

    c = login(client)
    token = csrf_token(c, "/admin/plugins")
    c.post("/admin/plugins/hello/toggle", data={"csrf_token": token, "enabled": "1"},
           follow_redirects=False)
    anon = TestClient(app)
    assert anon.get("/admin/plugins/hello", follow_redirects=False).status_code == 401


def test_links_counter_hooks(login, client):
    c = login(client)
    _toggle(c, "links-counter", True)

    # 创建链接触发 on_link_create
    token = csrf_token(c, "/admin/categories")
    c.post("/admin/categories", data={"csrf_token": token, "name": "工具"}, follow_redirects=False)
    token = csrf_token(c, "/admin/links")
    c.post("/admin/links", data={"csrf_token": token, "category_id": "1", "title": "豆包",
                                 "url": "https://www.doubao.com"}, follow_redirects=False)

    html = c.get("/").text
    assert "已收录 1 条链接" in html           # footer_html 钩子读取计数

    # 删除链接触发 on_link_delete
    token = csrf_token(c, "/admin/links")
    c.post("/admin/links/1/delete", data={"csrf_token": token}, follow_redirects=False)
    assert "已收录" not in c.get("/").text


def test_plugin_settings_namespace(login, client):
    """插件通过 plugin_api 读写独立命名空间设置。"""
    from sakunav import plugin_api

    plugin_api.set_setting("links_counter.total", 42)
    plugin_api.set_setting("links_counter.extra", {"a": 1})
    assert plugin_api.get_setting("links_counter.total") == 42
    assert plugin_api.get_setting("links_counter.extra") == {"a": 1}
