"""链接地址校验：仅允许安全协议，自动补全 https://。"""

import re
from typing import Optional

# 允许的协议白名单（拦截 javascript:、data:、vbscript: 等危险协议）
ALLOWED_SCHEMES = {"http", "https", "ftp", "ftps", "mailto", "tel", "magnet"}

MAX_URL_LENGTH = 2048

_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")


def validate_url(raw: Optional[str]) -> Optional[str]:
    """校验并规范化链接地址；非法时返回 None。"""
    url = (raw or "").strip()
    if not url:
        return None
    # 先提取原始字符串自带的协议前缀，避免 javascript: 等危险协议被 https:// 前缀掩盖
    match = _SCHEME_RE.match(url)
    if match is not None:
        scheme = match.group(1).lower()
        if scheme not in ALLOWED_SCHEMES:
            return None
        candidate = url
    else:
        candidate = "https://" + url
    if len(candidate) > MAX_URL_LENGTH:
        return None
    return candidate
