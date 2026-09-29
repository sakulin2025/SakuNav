"""插件系统。

插件即一个目录，结构约定：
  plugin.toml —— 元信息（name/version/description/author/entry）
  main.py     —— 插件入口（entry 字段指向的文件，默认 main.py）

插件通过「约定函数名」接入钩子，或调用 sakunav.plugin_api.register_hook 动态注册。
内置插件位于 SAKUNAV_PLUGINS_DIR；用户插件位于 SAKUNAV_EXTRA_PLUGINS_DIR（挂载卷）。
同名时内置插件优先。

注意事项：
- register_routes 只在应用启动时调用一次；启停涉及路由注册的插件后需重启生效；
- 其余数据类钩子在每次请求/事件时实时调用，启停即时生效；
- 插件代码以管理员权限运行，属「可信扩展」，请勿安装来源不明的插件。
"""

import importlib.util
import logging
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

from sakunav.db import Database, get_setting, set_setting

logger = logging.getLogger("sakunav.plugins")

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MANIFEST = "plugin.toml"

# 应用侧按顺序调用的钩子（约定函数名）
HOOKS = (
    "register_routes",      # register_routes(app) -> None           启动时注册路由
    "admin_nav",            # admin_nav() -> [{"name","path","icon"}] 管理端侧边栏
    "page_data",            # page_data(data, context) -> None/数据   修改公开页上下文
    "head_html",            # head_html(context) -> str|None         注入 <head>
    "footer_html",          # footer_html(context) -> str|None       注入页脚
    "link_filter",          # link_filter(links, context) -> list|None 过滤公开页链接
    "on_link_create",       # on_link_create(link: dict) -> None     链接创建后
    "on_link_update",       # on_link_update(link: dict) -> None     链接更新后
    "on_link_delete",       # on_link_delete(link_id: int) -> None   链接删除后
    "on_settings_update",   # on_settings_update(settings: dict) -> None 设置保存后
)


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str
    author: str
    entry: str
    builtin: bool
    enabled: bool
    source_dir: str


class PluginManager:
    def __init__(self, plugins_dir: Path, extra_dir: Path, db: Database) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.extra_dir = Path(extra_dir)
        self.db = db
        self.app: Any = None
        self._cache: dict[str, PluginInfo] = {}
        self._modules: dict[str, ModuleType] = {}

    # ---------------- 发现 ----------------

    def discover(self) -> list[PluginInfo]:
        found: dict[str, PluginInfo] = {}
        for base, builtin in ((self.plugins_dir, True), (self.extra_dir, False)):
            if not base.exists():
                continue
            for child in sorted(base.iterdir()):
                if not child.is_dir() or not _NAME_RE.match(child.name):
                    continue
                info = self._read_manifest(child, builtin)
                if info is None or info.name in found:
                    continue
                found[info.name] = info
        enabled = set(self.enabled_names())
        for info in found.values():
            info.enabled = info.name in enabled
        self._cache = found
        return list(found.values())

    def _read_manifest(self, dir_path: Path, builtin: bool) -> Optional[PluginInfo]:
        manifest = dir_path / _MANIFEST
        if not manifest.is_file():
            return None
        try:
            meta = tomllib.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            return None
        name = str(meta.get("name", dir_path.name))
        if not _NAME_RE.match(name):
            return None
        entry = str(meta.get("entry", "main.py"))
        return PluginInfo(
            name=name,
            version=str(meta.get("version", "0.0.0")),
            description=str(meta.get("description", "")),
            author=str(meta.get("author", "")),
            entry=entry,
            builtin=builtin,
            enabled=False,
            source_dir=str(dir_path),
        )

    def get(self, name: str) -> Optional[PluginInfo]:
        return self._cache.get(name)

    # ---------------- 启停 ----------------

    def enabled_names(self) -> list[str]:
        return list(get_setting(self.db, "plugins.enabled", []))

    def set_enabled(self, name: str, enabled: bool) -> bool:
        if self.get(name) is None:
            return False
        names = self.enabled_names()
        changed = False
        if enabled and name not in names:
            names.append(name)
            changed = True
        if not enabled and name in names:
            names.remove(name)
            changed = True
        if changed:
            set_setting(self.db, "plugins.enabled", names)
        self.unload(name)  # 卸载旧代码，下一次调用钩子时按新状态加载
        return changed

    # ---------------- 加载 / 卸载 ----------------

    def entry_path(self, info: PluginInfo) -> Path:
        return Path(info.source_dir) / info.entry

    def load(self, name: str) -> ModuleType:
        """以独立模块名加载插件入口，避免与现有模块冲突。"""
        info = self.get(name)
        if info is None:
            raise KeyError(f"插件不存在：{name}")
        if name in self._modules:
            return self._modules[name]
        entry = self.entry_path(info)
        if not entry.is_file():
            raise RuntimeError(f"插件 {name} 入口文件缺失：{entry}")
        mod_name = f"_sakunav_plugin_{name}"
        spec = importlib.util.spec_from_file_location(mod_name, entry)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"插件 {name} 无法加载")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(mod_name, None)
            raise
        self._modules[name] = module
        return module

    def unload(self, name: str) -> None:
        self._modules.pop(name, None)
        sys.modules.pop(f"_sakunav_plugin_{name}", None)

    def ensure_loaded(self) -> None:
        """应用启动时加载所有已启用插件，并调用其 register_routes 钩子。"""
        for name in self.enabled_names():
            if self.get(name) is None:
                logger.warning("插件 %s 已启用但不存在，已忽略", name)
                continue
            try:
                module = self.load(name)
                fn = getattr(module, "register_routes", None)
                if callable(fn):
                    fn(self.app)
            except Exception as exc:  # noqa: BLE001 —— 单个插件失败不影响整体启动
                logger.exception("插件 %s 加载失败：%s", name, exc)

    # ---------------- 钩子调度 ----------------

    def call_hook(self, hook: str, *args: Any, **kwargs: Any) -> list[Any]:
        """依次调用所有已启用插件中名为 hook 的函数，返回非空结果列表。

        约定：插件钩子函数要么返回 None（忽略），要么返回可消费的结果。
        """
        results: list[Any] = []
        for name in self.enabled_names():
            module = self._modules.get(name)
            if module is None:
                try:
                    module = self.load(name)
                except Exception as exc:
                    logger.warning("插件 %s 加载失败：%s", name, exc)
                    continue
            fn = getattr(module, hook, None)
            if not callable(fn):
                continue
            try:
                result = fn(*args, **kwargs)
                if result is not None:
                    results.append(result)
            except Exception as exc:  # noqa: BLE001 —— 单插件异常不拖垮页面
                logger.exception("插件 %s 的 %s 钩子执行失败：%s", name, hook, exc)
        return results
