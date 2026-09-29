"""管理端 JSON API（全部端点要求管理员会话）。

供自动化脚本、第三方客户端与后续前端扩展使用；
与表单页面共享同一仓储层，语义一致。
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from sakunav import repos
from sakunav.auth import require_admin_api
from sakunav.db import all_settings, get_setting, set_setting
from sakunav.security import hash_password, verify_password
from sakunav.validation import validate_url

router = APIRouter(prefix="/api", dependencies=[Depends(require_admin_api)])


# ---------------- 请求模型 ----------------

class LinkIn(BaseModel):
    category_id: int
    title: str = Field(min_length=1, max_length=128)
    url: str
    description: str = ""
    icon: str = ""
    color: str = ""
    target: str = "_blank"


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    icon: str = ""


class ThemeActivateIn(BaseModel):
    name: str


class PluginToggleIn(BaseModel):
    enabled: bool


class PasswordIn(BaseModel):
    current: str
    new: str = Field(min_length=8, max_length=128)


def _db(request: Request):
    return request.app.state.db


def _pm(request: Request):
    return request.app.state.plugin_manager


def _tm(request: Request):
    return request.app.state.theme_manager


# ---------------- 链接 ----------------

@router.post("/links", status_code=201)
def api_create_link(request: Request, payload: LinkIn):
    db = _db(request)
    url = validate_url(payload.url)
    if url is None:
        raise HTTPException(status_code=400, detail="链接地址非法")
    if repos.get_category(db, payload.category_id) is None:
        raise HTTPException(status_code=400, detail="分类不存在")
    lid = repos.create_link(
        db,
        category_id=payload.category_id,
        title=payload.title,
        url=url,
        description=payload.description,
        icon=payload.icon,
        color=payload.color,
        target=payload.target if payload.target in ("_blank", "_self") else "_blank",
    )
    link = repos.get_link(db, lid)
    _pm(request).call_hook("on_link_create", link)
    return link


@router.put("/links/{lid}")
def api_update_link(request: Request, lid: int, payload: LinkIn):
    db = _db(request)
    if repos.get_link(db, lid) is None:
        raise HTTPException(status_code=404, detail="链接不存在")
    url = validate_url(payload.url)
    if url is None:
        raise HTTPException(status_code=400, detail="链接地址非法")
    repos.update_link(
        db,
        lid,
        category_id=payload.category_id,
        title=payload.title,
        url=url,
        description=payload.description,
        icon=payload.icon,
        color=payload.color,
        target=payload.target if payload.target in ("_blank", "_self") else "_blank",
    )
    link = repos.get_link(db, lid)
    _pm(request).call_hook("on_link_update", link)
    return link


@router.delete("/links/{lid}", status_code=204)
def api_delete_link(request: Request, lid: int):
    db = _db(request)
    if not repos.delete_link(db, lid):
        raise HTTPException(status_code=404, detail="链接不存在")
    _pm(request).call_hook("on_link_delete", lid)
    return Response(status_code=204)


@router.post("/links/{lid}/move")
def api_move_link(request: Request, lid: int, direction: str):
    if direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail="direction 仅支持 up/down")
    if not repos.move_link(_db(request), lid, direction):
        raise HTTPException(status_code=404, detail="链接不存在或已在边界")
    return {"ok": True}


# ---------------- 分类 ----------------

@router.post("/categories", status_code=201)
def api_create_category(request: Request, payload: CategoryIn):
    db = _db(request)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="分类名称不能为空")
    if any(c["name"] == name for c in repos.list_categories(db)):
        raise HTTPException(status_code=409, detail="分类名称已存在")
    cid = repos.create_category(db, name, payload.icon)
    return repos.get_category(db, cid)


@router.put("/categories/{cid}")
def api_update_category(request: Request, cid: int, payload: CategoryIn):
    db = _db(request)
    if repos.get_category(db, cid) is None:
        raise HTTPException(status_code=404, detail="分类不存在")
    if not repos.update_category(db, cid, name=payload.name.strip(), icon=payload.icon):
        raise HTTPException(status_code=409, detail="分类名称已存在")
    return repos.get_category(db, cid)


@router.delete("/categories/{cid}", status_code=204)
def api_delete_category(request: Request, cid: int):
    db = _db(request)
    links = repos.list_links(db, category_id=cid)
    if not repos.delete_category(db, cid):
        raise HTTPException(status_code=404, detail="分类不存在")
    for link in links:
        _pm(request).call_hook("on_link_delete", link["id"])
    return Response(status_code=204)


@router.post("/categories/{cid}/move")
def api_move_category(request: Request, cid: int, direction: str):
    if direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail="direction 仅支持 up/down")
    if not repos.move_category(_db(request), cid, direction):
        raise HTTPException(status_code=404, detail="分类不存在或已在边界")
    return {"ok": True}


# ---------------- 设置 ----------------

@router.get("/settings")
def api_get_settings(request: Request):
    return all_settings(_db(request))


@router.put("/settings")
def api_update_settings(request: Request, payload: dict[str, Any]):
    db = _db(request)
    changes: dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key or len(key) > 128:
            continue
        set_setting(db, key, value)
        changes[key] = value
    _pm(request).call_hook("on_settings_update", changes)
    return {"ok": True, "updated": list(changes.keys())}


# ---------------- 主题 ----------------

@router.get("/themes")
def api_list_themes(request: Request):
    db = _db(request)
    themes = [{"name": t.name, "version": t.version, "description": t.description,
               "author": t.author, "color_scheme": t.color_scheme, "builtin": t.builtin}
              for t in _tm(request).discover()]
    return {"themes": themes, "active": get_setting(db, "theme.active", "default")}


@router.post("/themes/activate")
def api_activate_theme(request: Request, payload: ThemeActivateIn):
    mgr = _tm(request)
    if mgr.get(payload.name) is None:
        raise HTTPException(status_code=404, detail="主题不存在")
    set_setting(_db(request), "theme.active", payload.name)
    return {"ok": True, "active": payload.name}


# ---------------- 插件 ----------------

@router.get("/plugins")
def api_list_plugins(request: Request):
    plugins = [{"name": p.name, "version": p.version, "description": p.description,
                "author": p.author, "builtin": p.builtin, "enabled": p.enabled}
               for p in _pm(request).discover()]
    return {"plugins": plugins}


@router.post("/plugins/{name}/toggle")
def api_toggle_plugin(request: Request, name: str, payload: PluginToggleIn):
    pm = _pm(request)
    if not pm.set_enabled(name, payload.enabled):
        raise HTTPException(status_code=404, detail="插件不存在")
    info = pm.get(name)
    return {"ok": True, "name": name, "enabled": bool(info and info.enabled)}


# ---------------- 密码 ----------------

@router.post("/password")
def api_change_password(request: Request, payload: PasswordIn):
    db = _db(request)
    stored = get_setting(db, "admin.password_hash", "")
    if not verify_password(payload.current, stored):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    set_setting(db, "admin.password_hash", hash_password(payload.new))
    return {"ok": True}
