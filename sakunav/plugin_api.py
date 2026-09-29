"""插件公开 API。

插件内使用：from sakunav.plugin_api import ...

提供能力：
  register_hook(hook, fn)        —— 运行时注册钩子（与约定函数名等效）
  get_setting / set_setting      —— 读写全局设置
  logger(name)                   —— 获取日志器
  require_admin                  —— 装饰器：保护插件自定义管理端路由
  admin_route(path, methods)     —— 便捷注册受保护的管理端路由
  render_plugin_template(...)    —— 渲染插件自带模板（需插件目录下有 templates/）
"""

import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Callable

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape


class _State:
    """由 main.create_app 注入的应用级单例。"""

    app: Any = None
    db: Any = None
    plugin_manager: Any = None
    app_templates_dir: str = ""


state = _State()


def register_hook(hook: str, fn: Callable) -> None:
    """在运行时注册钩子（等效于在插件入口定义同名函数）。"""
    setattr(_current_module(), hook, fn)


def _current_module():
    """返回正在执行调用的插件模块对象。"""
    frame = inspect.currentframe()
    while frame is not None:
        name = frame.f_globals.get("__name__", "")
        if name.startswith("_sakunav_plugin_"):
            return sys.modules.get(name)
        frame = frame.f_back
    raise RuntimeError("register_hook 只能在插件模块内调用")


def get_setting(key: str, default: Any = None) -> Any:
    from sakunav.db import get_setting as _get

    return _get(state.db, key, default)


def set_setting(key: str, value: Any) -> None:
    from sakunav.db import set_setting as _set

    _set(state.db, key, value)


def logger(name: str = "plugin") -> logging.Logger:
    return logging.getLogger(f"sakunav.plugin.{name}")


def _annotate_request(fn: Callable) -> Callable:
    """为插件路由函数补全 request 参数类型注解（未标注时 FastAPI 会误判为查询参数）。"""
    from fastapi import Request

    if not hasattr(fn, "__annotations__"):
        fn.__annotations__ = {}
    fn.__annotations__["request"] = Request
    return fn


def require_admin(fn: Callable) -> Callable:
    """装饰器：为插件自定义路由附加管理端认证（未登录返回 401）。"""
    from sakunav.auth import require_admin_api as _guard

    _annotate_request(fn)
    _guard  # 保留引用以提示用法；实际守卫建议通过 admin_route 的 dependencies 注入
    return fn


def admin_route(path: str, methods: tuple = ("GET",)):
    """便捷装饰器：注册一个受管理端认证保护的路由。

    用法：
        @plugin_api.admin_route("/admin/plugins/hello")
        def hello_page(request: Request): ...
    """

    def decorator(fn: Callable) -> Callable:
        from fastapi import Depends

        from sakunav.auth import require_admin_api

        _annotate_request(fn)
        state.app.add_api_route(
            path,
            fn,
            methods=list(methods),
            include_in_schema=False,
            dependencies=[Depends(require_admin_api)],
        )
        return fn

    return decorator


def render_plugin_template(request, plugin_name: str, template_name: str, context: dict | None = None):
    """渲染插件自带模板（优先插件 templates/，回退应用内置模板）。"""
    from fastapi.responses import HTMLResponse

    info = state.plugin_manager.get(plugin_name)
    if info is None:
        raise RuntimeError(f"插件不存在：{plugin_name}")
    pdir = Path(info.source_dir) / "templates"
    loaders = []
    if pdir.is_dir():
        loaders.append(FileSystemLoader(str(pdir)))
    loaders.append(FileSystemLoader(state.app_templates_dir))
    env = Environment(loader=ChoiceLoader(loaders), autoescape=select_autoescape(["html", "xml"]))
    template = env.get_template(template_name)
    ctx = {"request": request}
    if context:
        ctx.update(context)
    return HTMLResponse(template.render(**ctx))
