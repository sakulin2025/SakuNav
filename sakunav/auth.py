"""管理员认证与会话守卫。

认证基于签名会话 Cookie（Starlette SessionMiddleware），
登录态信息存于 request.session["user"]。
"""

from urllib.parse import quote

from fastapi import HTTPException, Request

SESSION_USER = "user"
ADMIN = "admin"


def is_logged_in(request: Request) -> bool:
    return request.session.get(SESSION_USER) == ADMIN


def login(request: Request) -> None:
    request.session[SESSION_USER] = ADMIN


def logout(request: Request) -> None:
    request.session.clear()


def require_admin_page(request: Request) -> None:
    """页面级守卫：未登录时 303 跳转登录页，登录后回跳原地址。"""
    if not is_logged_in(request):
        location = "/login"
        if request.url.path and request.url.path != "/login":
            location += f"?next={quote(request.url.path)}"
        raise HTTPException(status_code=303, headers={"Location": location})


def require_admin_api(request: Request) -> None:
    """API 级守卫：未登录时返回 401。"""
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
