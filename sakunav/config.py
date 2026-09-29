"""全局配置。

所有配置项均可通过环境变量注入（SAKUNAV_* 前缀），默认值适配 Docker 与本地开发。
参见 docs/deployment.md 中的环境变量表。
"""

import os
import secrets
from pathlib import Path


def _env_bool(key: str, default: bool) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent

        # 应用
        self.app_name = os.getenv("SAKUNAV_APP_NAME", "SakuNav")
        self.version = "1.0.0"

        # 服务
        self.host = os.getenv("SAKUNAV_HOST", "0.0.0.0")
        self.port = int(os.getenv("SAKUNAV_PORT", "8000"))
        self.log_level = os.getenv("SAKUNAV_LOG_LEVEL", "info")
        self.trusted_hosts = [
            h.strip() for h in os.getenv("SAKUNAV_TRUSTED_HOSTS", "*").split(",") if h.strip()
        ]

        # 会话
        self.secret_key = os.getenv("SAKUNAV_SECRET_KEY", "").strip()
        self.session_cookie = "sakunav_session"
        self.https_only = _env_bool("SAKUNAV_HTTPS_ONLY", False)

        # 数据与扩展目录
        self.data_dir = Path(os.getenv("SAKUNAV_DATA_DIR", str(self.base_dir / "data")))
        self.db_path = Path(os.getenv("SAKUNAV_DB_PATH", str(self.data_dir / "sakunav.db")))
        self.themes_dir = Path(os.getenv("SAKUNAV_THEMES_DIR", str(self.base_dir / "themes")))
        self.plugins_dir = Path(os.getenv("SAKUNAV_PLUGINS_DIR", str(self.base_dir / "plugins")))
        # 用户扩展目录（挂载卷，跨容器重启持久化；优先级低于内置目录）
        self.extra_themes_dir = Path(
            os.getenv("SAKUNAV_EXTRA_THEMES_DIR", str(self.data_dir / "themes"))
        )
        self.extra_plugins_dir = Path(
            os.getenv("SAKUNAV_EXTRA_PLUGINS_DIR", str(self.data_dir / "plugins"))
        )

        # 上传限制（主题 zip 包），默认 8MB
        self.max_upload_size = int(os.getenv("SAKUNAV_MAX_UPLOAD_SIZE", str(8 * 1024 * 1024)))

        # 首次启动创建管理员所用凭据
        self.admin_username = os.getenv("SAKUNAV_ADMIN_USERNAME", "").strip()
        self.admin_password = os.getenv("SAKUNAV_ADMIN_PASSWORD", "").strip()

    def ensure_dirs(self) -> None:
        """确保所有运行时目录存在。"""
        for d in (
            self.data_dir,
            self.db_path.parent,
            self.themes_dir,
            self.plugins_dir,
            self.extra_themes_dir,
            self.extra_plugins_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def get_secret_key(self) -> str:
        """返回会话签名密钥。

        未通过环境变量指定时，自动生成并持久化到 data/secret.key，
        保证容器重启后会话不失效。
        """
        if self.secret_key:
            return self.secret_key
        key_file = self.data_dir / "secret.key"
        if key_file.exists():
            return key_file.read_text(encoding="utf-8").strip()
        key = secrets.token_hex(32)
        key_file.write_text(key, encoding="utf-8")
        return key
