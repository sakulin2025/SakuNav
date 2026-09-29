"""公开路由：导航首页、健康检查、公开只读 JSON API。"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from sakunav import __version__
from sakunav.auth import is_logged_in
from sakunav.context import public_page_context, render_theme_page
from sakunav.db import get_setting
from sakunav.repos import list_categories, list_links

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    """公开导航首页：按激活主题渲染。"""
    app = request.app
    db = app.state.db
    if not get_setting(db, "site.public_access", True) and not is_logged_in(request):
        return RedirectResponse("/login?next=/", status_code=303)

    active = app.state.theme_manager.active(get_setting(db, "theme.active", "default"))
    ctx = public_page_context(request, active)
    try:
        html = render_theme_page(request, active, ctx)
    except Exception as exc:  # 主题模板异常时给出可读错误而非白屏
        return HTMLResponse(
            f"<h1>主题渲染失败</h1><p>主题 {active.name} 缺少合法的 templates/index.html "
            f"或模板存在错误：{exc}</p>",
            status_code=500,
        )
    return HTMLResponse(html)


@router.get("/api/health")
def health(request: Request):
    return {"status": "ok", "app": request.app.title, "version": __version__}


def _require_public_or_admin(request: Request) -> None:
    """公开 JSON API 守卫：站点设为私有时需登录。"""
    if not get_setting(request.app.state.db, "site.public_access", True) and not is_logged_in(request):
        raise HTTPException(status_code=401, detail="站点为私有模式，请先登录")


@router.get("/api/links")
def api_links(request: Request, category: int | None = None, search: str | None = None):
    _require_public_or_admin(request)
    return {"links": list_links(request.app.state.db, category_id=category, search=search)}


@router.get("/api/categories")
def api_categories(request: Request):
    _require_public_or_admin(request)
    return {"categories": list_categories(request.app.state.db, with_counts=True)}


@router.get("/api/site")
def api_site(request: Request):
    _require_public_or_admin(request)
    db = request.app.state.db
    return {
        "site": {
            "title": get_setting(db, "site.title", "SakuNav"),
            "description": get_setting(db, "site.description", ""),
            "search_enabled": get_setting(db, "search.enabled", True),
        }
    }
