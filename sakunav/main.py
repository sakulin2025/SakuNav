"""应用工厂：装配配置、数据库、主题、插件、模板与路由。"""

import logging
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sakunav import __version__
from sakunav import plugin_api
from sakunav.config import Settings
from sakunav.db import Database, get_setting, set_setting
from sakunav.plugin_manager import PluginManager
from sakunav.security import hash_password
from sakunav.theme_manager import ThemeManager

logger = logging.getLogger("sakunav")


def _init_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _bootstrap_admin(db: Database, settings: Settings) -> None:
    """首次启动时创建管理员账号。

    优先使用环境变量 SAKUNAV_ADMIN_USERNAME / SAKUNAV_ADMIN_PASSWORD；
    未配置密码时自动生成随机密码并打印到日志（Docker 下可用 docker logs 查看）。
    """
    if get_setting(db, "admin.username") is not None:
        return
    username = settings.admin_username or "admin"
    password = settings.admin_password
    generated = False
    if not password:
        password = secrets.token_urlsafe(10)
        generated = True
    set_setting(db, "admin.username", username)
    set_setting(db, "admin.password_hash", hash_password(password))
    if generated:
        logger.warning("==== 首次启动，未配置 SAKUNAV_ADMIN_PASSWORD ====")
        logger.warning("管理员账号：%s / 随机密码：%s（请登录后立即修改）", username, password)
    else:
        logger.info("管理员账号已创建：%s", username)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    _init_logging(settings.log_level)
    settings.ensure_dirs()

    db = Database(settings.db_path)
    _bootstrap_admin(db, settings)

    theme_manager = ThemeManager(settings.themes_dir, settings.extra_themes_dir)
    theme_manager.discover()
    plugin_manager = PluginManager(settings.plugins_dir, settings.extra_plugins_dir, db)
    plugin_manager.discover()

    app = FastAPI(
        title=f"{settings.app_name} v{__version__}",
        version=__version__,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.theme_manager = theme_manager
    app.state.plugin_manager = plugin_manager
    app.state.theme_envs: dict = {}

    # 会话中间件：签名 Cookie + SameSite=Lax
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.get_secret_key(),
        session_cookie=settings.session_cookie,
        max_age=60 * 60 * 24 * 7,
        same_site="lax",
        https_only=settings.https_only,
    )
    # 反向代理场景下可收紧 Host 校验
    if settings.trusted_hosts and settings.trusted_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

    # 安全响应头
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    # 模板（管理端页面 + 主题回退基座）
    app_dir = Path(__file__).resolve().parent
    app_templates_dir = app_dir / "templates"
    app.state.app_templates_dir = str(app_templates_dir)
    app.state.jinja_env = Environment(
        loader=FileSystemLoader(str(app_templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        auto_reload=True,
    )

    # 静态资源
    app.mount("/static", StaticFiles(directory=str(app_dir / "static")), name="static")

    # 注入插件运行时
    plugin_api.state.app = app
    plugin_api.state.db = db
    plugin_api.state.plugin_manager = plugin_manager
    plugin_api.state.app_templates_dir = str(app_templates_dir)

    # 路由（先挂载业务路由，再让插件注册自己的路由）
    from sakunav.routes import admin as admin_routes
    from sakunav.routes import api as api_routes
    from sakunav.routes import public as public_routes

    app.include_router(public_routes.router)
    app.include_router(admin_routes.router)
    app.include_router(api_routes.router)

    # 主题静态资源路由
    @app.get("/theme-static/{name}/{path:path}")
    def theme_static(name: str, path: str, request: Request):
        theme = request.app.state.theme_manager.get(name)
        if theme is None:
            raise HTTPException(status_code=404, detail="主题不存在")
        base = (Path(theme.source_dir) / "static").resolve()
        target = (base / path).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            raise HTTPException(status_code=404, detail="资源不存在")
        return FileResponse(target)

    # 加载启用插件并注册其路由
    plugin_manager.app = app
    plugin_manager.ensure_loaded()

    return app
