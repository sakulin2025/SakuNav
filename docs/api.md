# REST API 文档

除服务端渲染页面外，SakuNav 提供一组轻量 JSON API。
管理端 API 全部要求管理员会话（携带登录后的会话 Cookie，无 Cookie 时返回 401）。

## 约定

- 基础地址：`http://<host>:<port>`
- 管理端 API 前缀：`/api/*`（除下表标注「公开」外，均需登录）
- 错误格式：`{"detail": "…"}`
- 分页：暂不提供（个人导航页数据量小，一次性返回）

## 公开端点

### `GET /api/health`（公开）

健康检查。

```json
{"status": "ok", "app": "SakuNav v1.0.0", "version": "1.0.0"}
```

### `GET /api/links`（公开；私有模式下需登录）

查询参数：`category`（分类 ID，可选）、`search`（关键词，可选）。

```json
{"links": [{"id": 1, "category_id": 2, "title": "豆包", "url": "https://www.doubao.com", "description": "", "icon": "", "color": "", "sort_order": 0, "target": "_blank", "created_at": "…", "updated_at": "…"}]}
```

### `GET /api/categories`（公开；私有模式下需登录）

```json
{"categories": [{"id": 1, "name": "常用工具", "icon": "🧰", "link_count": 3}]}
```

### `GET /api/site`（公开；私有模式下需登录）

```json
{"site": {"title": "SakuNav", "description": "", "search_enabled": true}}
```

## 管理端 API

> 全部端点要求登录。请求体使用 JSON（`Content-Type: application/json`）。

### 链接

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/links` | 列表（同上，登录后可见全部） |
| POST | `/api/links` | 新建，返回链接对象 |
| PUT | `/api/links/{id}` | 更新，返回链接对象 |
| DELETE | `/api/links/{id}` | 删除（204） |
| POST | `/api/links/{id}/move` | 排序移动，query 参数 `direction=up|down` |

新建/更新请求体：

```json
{
  "category_id": 1,
  "title": "豆包",
  "url": "https://www.doubao.com",
  "description": "",
  "icon": "",
  "color": "#4f46e5",
  "target": "_blank"
}
```

校验：URL 仅允许 `http/https/ftp/ftps/mailto/tel/magnet` 协议；分类必须存在；`target` 仅 `_blank/_self`。

### 分类

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/categories` | 列表（含 link_count） |
| POST | `/api/categories` | 新建（名称唯一，409 冲突） |
| PUT | `/api/categories/{id}` | 更新 |
| DELETE | `/api/categories/{id}` | 删除（级联删除链接，204） |
| POST | `/api/categories/{id}/move` | 排序移动，query 参数 `direction=up|down` |

请求体：`{"name": "常用工具", "icon": "🧰"}`

### 设置

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/settings` | 全部设置（扁平键值） |
| PUT | `/api/settings` | 批量更新：`{"site.title": "…", "site.public_access": false, …}` |

常用键：`site.title`、`site.description`、`site.logo`、`site.footer`、
`site.public_access`（布尔）、`search.enabled`（布尔）、`links.target_default`、`theme.active`。

### 主题

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/themes` | 主题列表 + 当前激活主题 |
| POST | `/api/themes/activate` | 激活主题：`{"name": "dark"}` |

### 插件

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/plugins` | 插件列表（含 enabled 状态） |
| POST | `/api/plugins/{name}/toggle` | 启停：`{"enabled": true}` |

### 密码

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/password` | 修改管理员密码：`{"current": "旧密码", "new": "新密码(≥8位)"}` |

## 调用示例

```bash
# 登录（保存会话 Cookie）
curl -c cookies.txt -X POST http://host:8080/login \
  -d "csrf_token=<从登录页获取>&username=admin&password=你的密码"

# 新建链接
curl -b cookies.txt -X POST http://host:8080/api/links \
  -H "Content-Type: application/json" \
  -d '{"category_id":1,"title":"豆包","url":"https://www.doubao.com"}'

# 激活暗色主题
curl -b cookies.txt -X POST http://host:8080/api/themes/activate \
  -H "Content-Type: application/json" -d '{"name":"dark"}'
```

> 说明：登录端点使用会话绑定 CSRF 令牌（表单字段 `csrf_token`），
> 令牌可从 `GET /login` 页面 HTML 的隐藏字段中读取，同一会话内保持不变。
