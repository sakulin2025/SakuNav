"""links-counter 示例插件。

演示数据类钩子：
1. on_link_create / on_link_update / on_link_delete —— 链接增删改时更新计数；
2. page_data —— 向公开导航页上下文注入统计数据；
3. footer_html —— 在页脚展示「已收录 N 条链接」。

计数持久化在全局设置 links_counter.total 中。
"""

from sakunav import plugin_api

KEY = "links_counter.total"


def _get_total():
    return int(plugin_api.get_setting(KEY, 0) or 0)


def on_link_create(link):
    plugin_api.set_setting(KEY, _get_total() + 1)


def on_link_update(link):
    pass  # 计数不变；演示保留钩子但无需处理


def on_link_delete(link_id):
    plugin_api.set_setting(KEY, max(0, _get_total() - 1))


def page_data(data, context):
    """向模板上下文注入插件数据（模板中可用 {{ plugin_links_total }}）。"""
    data["plugin_links_total"] = _get_total()


def footer_html(context):
    total = _get_total()
    if total <= 0:
        return None
    return (
        '<span class="plugin-counter" style="font-size:12.5px;color:var(--text-muted);">'
        f'已收录 {total} 条链接（由 links-counter 统计）</span>'
    )
