"""管理面板页面路由：服务端渲染 + 表单提交 + CSRF 防护。"""

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from sakunav import repos
from sakunav.auth import is_logged_in, login, logout, require_admin_page
from sakunav.context import flash, render
from sakunav.db import get_setting, set_setting
from sakunav.security import hash_password, verify_csrf, verify_password
from sakunav.validation import validate_url

router = APIRouter(include_in_schema=False)


# ---------------- CSRF 依赖 ----------------

def require_csrf(request: Request, csrf_token: str = Form("")) -> None:
    if not verify_csrf(request.session, csrf_token):
        raise HTTPException(status_code=400, detail="CSRF 校验失败，请刷新页面后重试")


def _safe_referer(request: Request, fallback: str = "/admin") -> str:
    """仅允许回跳本站 /admin 路径，防开放重定向。"""
    ref = request.headers.get("referer", "")
    path = urlparse(ref).path
    if ref and path.startswith("/admin/"):
        return path
    return fallback


# ---------------- 登录 / 登出 ----------------

@router.get("/login")
def login_page(request: Request, next: str = ""):
    if is_logged_in(request):
        return RedirectResponse("/admin", status_code=303)
    return render(request, "login.html", {"next": next, "error": ""})


@router.post("/login", dependencies=[Depends(require_csrf)])
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(""),
):
    db = request.app.state.db
    stored_user = get_setting(db, "admin.username")
    stored_hash = get_setting(db, "admin.password_hash", "")
    if stored_user is None or username != stored_user or not verify_password(password, stored_hash):
        return render(request, "login.html", {"next": next, "error": "用户名或密码错误"}, status_code=400)
    login(request)
    flash(request, "欢迎回来", "success")
    target = next if (next.startswith("/") and not next.startswith("//")) else "/admin"
    return RedirectResponse(target, status_code=303)


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout_view(request: Request):
    logout(request)
    return RedirectResponse("/login", status_code=303)


# ---------------- 概览 ----------------

@router.get("/admin", dependencies=[Depends(require_admin_page)])
def dashboard(request: Request):
    db = request.app.state.db
    stats = {
        "links": repos.count_links(db),
        "categories": repos.count_categories(db),
        "theme": get_setting(db, "theme.active", "default"),
        "plugins": len(request.app.state.plugin_manager.enabled_names()),
    }
    return render(
        request,
        "admin/dashboard.html",
        {"active": "dashboard", "stats": stats, "recent": repos.recent_links(db)},
    )


# ---------------- 链接管理 ----------------

@router.get("/admin/links", dependencies=[Depends(require_admin_page)])
def links_page(request: Request, category: int | None = None, edit: int | None = None):
    db = request.app.state.db
    categories = repos.list_categories(db)
    cat_names = {c["id"]: c["name"] for c in categories}
    links = repos.list_links(db, category_id=category)
    for link in links:
        link["category_name"] = cat_names.get(link["category_id"])
    editing = repos.get_link(db, edit) if edit else None
    return render(
        request,
        "admin/links.html",
        {
            "active": "links",
            "categories": categories,
            "links": links,
            "current_category": category,
            "editing": editing,
        },
    )


