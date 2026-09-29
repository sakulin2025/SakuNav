# 架构设计

## 1. 总体架构

SakuNav 是一个「服务端渲染 + 轻量 API」的单容器应用，部署形态为一个 Docker 镜像 + 一个数据卷。

```
┌────────────────────────────── 浏览器 ──────────────────────────────┐
│  公开导航页（主题渲染）   ·   管理面板（服务端渲染表单）   ·   JSON API  │
└──────────────┬──────────────────────────────┬──────────────────────┘
               │ HTTP                          │ HTTP
┌──────────────▼──────────────────────────────▼──────────────────────┐
│                          FastAPI 应用（uvicorn）                    │
│  ┌────────────┐  ┌─────────────┐  ┌───────────────────────────┐    │
│  │ 公开路由    │  │ 管理路由     │  │ 管理 JSON API              │    │
│  │ /          │  │ /login      │  │ /api/links · /api/themes … │    │
│  │ /api/health│  │ /admin/*    │  │ （全部要求管理员会话）         │    │
│  └─────┬──────┘  └──────┬──────┘  └────────────┬──────────────┘    │
│        │                │                      │                    │
│  ┌─────▼────────────────▼──────────────────────▼─────┐              │
│  │ 领域服务层                                          │              │
│  │  ThemeManager（主题发现/激活/安装）                   │              │
│  │  PluginManager（插件加载/钩子调度/路由注册）            │              │
│  │  repos（分类/链接仓储）  ·  auth（会话守卫）            │              │
│  └─────┬──────────────────────────┬───────────────────┘              │
│        │                          │                                  │
│  ┌─────▼─────┐           ┌────────▼────────┐                        │
│  │ SQLite    │           │ 模板引擎 Jinja2  │                        │
│  │ 单文件 WAL │           │ 管理端模板       │                        │
│  └───────────┘           │ 主题模板(独立env)│                        │
│                          └──────────────────┘                        │
└──────────────────────────────────────────────────────────────────────┘
  镜像内（只读）: themes/ · plugins/ · sakunav/static
  数据卷（可写）: data/sakunav.db · data/themes(用户主题) · data/plugins(用户插件) · data/secret.key
```

关键设计决策：

- **服务端渲染**：公开导航页与管理面板均由 Jinja2 在服务端渲染，前端只有「搜索过滤」一个原生 JS 脚本。无 SPA、无构建步骤，首屏渲染快，资源占用极低。
- **SQLite + 每请求独立连接**：单文件数据库，WAL 模式，`busy_timeout` 防并发写冲突；每个请求独立开连接提交，天然线程安全。
- **主题/插件双目录**：内置扩展随镜像分发（只读），用户扩展放数据卷（可写、跨重启持久）。同名时内置优先，避免被误覆盖。

## 2. 模块划分

| 模块 | 职责 |
|---|---|
| `config.py` | 全部配置由 `SAKUNAV_*` 环境变量注入，含目录、密钥、管理员引导参数 |
| `db.py` | SQLite 连接与会话管理、建表、设置项（JSON）读写 |
| `repos.py` | 分类/链接的仓储函数：增删改查、排序交换、统计 |
| `security.py` | PBKDF2 密码哈希、会话绑定的 CSRF 令牌 |
| `auth.py` | 登录态判断、页面级（303 跳转）/ API 级（401）守卫 |
| `theme_manager.py` | 主题发现、激活、zip 安全安装、删除 |
| `plugin_manager.py` | 插件发现、启停、独立模块加载、10 种钩子调度 |
| `plugin_api.py` | 暴露给插件的稳定 API（钩子注册、设置读写、受保护路由、模板渲染） |
| `context.py` | 标准上下文（站点设置 + CSRF + 插件注入）+ 主题页渲染 |
| `routes/public.py` | `/` 导航页、`/api/health`、公开只读 JSON |
| `routes/admin.py` | 登录/登出、管理面板全部表单页 |
| `routes/api.py` | 管理端 REST API（与表单共享仓储层） |
| `main.py` | 应用工厂：装配中间件、模板、路由、加载插件 |

## 3. 数据模型

```sql
categories(id, name UNIQUE, icon, sort_order, created_at, updated_at)
links(id, category_id → categories ON DELETE CASCADE, title, url,
      description, icon, color, sort_order, target, created_at, updated_at)
settings(key PRIMARY KEY, value)          -- value 为 JSON 文本
```

