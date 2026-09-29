"""主题管理测试：发现、激活、静态资源、zip 安装与安全校验。"""

import io
import zipfile

from tests.conftest import csrf_token


def test_theme_discovery(app):
    names = {t.name for t in app.state.theme_manager.discover()}
    assert {"default", "dark"} <= names


def test_activate_dark_theme(login, client):
    c = login(client)
    token = csrf_token(c, "/admin/themes")
    r = c.post("/admin/themes/activate", data={"csrf_token": token, "name": "dark"},
               follow_redirects=False)
    assert r.status_code == 303
    html = c.get("/").text
    assert 'data-theme="dark"' in html
    assert "/theme-static/dark/style.css" in html


def test_theme_static_served(client):
    assert client.get("/theme-static/default/style.css").status_code == 200
    assert client.get("/theme-static/default/not-exist.css").status_code == 404
    assert client.get("/theme-static/../secrets").status_code == 404


def _make_theme_zip(name="testtheme"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{name}/theme.toml", f'name="{name}"\nversion="1.0.0"\ndescription="测试"\ncolor_scheme="light"\n')
        z.writestr(f"{name}/templates/index.html",
                   '{% extends "theme_base.html" %}{% block body %}<h1>THEME TEST</h1>{% endblock %}')
        z.writestr(f"{name}/static/style.css", "body{}")
    return buf.getvalue()


def test_upload_and_activate_theme(login, client):
    c = login(client)
    token = csrf_token(c, "/admin/themes")
    r = c.post("/admin/themes/upload", data={"csrf_token": token},
               files={"file": ("t.zip", _make_theme_zip(), "application/zip")},
               follow_redirects=False)
    assert r.status_code == 303
    assert "安装成功" in c.get("/admin/themes").text

    token = csrf_token(c, "/admin/themes")
    c.post("/admin/themes/activate", data={"csrf_token": token, "name": "testtheme"},
           follow_redirects=False)
    assert "THEME TEST" in c.get("/").text

    # 删除用户主题
    token = csrf_token(c, "/admin/themes")
    r = c.post("/admin/themes/testtheme/delete", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303


def test_upload_bad_zip_rejected(login, client):
    c = login(client)
    token = csrf_token(c, "/admin/themes")
    r = c.post("/admin/themes/upload", data={"csrf_token": token},
               files={"file": ("bad.zip", b"not-a-zip", "application/zip")},
               follow_redirects=False)
    assert r.status_code == 303
    assert "不是有效的 zip" in c.get("/admin/themes").text


def test_upload_traversal_zip_rejected(login, client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../evil/theme.toml", 'name="evil"')
    c = login(client)
    token = csrf_token(c, "/admin/themes")
    r = c.post("/admin/themes/upload", data={"csrf_token": token},
               files={"file": ("evil.zip", buf.getvalue(), "application/zip")},
               follow_redirects=False)
    assert r.status_code == 303
    assert "目录名非法" in c.get("/admin/themes").text


def test_builtin_theme_not_deletable(login, client):
    c = login(client)
    # 先切换到非内置主题，再尝试删除内置 default
    token = csrf_token(c, "/admin/themes")
    c.post("/admin/themes/activate", data={"csrf_token": token, "name": "dark"}, follow_redirects=False)
    token = csrf_token(c, "/admin/themes")
    r = c.post("/admin/themes/default/delete", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303
    assert "内置主题不可删除" in c.get("/admin/themes").text


def test_active_theme_not_deletable(login, client):
    c = login(client)
    token = csrf_token(c, "/admin/themes")
    r = c.post("/admin/themes/default/delete", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303
    assert "不能删除当前正在使用的主题" in c.get("/admin/themes").text