@router.post("/admin/links", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def links_create(
    request: Request,
    title: str = Form(...),
    url: str = Form(...),
    category_id: int = Form(...),
    description: str = Form(""),
    icon: str = Form(""),
    color: str = Form(""),
    target: str = Form("_blank"),
):
    db = request.app.state.db
    valid_url = validate_url(url)
    if valid_url is None:
        flash(request, "链接地址非法（仅支持 http/https/ftp/mailto/tel/magnet）", "error")
        return RedirectResponse("/admin/links", status_code=303)
    if repos.get_category(db, category_id) is None:
        flash(request, "请选择有效的分类", "error")
        return RedirectResponse("/admin/links", status_code=303)
    lid = repos.create_link(
        db,
        category_id=category_id,
        title=title,
        url=valid_url,
        description=description,
        icon=icon,
        color=color,
        target=target if target in ("_blank", "_self") else "_blank",
    )
    request.app.state.plugin_manager.call_hook("on_link_create", repos.get_link(db, lid))
    flash(request, "链接已添加", "success")
    return RedirectResponse(f"/admin/links?category={category_id}", status_code=303)


@router.post("/admin/links/{lid}", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def links_update(
    request: Request,
    lid: int,
    title: str = Form(...),
    url: str = Form(...),
    category_id: int = Form(...),
    description: str = Form(""),
    icon: str = Form(""),
    color: str = Form(""),
    target: str = Form("_blank"),
):
    db = request.app.state.db
    if repos.get_link(db, lid) is None:
        raise HTTPException(status_code=404, detail="链接不存在")
    valid_url = validate_url(url)
    if valid_url is None:
        flash(request, "链接地址非法", "error")
        return RedirectResponse(f"/admin/links/{lid}/edit", status_code=303)
    repos.update_link(
        db,
        lid,
        category_id=category_id,
        title=title,
        url=valid_url,
        description=description,
        icon=icon,
        color=color,
        target=target if target in ("_blank", "_self") else "_blank",
    )
    request.app.state.plugin_manager.call_hook("on_link_update", repos.get_link(db, lid))
    flash(request, "链接已更新", "success")
    return RedirectResponse("/admin/links", status_code=303)


@router.post("/admin/links/{lid}/delete", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def links_delete(request: Request, lid: int):
    db = request.app.state.db
    if repos.delete_link(db, lid):
        request.app.state.plugin_manager.call_hook("on_link_delete", lid)
        flash(request, "链接已删除", "success")
    return RedirectResponse(_safe_referer(request, "/admin/links"), status_code=303)


@router.post("/admin/links/{lid}/move", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def links_move(request: Request, lid: int, direction: str = Form(...)):
    if direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail="非法方向")
    repos.move_link(request.app.state.db, lid, direction)
    return RedirectResponse(_safe_referer(request, "/admin/links"), status_code=303)


# ---------------- 分类管理 ----------------

@router.get("/admin/categories", dependencies=[Depends(require_admin_page)])
def categories_page(request: Request, edit: int | None = None):
    db = request.app.state.db
    editing = repos.get_category(db, edit) if edit else None
    return render(
        request,
        "admin/categories.html",
        {"active": "categories", "categories": repos.list_categories(db, with_counts=True), "editing": editing},
    )


@router.post("/admin/categories", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def categories_create(request: Request, name: str = Form(...), icon: str = Form("")):
    db = request.app.state.db
    name = name.strip()
    if not name:
        flash(request, "分类名称不能为空", "error")
        return RedirectResponse("/admin/categories", status_code=303)
    try:
        repos.create_category(db, name, icon)
        flash(request, "分类已创建", "success")
    except Exception:
        flash(request, "分类名称已存在", "error")
    return RedirectResponse("/admin/categories", status_code=303)


@router.post("/admin/categories/{cid}", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def categories_update(request: Request, cid: int, name: str = Form(...), icon: str = Form("")):
    db = request.app.state.db
    if repos.get_category(db, cid) is None:
        raise HTTPException(status_code=404, detail="分类不存在")
    try:
        repos.update_category(db, cid, name=name.strip(), icon=icon)
        flash(request, "分类已更新", "success")
    except Exception:
        flash(request, "分类名称已存在", "error")
    return RedirectResponse("/admin/categories", status_code=303)


@router.post("/admin/categories/{cid}/delete", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def categories_delete(request: Request, cid: int):
    db = request.app.state.db
    links = repos.list_links(db, category_id=cid)
    if repos.delete_category(db, cid):
        for link in links:  # 级联删除的链接同样通知插件
            request.app.state.plugin_manager.call_hook("on_link_delete", link["id"])
        flash(request, f"分类已删除（含 {len(links)} 条链接）", "success")
    return RedirectResponse("/admin/categories", status_code=303)


@router.post("/admin/categories/{cid}/move", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def categories_move(request: Request, cid: int, direction: str = Form(...)):
    if direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail="非法方向")
    repos.move_category(request.app.state.db, cid, direction)
    return RedirectResponse("/admin/categories", status_code=303)


# ---------------- 主题管理 ----------------

@router.get("/admin/themes", dependencies=[Depends(require_admin_page)])
def themes_page(request: Request):
    mgr = request.app.state.theme_manager
    active = get_setting(request.app.state.db, "theme.active", "default")
    return render(
        request,
        "admin/themes.html",
        {"active": "themes", "themes": mgr.discover(), "active_theme": active},
    )


@router.post("/admin/themes/activate", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def themes_activate(request: Request, name: str = Form(...)):
    mgr = request.app.state.theme_manager
    if mgr.get(name) is None:
        flash(request, f"主题 {name} 不存在", "error")
    else:
        set_setting(request.app.state.db, "theme.active", name)
        flash(request, f"已启用主题 {name}", "success")
    return RedirectResponse("/admin/themes", status_code=303)


@router.post("/admin/themes/upload", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def themes_upload(request: Request, file: UploadFile = File(...)):
    mgr = request.app.state.theme_manager
    max_size = request.app.state.settings.max_upload_size
    data = file.file.read(max_size + 1)
    if len(data) > max_size:
        flash(request, f"文件超过大小限制（{max_size // 1024 // 1024}MB）", "error")
    else:
        try:
            theme = mgr.install_zip(data)
            flash(request, f"主题 {theme.name} v{theme.version} 安装成功", "success")
        except ValueError as exc:
            flash(request, str(exc), "error")
    return RedirectResponse("/admin/themes", status_code=303)


@router.post("/admin/themes/{name}/delete", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def themes_delete(request: Request, name: str):
    mgr = request.app.state.theme_manager
    db = request.app.state.db
    active = get_setting(db, "theme.active", "default")
    if name == active:
        flash(request, "不能删除当前正在使用的主题", "error")
    elif mgr.remove(name):
        flash(request, f"主题 {name} 已删除", "success")
    else:
        flash(request, "内置主题不可删除或主题不存在", "error")
    return RedirectResponse("/admin/themes", status_code=303)


# ---------------- 插件管理 ----------------

@router.get("/admin/plugins", dependencies=[Depends(require_admin_page)])
def plugins_page(request: Request):
    pm = request.app.state.plugin_manager
    return render(request, "admin/plugins.html", {"active": "plugins", "plugins": pm.discover()})


@router.post("/admin/plugins/{name}/toggle", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def plugins_toggle(request: Request, name: str, enabled: str = Form("")):
    pm = request.app.state.plugin_manager
    want = enabled == "1"
    if pm.set_enabled(name, want):
        flash(request, f"插件 {name} 已{'启用' if want else '停用'}", "success")
        if want and _plugin_has_route_hook(pm, name):
            flash(request, "提示：注册了路由的插件需重启容器后完全生效", "info")
    else:
        flash(request, f"插件 {name} 不存在", "error")
    return RedirectResponse("/admin/plugins", status_code=303)


def _plugin_has_route_hook(pm, name: str) -> bool:
    try:
        module = pm.load(name)
        return callable(getattr(module, "register_routes", None))
    except Exception:
        return False


# ---------------- 设置 ----------------

@router.get("/admin/settings", dependencies=[Depends(require_admin_page)])
def settings_page(request: Request):
    return render(request, "admin/settings.html", {"active": "settings"})


@router.post("/admin/settings", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def settings_save(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    logo: str = Form(""),
    footer: str = Form(""),
    public_access: str = Form(""),
    search_enabled: str = Form(""),
    target_default: str = Form("_blank"),
):
    db = request.app.state.db
    changes = {
        "site.title": title.strip() or "SakuNav",
        "site.description": description.strip(),
        "site.logo": logo.strip(),
        "site.footer": footer.strip(),
        "site.public_access": public_access == "1",
        "search.enabled": search_enabled == "1",
        "links.target_default": target_default if target_default in ("_blank", "_self") else "_blank",
    }
    for key, value in changes.items():
        set_setting(db, key, value)
    request.app.state.plugin_manager.call_hook("on_settings_update", changes)
    flash(request, "设置已保存", "success")
    return RedirectResponse("/admin/settings", status_code=303)


@router.post("/admin/password", dependencies=[Depends(require_admin_page), Depends(require_csrf)])
def password_change(
    request: Request,
    current: str = Form(...),
    new: str = Form(...),
    confirm: str = Form(...),
):
    db = request.app.state.db
    stored = get_setting(db, "admin.password_hash", "")
    if not verify_password(current, stored):
        flash(request, "当前密码不正确", "error")
        return RedirectResponse("/admin/settings", status_code=303)
    if len(new) < 8:
        flash(request, "新密码长度至少 8 位", "error")
        return RedirectResponse("/admin/settings", status_code=303)
    if new != confirm:
        flash(request, "两次输入的新密码不一致", "error")
        return RedirectResponse("/admin/settings", status_code=303)
    set_setting(db, "admin.password_hash", hash_password(new))
    flash(request, "密码已修改", "success")
    return RedirectResponse("/admin/settings", status_code=303)
