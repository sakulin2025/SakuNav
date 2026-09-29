# 部署运维指南

## 1. 构建镜像

```bash
docker build -t sakunav:latest .
```

镜像基于 `python:3.11-slim`，约 180MB。构建产物仅含应用源码、内置主题与内置插件，不含测试与文档。

## 2. 单容器部署

### docker run

```bash
docker run -d --name sakunav \
  -p 8080:8000 \
  -e SAKUNAV_ADMIN_USERNAME=admin \
  -e SAKUNAV_ADMIN_PASSWORD=请改成强密码 \
  -e SAKUNAV_SECRET_KEY=请用下方命令生成 \
  -v "$(pwd)/data:/app/data" \
  --restart unless-stopped \
  sakunav:latest
```

### docker compose（推荐）

```bash
docker compose up -d --build
```

`docker-compose.yml` 已配置端口映射（8080）、数据卷与重启策略；请先修改其中的管理员密码。

### 健康检查

镜像内置 HEALTHCHECK（每 30s 请求 `/api/health`）。手动验证：

```bash
curl http://127.0.0.1:8080/api/health
# {"status":"ok","app":"SakuNav v1.0.0","version":"1.0.0"}
```

## 3. 首次启动与管理员账号

- 启动时若数据库中尚无管理员，将按以下顺序创建：
  1. 环境变量 `SAKUNAV_ADMIN_USERNAME` / `SAKUNAV_ADMIN_PASSWORD`；
  2. 未配置密码时自动生成随机密码，打印到日志（`docker logs sakunav` 搜索「随机密码」）。
- 账号创建后，修改密码请到「管理面板 → 设置」，环境变量不再生效。
- 忘记密码：`docker exec sakunav python -m sakunav.cli reset-password --password 新密码`

## 4. 环境变量表

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SAKUNAV_HOST` | `0.0.0.0` | 监听地址 |
| `SAKUNAV_PORT` | `8000` | 监听端口 |
| `SAKUNAV_DATA_DIR` | `/app/data` | 数据卷根目录（数据库、用户扩展、密钥） |
| `SAKUNAV_DB_PATH` | `<DATA_DIR>/sakunav.db` | SQLite 数据库路径 |
| `SAKUNAV_THEMES_DIR` | `/app/themes` | 内置主题目录（只读） |
| `SAKUNAV_PLUGINS_DIR` | `/app/plugins` | 内置插件目录（只读） |
| `SAKUNAV_EXTRA_THEMES_DIR` | `<DATA_DIR>/themes` | 用户主题目录（上传主题存放处） |
| `SAKUNAV_EXTRA_PLUGINS_DIR` | `<DATA_DIR>/plugins` | 用户插件目录 |
| `SAKUNAV_SECRET_KEY` | 自动生成并持久化 | 会话签名密钥；生成：`docker run --rm sakunav python -m sakunav.cli generate-secret` |
| `SAKUNAV_ADMIN_USERNAME` | `admin` | 首次创建管理员用 |
| `SAKUNAV_ADMIN_PASSWORD` | 自动生成 | 首次创建管理员用 |
| `SAKUNAV_HTTPS_ONLY` | `false` | HTTPS 反向代理对外时设 `true` |
| `SAKUNAV_TRUSTED_HOSTS` | `*` | Host 白名单（逗号分隔），代理场景建议设置 |
| `SAKUNAV_MAX_UPLOAD_SIZE` | `8388608` | 主题包上传上限（字节） |
| `SAKUNAV_LOG_LEVEL` | `info` | 日志级别 |

## 5. 反向代理与 HTTPS

以 Caddy 为例：

```
sakunav.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Nginx：

```nginx
server {
    listen 443 ssl;
    server_name sakunav.example.com;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

HTTPS 生效后，将 `SAKUNAV_HTTPS_ONLY=true` 以保证会话 Cookie 仅通过 HTTPS 传输。

## 6. 数据备份与迁移

数据全部位于数据卷 `/app/data`：

```
data/
├── sakunav.db         # SQLite 数据库（所有书签与设置）
├── secret.key         # 会话签名密钥（备份需一并保留，否则会话失效）
├── themes/            # 用户上传的主题
└── plugins/           # 用户安装的插件
```

备份：

```bash
docker exec sakunav sh -c 'cd /app/data && tar czf /tmp/backup.tgz .'
docker cp sakunav:/tmp/backup.tgz ./sakunav-backup.tgz
```

恢复：解压到新实例的数据卷对应目录，重启即可。迁移到其他机器同理（只需迁移 `data/` 目录）。

## 7. 升级

```bash
docker compose down
# 拉取新镜像 / 重新构建
docker compose up -d --build
```

数据卷内容自动保留；升级前建议先备份。

## 8. 常见问题（FAQ）

**Q：首次启动日志里的随机密码在哪里看？**
`docker logs sakunav 2>&1 | grep 随机密码`。

**Q：如何安装用户插件？**
将插件目录放入数据卷 `data/plugins/<插件名>/`（含 `plugin.toml` 与 `main.py`），重启容器后在「管理面板 → 插件」启用。

**Q：上传主题提示「主题已存在」？**
同名用户主题已存在，先删除旧主题再上传；内置主题同名时优先，不能通过上传覆盖内置主题。

**Q：私有模式下所有人访问 `/` 都被要求登录？**
是的。`site.public_access=false` 时导航页需登录浏览；管理面板始终需要登录。

**Q：容器重启后会话失效？**
若未显式设置 `SAKUNAV_SECRET_KEY`，密钥自动生成并保存在数据卷 `secret.key`，重启不失效；但备份/迁移时必须连同该文件一起备份。

**Q：端口如何修改？**
改 `docker-compose.yml` 的端口映射（宿主机端口:8000），或运行时用 `-e SAKUNAV_PORT=xxxx`。
