# 主题包开发指南

主题（Theme）是 SakuNav 视觉与页面结构的扩展单位。一个主题就是一个目录包，
可完全自定义导航页的布局、配色与交互，也可继承应用内置的页面骨架。

## 1. 主题包结构

```
my-theme/
├── theme.toml            # 元信息（必填）
├── templates/
│   └── index.html        # 导航页模板（必填）
└── static/
    ├── style.css         # 样式（建议）
    ├── main.js           # 交互脚本（可选）
    └── favicon.svg       # 站点图标（可选）
```

### theme.toml

```toml
name = "my-theme"          # 目录名一致，仅允许字母/数字/下划线/中划线
version = "1.0.0"
description = "我的第一个主题"
author = "Me"
color_scheme = "light"     # light | dark（用于管理面板色板预览）
```

## 2. 两种写法

### 写法 A：继承内置骨架（推荐）

`templates/index.html` 使用 Jinja2 `extends` 应用内置的 `theme_base.html`，
只需覆写需要的区块：

```jinja
{% extends "theme_base.html" %}
{% block title %}{{ site.title }}{% endblock %}
{% block body %}
  <header>…自定义头部…</header>
  <main>
    {% for cat in categories %}
      <h2>{{ cat.name }}</h2>
      <div class="link-grid">
        {% for link in cat.links %}
          <a href="{{ link.url }}" target="{{ link.target }}" rel="noopener noreferrer">
            {{ link.title }}
          </a>
        {% endfor %}
      </div>
    {% endfor %}
  </main>
{% endblock %}
```

`theme_base.html` 提供区块：`title`、`head`、`body`、`scripts`，
并已自动引入 `{{ theme_url('style.css') }}`、`{{ theme_url('main.js') }}`、`{{ theme_url('favicon.svg') }}`
以及插件注入的 `{{ plugin_head_html }}` / `{{ plugin_footer_html }}`。

### 写法 B：完全自定义

不 `extends`，从零写完整 HTML。此时需自行引入静态资源：

```html
<link rel="stylesheet" href="{{ theme_url('style.css') }}">
<script src="{{ theme_url('main.js') }}"></script>
```

## 3. 模板上下文变量

公开导航页渲染时，模板可获得以下变量：

| 变量 | 说明 |
|---|---|
| `site.title / site.description / site.logo / site.footer` | 站点设置 |
| `site.target_default` | 链接默认打开方式（`_blank` / `_self`） |
| `categories` | 分类列表：`{id, name, icon, link_count, links[]}` |
| `link.title / link.url / link.description / link.icon / link.target` | 链接字段 |
| `icon_for(link)` | 图标计算辅助：返回 `{"type":"image","url":…}` 或 `{"type":"letter","letter":…,"color":…}` |
| `search_enabled` | 是否显示搜索框（布尔） |
| `user` | 当前是否为管理员登录（布尔） |
| `theme` | 当前主题信息（`{name, color_scheme, …}`） |
| `theme_url(path)` | 生成主题静态资源 URL |
| `plugin_head_html / plugin_footer_html` | 插件注入的 HTML（已标记为安全） |
| `plugin_*` | 插件通过 `page_data` 钩子注入的自定义变量 |
| `version` | SakuNav 版本号 |

## 4. 图标规范

- 链接有自定义图标（`link.icon` 非空）：`icon_for(link).type == "image"`，直接 `<img src=…>`。
- 无自定义图标：使用首字母色块。推荐写法：

```html
<span class="link-icon letter" style="--accent: {{ icon_for(link).color }}">{{ icon_for(link).letter }}</span>
```

颜色由链接自定义或按标题哈希从 8 色调色板自动分配。

## 5. 打包与上传

1. 将主题目录打成 zip（顶层目录即主题名）：

```bash
cd 主题父目录 && zip -r my-theme.zip my-theme
```

2. 管理面板 → 主题 → 上传并安装；安装成功后即可「启用」。

**zip 校验规则**：必须是合法 zip、顶层目录名合法、包含 `theme.toml`；
拒绝绝对路径、路径穿越（`..`）与空字节条目。内置主题不可删除，用户主题可删除。

## 6. 注意事项

- 主题模板中的输出会自动转义（`autoescape`）；若确需输出原始 HTML（如插件注入内容），
  请使用 `|safe` 并确保内容来源可信。
- 用户主题存放在数据卷 `data/themes/`，重建容器不丢失；同名时内置主题优先。
- 开发时可先把主题目录放进 `data/themes/` 直接刷新查看，迭代完成后再打成 zip 分发。
- 参考实现：`themes/default/`（明亮、卡片式）、`themes/dark/`（暗色）——两者共用页面结构，仅色板不同。
