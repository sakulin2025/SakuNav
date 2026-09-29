"""模板上下文装配：把站点设置、主题、插件注入与 CSRF 统一注入每个页面。"""

from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import Request
from fastapi.responses import HTMLResponse
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from sakunav import __version__
from sakunav.auth import is_logged_in
from sakunav.db import all_settings, get_setting
from sakunav.repos import list_categories, list_links
from sakunav.security import csrf_token
from sakunav.theme_manager import ThemeInfo

_PALETTE = [
    "#4f46e5", "#0ea5e9", "#10b981", "#f59e0b",
    "#ef4444", "#8b5cf6", "#14b8a6", "#f97316",
]


def flash(request: Request, message: str, kind: str = "info") -> None:
    request.session.setdefault("flashes", []).append({"message": message, "kind": kind})


def pop_flashes(request: Request) -> list[dict]:
    return request.session.pop("flashes", [])


def icon_for(link: dict) -> dict:
    """计算链接图标：优先自定义图标 URL，否则使用标题首字母色块。"""
    if link.get("icon"):
        return {"type": "image", "url": link["icon"]}
    title = (link.get("title") or "?").strip()
    letter = title[0].upper() if title else "?"
    color = link.get("color") or _PALETTE[sum(ord(c) for c in title) % len(_PALETTE)]
    return {"type": "letter", "letter": letter, "color": color}


def enrich_link(link: dict) -> dict:
    link["icon_display"] = icon_for(link)
    return link


def standard_context(request: Request) -> dict:
    """每个页面共享的上下文基座。"""
    app = request.app
    db = app.state.db
    settings_all = all_settings(db)
    site = {
        "title": settings_all.get("site.title", "SakuNav"),
        "description": settings_all.get("site.description", ""),
        "logo": settings_all.get("site.logo", ""),
        "footer": settings_all.get("site.footer", ""),
        "public_access": get_setting(db, "site.public_access", True),
        "target_default": settings_all.get("links.target_default", "_blank"),
    }
    plugin_manager = app.state.plugin_manager
    ctx: dict[str, Any] = {
        "site": site,
        "user": is_logged_in(request),
        "settings": settings_all,
        "version": __version__,
        "request": request,
        "csrf_token": csrf_token(request.session),
        "flashes": pop_flashes(request),
    }

    head_parts = [x for x in plugin_manager.call_hook("head_html", ctx) if x]
    foot_parts = [x for x in plugin_manager.call_hook("footer_html", ctx) if x]
    ctx["plugin_head_html"] = Markup("".join(head_parts))
    ctx["plugin_footer_html"] = Markup("".join(foot_parts))

    nav_parts: list[dict] = []
    for item in plugin_manager.call_hook("admin_nav"):
        if isinstance(item, list):
            nav_parts.extend(item)
    ctx["plugin_nav"] = nav_parts
    return ctx


def render(request: Request, template: str, ctx: Optional[dict] = None, status_code: int = 200) -> HTMLResponse:
    """渲染应用内置模板（管理端页面）。"""
    data = standard_context(request)
    if ctx:
        data.update(ctx)
    template_obj = request.app.state.jinja_env.get_template(template)
    return HTMLResponse(template_obj.render(**data), status_code=status_code)


def render_theme_page(request: Request, theme: ThemeInfo, ctx: dict) -> str:
    """按当前激活主题渲染公开导航页。

    主题模板目录优先，extends 的 theme_base.html 回退到应用内置模板。
    每个主题独立 Jinja 环境，缓存于 app.state.theme_envs。
    """
    app = request.app
    cache: dict = app.state.theme_envs
    key = theme.name
    if key not in cache:
        theme_templates = Path(theme.source_dir) / "templates"
        loaders = []
        if theme_templates.is_dir():
            loaders.append(FileSystemLoader(str(theme_templates)))
        loaders.append(FileSystemLoader(str(app.state.app_templates_dir)))
        cache[key] = Environment(
            loader=ChoiceLoader(loaders),
            autoescape=select_autoescape(["html", "xml"]),
        )
    template = cache[key].get_template("index.html")
    return template.render(**ctx)


def public_page_context(request: Request, theme: ThemeInfo) -> dict:
    """装配公开导航页上下文（含插件数据钩子与链接过滤钩子）。"""
    app = request.app
    db = app.state.db
    ctx = standard_context(request)

    categories = list_categories(db, with_counts=True)
    links_by_cat: dict[int, list[dict]] = {}
    for link in list_links(db):
        links_by_cat.setdefault(link["category_id"], []).append(enrich_link(link))
    for cat in categories:
        cat["links"] = links_by_cat.get(cat["id"], [])

    ctx.update(
        {
            "categories": categories,
            "theme": theme,
            "theme_url": _theme_url_builder(theme),
            "icon_for": icon_for,
            "search_enabled": get_setting(db, "search.enabled", True),
        }
    )

    # 插件数据钩子：可修改上下文（如注入统计数据）
    app.state.plugin_manager.call_hook("page_data", ctx, {"page": "index", "request": request})

    # 插件链接过滤钩子：返回 list 时整体替换分类数据
    for result in app.state.plugin_manager.call_hook("link_filter", ctx["categories"], {"page": "index"}):
        if isinstance(result, list):
            ctx["categories"] = result
    return ctx


def _theme_url_builder(theme: ThemeInfo) -> Callable[[str], str]:
    def _build(path: str) -> str:
        return f"/theme-static/{theme.name}/{path}"

    return _build
