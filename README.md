# SakuNav

轻量、容器化、可自托管的私有云书签导航页（OneNav 风格）。

用 Docker 一键部署到你的私有云 / NAS / 内网服务器，即可拥有一个干净、快速、可自定义的导航首页：
按分类管理常用链接、即时搜索、明亮/暗色主题切换、上传自定义主题包、启用插件扩展能力。

## 特性

- **用户界面（公开导航页）**
  - 分类卡片式布局，链接自动生成首字母色块图标（或自定义图标）
  - 客户端即时搜索（标题 / 地址 / 描述），零请求零延迟
  - 站点名称、描述、Logo、页脚均可自定义；支持公开访问或私有模式
- **管理面板**
  - 链接 / 分类的增删改查，一键上移下移排序
  - 主题管理：切换、上传（zip 主题包）、删除用户主题
  - 插件管理：启用 / 停用，插件可扩展管理端侧边栏与页面
  - 站点设置：公开模式、搜索开关、默认打开方式、修改管理员密码
- **自定义主题包**
  - 主题 = 目录包：`theme.toml` 元信息 + `templates/index.html` 模板 + `static/` 静态资源
  - 可完全自定义页面结构与视觉，内置 `default`（明亮）与 `dark`（暗色）两套参考实现
  - 用户主题存放在数据卷，重建容器不丢失
- **插件扩展控制**
  - 插件 = 目录包：`plugin.toml` + 入口 `main.py`
  - 10 种钩子：页面数据注入、页头/页脚 HTML 注入、链接过滤、增删改事件、设置变更事件、管理端导航/路由
  - 管理面板可视化启停，内置 `hello`、`links-counter` 两个示例插件
- **轻量化**
  - 技术栈：Python 3.11 + FastAPI + SQLite + Jinja2 + 原生 JS/CSS，**无前端构建步骤、无 Node 依赖**
  - 单容器部署，镜像约 **240MB**（`python:3.11-slim` 基础，压缩层约 50MB），运行时内存占用 < 60MB
  - SQLite 单文件存储，备份 = 复制一个文件

## 快速开始（Docker）

```bash
# 1. 构建镜像
docker build -t sakunav:latest .

# 2. 启动（默认端口 8080，数据持久化到 ./data）
docker run -d --name sakunav -p 8080:8000 \
  -e SAKUNAV_ADMIN_USERNAME=admin \
  -e SAKUNAV_ADMIN_PASSWORD=你的强密码 \
  -v "$(pwd)/data:/app/data" \
  --restart unless-stopped \
  sakunav:latest

# 3. 打开
#   导航页  http://<服务器IP>:8080/
#   管理面板 http://<服务器IP>:8080/admin
```

或使用 docker compose：

```bash
docker compose up -d --build
```

> 未设置 `SAKUNAV_ADMIN_PASSWORD` 时，首次启动会自动生成随机密码并打印到日志：
> `docker logs sakunav` 中查找「随机密码」。

## 本地开发

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -e ".[dev]"
.venv/bin/python -m sakunav        # http://127.0.0.1:8000
.venv/bin/python -m pytest tests   # 运行测试
```

## 目录结构

```
SakuNav/
├── sakunav/                  # 应用源码（Python 包）
│   ├── main.py               # 应用工厂
│   ├── config.py             # 环境变量配置
│   ├── db.py / repos.py      # SQLite 数据层与仓储
│   ├── auth.py / security.py # 认证 / 密码 / CSRF
│   ├── theme_manager.py      # 主题包管理
│   ├── plugin_manager.py     # 插件与钩子系统
│   ├── plugin_api.py         # 插件公开 API
│   ├── context.py            # 模板上下文装配
│   ├── routes/               # public / admin / api 路由
│   ├── templates/            # 管理端模板 + 主题基座
│   └── static/               # 管理端静态资源
├── themes/                   # 内置主题（default / dark）
├── plugins/                  # 内置插件（hello / links-counter）
├── docs/                     # 文档
│   ├── architecture.md       # 架构设计
│   ├── deployment.md         # 部署运维
│   ├── theme-development.md  # 主题开发
│   ├── plugin-development.md # 插件开发
│   └── api.md                # REST API
├── tests/                    # pytest 测试
├── Dockerfile                # 镜像构建
├── docker-compose.yml        # 单容器编排
└── requirements.txt          # Python 依赖（仅 4 个）
```

## 文档

| 文档 | 内容 |
|---|---|
| [docs/architecture.md](docs/architecture.md) | 总体架构、模块划分、数据模型、请求流程、安全设计 |
| [docs/deployment.md](docs/deployment.md) | Docker 部署、反向代理 / HTTPS、备份迁移、环境变量表、FAQ |
| [docs/theme-development.md](docs/theme-development.md) | 主题包结构、模板上下文、CSS 变量、打包上传 |
| [docs/plugin-development.md](docs/plugin-development.md) | 插件结构、10 种钩子、plugin_api 用法、示例拆解 |
| [docs/api.md](docs/api.md) | 公开 / 管理 REST API 说明 |

## 许可证

MIT
