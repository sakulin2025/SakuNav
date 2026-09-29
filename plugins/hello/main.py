"""hello 示例插件。

演示三种扩展方式：
1. 约定钩子函数 footer_html —— 向公开导航页页脚注入 HTML；
2. 约定钩子函数 admin_nav —— 在管理面板侧边栏新增入口；
3. 使用 plugin_api.admin_route —— 注册一个受管理员认证保护的自定义管理页。

启用方法：管理面板 → 插件 → 启用 hello。
"""

from sakunav import plugin_api


def footer_html(context):
    """向公开导航页页脚注入一行问候语。"""
    return '<div class="plugin-banner" style="text-align:center;font-size:12.5px;color:var(--text-muted);padding:8px 0;">由 hello 插件注入：欢迎使用 SakuNav ✦</div>'


def admin_nav():
    """在管理面板侧边栏追加一个入口。"""
    return [{"name": "Hello 示例", "path": "/admin/plugins/hello", "icon": "👋"}]


@plugin_api.admin_route("/admin/plugins/hello")
def hello_page(request):
    """自定义管理页：点击侧边栏「Hello 示例」进入。"""
    from fastapi.responses import HTMLResponse

    html = """
    <!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
    <title>Hello 插件</title>
    <link rel="stylesheet" href="/static/admin.css"></head>
    <body class="admin-body"><div class="admin-shell">
    <main class="admin-main">
      <h1>Hello 插件面板</h1>
      <div class="card">
        <h2>演示：插件自定义管理页</h2>
        <p>这个页面由 <code>plugins/hello/main.py</code> 注册，受管理员会话保护。</p>
        <p>插件读取设置示例：<code>hello.note</code> =
        <strong>""" + str(plugin_api.get_setting("hello.note", "未设置（可在下方写入）")) + """</strong></p>
        <form method="post" action="/admin/plugins/hello/save" style="display:flex;gap:10px;align-items:center;">
          <input type="text" name="note" placeholder="写入一条备注" style="padding:8px;border:1px solid var(--border);border-radius:8px;">
          <button class="btn btn-primary" type="submit">保存</button>
        </form>
      </div>
    </main></div></body></html>
    """
    return HTMLResponse(html)


@plugin_api.admin_route("/admin/plugins/hello/save", methods=("POST",))
async def hello_save(request):
    from fastapi.responses import RedirectResponse

    form = await request.form()
    plugin_api.set_setting("hello.note", str(form.get("note", "")))
    return RedirectResponse("/admin/plugins/hello", status_code=303)
