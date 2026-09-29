"""命令行工具：python -m sakunav.cli <command>

用法：
  python -m sakunav.cli create-admin [--username admin] [--password 密码]
  python -m sakunav.cli reset-password --password 新密码
  python -m sakunav.cli generate-secret
  python -m sakunav.cli status

说明：以上命令读取与运行时一致的环境变量（SAKUNAV_DB_PATH 等），
在容器内执行时可直接复用容器环境。
"""

import argparse
import secrets
import sys
from pathlib import Path

from sakunav.config import Settings
from sakunav.db import Database, get_setting, set_setting
from sakunav.security import hash_password


def _get_db() -> Database:
    settings = Settings()
    settings.ensure_dirs()
    return Database(settings.db_path)


def cmd_create_admin(args) -> None:
    db = _get_db()
    if get_setting(db, "admin.username") is not None:
        print("管理员已存在，如需改密请使用 reset-password 命令。")
        return
    password = args.password or secrets.token_urlsafe(10)
    set_setting(db, "admin.username", args.username)
    set_setting(db, "admin.password_hash", hash_password(password))
    print(f"管理员账号已创建：{args.username}")
    if not args.password:
        print(f"随机密码：{password}（请妥善保存）")


def cmd_reset_password(args) -> None:
    db = _get_db()
    if not args.password:
        print("请使用 --password 指定新密码。")
        sys.exit(1)
    if len(args.password) < 8:
        print("新密码长度至少 8 位。")
        sys.exit(1)
    set_setting(db, "admin.password_hash", hash_password(args.password))
    print("密码已重置。")


def cmd_generate_secret(args) -> None:
    print(secrets.token_hex(32))


def cmd_status(args) -> None:
    settings = Settings()
    db = _get_db()
    admin = get_setting(db, "admin.username")
    print(f"数据目录：{settings.data_dir}")
    print(f"数据库：  {settings.db_path}")
    print(f"管理员：  {admin or '未创建'}")
    print(f"主题目录：{settings.themes_dir}")
    print(f"插件目录：{settings.plugins_dir}")
    key_file = settings.data_dir / "secret.key"
    print(f"会话密钥：{'已持久化（' + str(key_file) + '）' if key_file.exists() else '未设置（首次启动自动生成）'}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="sakunav.cli", description="SakuNav 命令行工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("create-admin", help="创建管理员账号（仅首次）")
    p1.add_argument("--username", default="admin")
    p1.add_argument("--password", default="")
    p1.set_defaults(func=cmd_create_admin)

    p2 = sub.add_parser("reset-password", help="重置管理员密码")
    p2.add_argument("--password", required=True)
    p2.set_defaults(func=cmd_reset_password)

    p3 = sub.add_parser("generate-secret", help="生成会话签名密钥")
    p3.set_defaults(func=cmd_generate_secret)

    p4 = sub.add_parser("status", help="查看运行时状态")
    p4.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
