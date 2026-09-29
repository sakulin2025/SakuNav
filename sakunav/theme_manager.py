"""主题包管理器。

主题即一个目录，结构约定：
  theme.toml            —— 元信息（name/version/description/author/color_scheme）
  templates/index.html  —— 首页模板（可 extends 应用内置的 theme_base.html）
  static/               —— 静态资源（style.css / main.js / favicon.svg 等）

内置主题位于 SAKUNAV_THEMES_DIR（随镜像分发）；
用户上传/放置的主题位于 SAKUNAV_EXTRA_THEMES_DIR（挂载卷，重启不丢失）。
同名时内置主题优先。
"""

import re
import shutil
import tomllib
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MANIFEST = "theme.toml"


@dataclass
class ThemeInfo:
    name: str
    version: str
    description: str
    author: str
    color_scheme: str
    builtin: bool
    source_dir: str


class ThemeManager:
    def __init__(self, themes_dir: Path, extra_dir: Path) -> None:
        self.themes_dir = Path(themes_dir)
        self.extra_dir = Path(extra_dir)
        self._cache: Optional[dict[str, ThemeInfo]] = None

    # ---------------- 发现 ----------------

    def discover(self) -> list[ThemeInfo]:
        found: dict[str, ThemeInfo] = {}
        for base, builtin in ((self.themes_dir, True), (self.extra_dir, False)):
            if not base.exists():
                continue
            for child in sorted(base.iterdir()):
                if not child.is_dir() or not _NAME_RE.match(child.name):
                    continue
                info = self._read_manifest(child, builtin)
                if info is None or info.name in found:
                    continue
                found[info.name] = info
        self._cache = found
        return list(found.values())

    def _read_manifest(self, dir_path: Path, builtin: bool) -> Optional[ThemeInfo]:
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
        return ThemeInfo(
            name=name,
            version=str(meta.get("version", "0.0.0")),
            description=str(meta.get("description", "")),
            author=str(meta.get("author", "")),
            color_scheme=str(meta.get("color_scheme", "light")),
            builtin=builtin,
            source_dir=str(dir_path),
        )

    def get(self, name: str) -> Optional[ThemeInfo]:
        if self._cache is None:
            self.discover()
        return self._cache.get(name) if self._cache else None

    def active(self, active_name: str) -> ThemeInfo:
        theme = self.get(active_name)
        if theme is None:
            theme = self.get("default")
        if theme is None:
            themes = self.discover()
            theme = themes[0] if themes else None
        if theme is None:
            raise RuntimeError("未发现任何可用主题")
        return theme

    def template_dir(self, theme: ThemeInfo) -> Path:
        return Path(theme.source_dir) / "templates"

    def static_dir(self, theme: ThemeInfo) -> Path:
        return Path(theme.source_dir) / "static"

    # ---------------- 安装 / 删除 ----------------

    def install_zip(self, data: bytes) -> ThemeInfo:
        """安全解压主题 zip 包。

        校验项：合法 zip、顶层目录名合法、包含 theme.toml、
        拒绝绝对路径 / 路径穿越 / 空字节，解压后再校验清单。
        """
        try:
            zf = zipfile.ZipFile(BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise ValueError("不是有效的 zip 文件") from exc
        names = zf.namelist()
        if not names:
            raise ValueError("zip 包为空")

        top = names[0].split("/")[0]
        if not _NAME_RE.match(top):
            raise ValueError(f"主题目录名非法：{top!r}")
        if f"{top}/{_MANIFEST}" not in names:
            raise ValueError("主题包缺少 theme.toml")

        target_dir = self.extra_dir / top
        if target_dir.exists():
            raise ValueError(f"主题 {top} 已存在，请先删除再上传")

        for info in zf.infolist():
            name = info.filename
            if name.startswith("/") or "\x00" in name or ".." in Path(name).parts:
                raise ValueError(f"存在非法路径条目：{name!r}")
            if info.is_dir():
                continue
            target = (self.extra_dir / name).resolve()
            if not target.is_relative_to(self.extra_dir.resolve()):
                raise ValueError(f"存在越界路径条目：{name!r}")

        try:
            zf.extractall(self.extra_dir)
        except Exception as exc:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise ValueError(f"主题解压失败：{exc}") from exc

        theme = self._read_manifest(target_dir, builtin=False)
        if theme is None:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise ValueError("主题包缺少合法的 theme.toml")
        self.discover()
        return theme

    def remove(self, name: str) -> bool:
        theme = self.get(name)
        if theme is None or theme.builtin:
            return False
        shutil.rmtree(Path(theme.source_dir), ignore_errors=True)
        self.discover()
        return True