- 删除分类时级联删除其下链接（删除前会先通知插件，见 `routes/admin.py`）。
- `sort_order` 用于排序；上移/下移通过交换相邻条目的 `sort_order` 实现。
- 关键设置项：`admin.username`、`admin.password_hash`、`theme.active`、
  `plugins.enabled`（JSON 数组）、`site.title`、`site.public_access`、`search.enabled`、`links.target_default`。

## 4. 请求流程

### 公开导航页 `/`

1. 检查 `site.public_access`；私有模式下未登录 → 303 到 `/login`。
2. `ThemeManager.active()` 解析当前主题；若主题缺失回退 `default`。
3. `context.public_page_context()`：读取分类与链接 → 计算图标（自定义 URL 或首字母色块）
   → 调用插件 `page_data` 钩子（可改上下文）→ 调用 `link_filter` 钩子（可整体替换分类数据）。
4. 用「主题独立 Jinja 环境」渲染 `templates/index.html`（主题模板可 `extends` 应用内置 `theme_base.html`）。
5. 返回 HTML。前端 `main.js` 提供即时搜索过滤。

### 管理操作（示例：新建链接）

1. `POST /admin/links` 携带表单 + CSRF 令牌。
2. `require_admin_page` 校验会话 → `require_csrf` 校验令牌。
3. 路由层校验（URL 协议白名单、分类存在性）→ `repos.create_link` 落库。
4. 调用插件 `on_link_create` 钩子 → flash 提示 → 303 回跳。

### 启动流程

1. `python -m sakunav` → `create_app()`。
2. 初始化目录 → 打开数据库建表 → 引导管理员（环境变量或自动生成）。
3. 装配中间件（会话、安全头、可选 Host 白名单）→ 挂载静态资源 → 注册业务路由。
4. `PluginManager.ensure_loaded()`：加载所有已启用插件并调用其 `register_routes(app)`。

## 5. 安全设计

| 威胁 | 对策 |
|---|---|
| 会话劫持 | 签名会话 Cookie（HMAC，`SAKUNAV_SECRET_KEY`），`SameSite=Lax`，`HttpOnly`；HTTPS 部署时设 `SAKUNAV_HTTPS_ONLY=true` |
| 密码泄露 | 明文不落库；PBKDF2-HMAC-SHA256（26 万次迭代）+ 随机盐 |
| CSRF | 所有写操作强制会话绑定令牌（表单字段 `csrf_token`） |
| XSS | Jinja2 自动转义（`autoescape=True`）；链接 URL 仅允许白名单协议（拦截 `javascript:` 等） |
| 开放重定向 | 登录回跳仅接受本站单斜杠路径；管理端回跳仅接受 `/admin/*` |
| 主题 zip 攻击 | 拒绝绝对路径 / 路径穿越 / 空字节；解压前校验清单，解压后校验 `theme.toml` 合法性 |
| 点击劫持 | `X-Frame-Options: DENY`、`X-Content-Type-Options: nosniff` |
| Host 头攻击 | 可选 `SAKUNAV_TRUSTED_HOSTS` 收紧（反向代理场景） |

**边界说明**：插件与主题均以管理员权限运行，属「可信扩展」；请只安装来源可信的插件/主题（见 `docs/plugin-development.md`）。

## 6. 扩展机制（钩子一览）

| 钩子 | 触发时机 | 返回值语义 |
|---|---|---|
| `register_routes(app)` | 启动时（启用插件的注册路由生效需重启） | 无 |
| `admin_nav()` | 渲染管理端侧边栏 | `[{"name","path","icon"}]` |
| `page_data(data, context)` | 渲染公开导航页前 | 修改 `data` 字典即可 |
| `head_html(context)` | 渲染公开导航页 | HTML 字符串（注入 `<head>`） |
| `footer_html(context)` | 渲染公开导航页 | HTML 字符串（注入页脚） |
| `link_filter(links, context)` | 渲染公开导航页前 | 返回 `list` 时整体替换分类数据 |
| `on_link_create(link)` / `on_link_update(link)` / `on_link_delete(link_id)` | 对应数据变更后 | 无 |
| `on_settings_update(settings)` | 设置保存后 | 无 |

## 7. 演进方向（Roadmap）

- 多用户与细粒度权限
- 链接可用性监控（可作为插件实现）
- 导入导出（浏览器书签 HTML / OPML）
- 分组/标签与拖拽排序
- 一键备份与数据迁移助手
