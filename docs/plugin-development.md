# 插件开发指南

插件（Plugin）是 SakuNav 的扩展单位：一个目录 + 一个 Python 入口文件。
通过钩子（hook）在特定时机介入系统行为，可扩展导航页、管理面板与业务事件。

> ⚠️ **信任边界**：插件以管理员权限在应用进程内运行，可读写数据库与文件。
> 请只安装来源可信的插件；安装前建议通读其 `main.py`。

## 1. 插件包结构

```
my-plugin/
├── plugin.toml     # 元信息（必填）
├── main.py         # 入口（entry 字段指向的文件，默认 main.py）
└── templates/      # 可选：插件自带模板（配合 plugin_api.render_plugin_template 使用）
```

### plugin.toml

```toml
name = "my-plugin"        # 目录名一致，仅允许字母/数字/下划线/中划线
version = "1.0.0"
description = "我的第一个插件"
author = "Me"
entry = "main.py"         # 可省略，默认 main.py
```

## 2. 钩子（Hooks）

在 `main.py` 中定义与钩子同名的函数即可接入；也可以用 `plugin_api.register_hook` 动态注册。

### 完整钩子清单

| 钩子 | 签名 | 时机 | 返回值 |
|---|---|---|---|
| `register_routes` | `register_routes(app)` | 应用启动时（一次） | 无 |
| `admin_nav` | `admin_nav()` | 渲染管理端侧边栏 | `[{"name": str, "path": str, "icon": str}]` |
| `page_data` | `page_data(data, context)` | 渲染公开导航页前 | 修改 `data` 字典（可返回新数据或 None） |
| `head_html` | `head_html(context)` | 渲染公开导航页 | HTML 字符串（注入 `<head>`） |
| `footer_html` | `footer_html(context)` | 渲染公开导航页 | HTML 字符串（注入页脚） |
| `link_filter` | `link_filter(links, context)` | 渲染公开导航页前 | 返回 `list` 时整体替换分类数据 |
| `on_link_create` | `on_link_create(link: dict)` | 链接创建后 | 无 |
| `on_link_update` | `on_link_update(link: dict)` | 链接更新后 | 无 |
| `on_link_delete` | `on_link_delete(link_id: int)` | 链接删除后（含级联删除） | 无 |
| `on_settings_update` | `on_settings_update(settings: dict)` | 设置保存后 | 无 |

### 钩子调度规则

- 全部钩子按「启用状态」实时调度：启用后立即生效，停用后立即失效；
- **例外**：`register_routes` 只在应用启动时调用。注册了路由的插件，启用/停用后需重启容器才完全生效
  （管理面板在启用时会给出提示）；
- 单个插件钩子抛异常不影响其他插件与页面渲染，错误记录在日志（前缀 `sakunav.plugin`）。

## 3. 插件 API（`sakunav.plugin_api`）

```python
from sakunav import plugin_api

plugin_api.get_setting(key, default=None)          # 读全局设置
plugin_api.set_setting(key, value)                 # 写全局设置（JSON 持久化）
plugin_api.logger(name="my-plugin")                # 获取日志器
plugin_api.register_hook("footer_html", fn)        # 运行时注册钩子

# 自定义管理端路由
@plugin_api.admin_route("/admin/plugins/my", methods=("GET",))
def my_page(request): ...                          # 受管理员认证保护

# 渲染插件自带模板（需插件目录下有 templates/）
def some_handler(request):
    return plugin_api.render_plugin_template(request, "my-plugin", "panel.html", {"x": 1})
```

> 注意：`admin_route` 注册的路由已自动附加管理员会话校验，无需自行判断登录态。
> 插件路由的 `request` 参数类型为 `fastapi.Request`，可读取表单/JSON 等。

## 4. 完整示例：links-counter（数据类钩子）

```python
from sakunav import plugin_api

KEY = "links_counter.total"

def on_link_create(link):
    total = int(plugin_api.get_setting(KEY, 0) or 0)
    plugin_api.set_setting(KEY, total + 1)

def on_link_delete(link_id):
    total = int(plugin_api.get_setting(KEY, 0) or 0)
    plugin_api.set_setting(KEY, max(0, total - 1))

def page_data(data, context):
    data["plugin_links_total"] = int(plugin_api.get_setting(KEY, 0) or 0)

def footer_html(context):
    total = int(plugin_api.get_setting(KEY, 0) or 0)
    if total <= 0:
        return None
    return f'<span>已收录 {total} 条链接</span>'
```

## 5. 完整示例：hello（路由 + 管理端扩展）

见 `plugins/hello/main.py`，演示：

- `footer_html` 注入页脚横幅；
- `admin_nav` 在管理端侧边栏新增入口；
- `@plugin_api.admin_route("/admin/plugins/hello")` 注册受保护的自定义管理页；
- `plugin_api.get_setting / set_setting` 持久化插件数据。

## 6. 安装 / 启停

1. 将插件目录放到数据卷 `data/plugins/<插件名>/`（含 `plugin.toml` 与 `main.py`）；
2. `docker restart sakunav`（或本地重启服务）；
3. 管理面板 → 插件 → 找到插件 → 点击「启用插件」。

内置插件示例位于 `plugins/hello`、`plugins/links-counter`，可对照阅读。

## 7. 注意事项

- 插件内导入请使用 `sakunav.plugin_api` 等稳定 API；直接访问内部模块可能导致升级不兼容。
- `head_html` / `footer_html` 返回的 HTML 会被原样注入（已标记安全），
  请自行做好转义（如使用 `html.escape`）与可信来源控制。
- 插件可读写全局设置（`plugin_api.set_setting`），推荐使用独立命名空间前缀（如 `myplugin.xxx`）避免键冲突。
- 不要在插件中阻塞主线程（如同步网络请求耗时过长），否则会影响页面响应。
