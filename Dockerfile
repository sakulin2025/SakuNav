# SakuNav —— 轻量私有云书签导航页
# 单阶段精简镜像：仅保留运行期依赖，无编译步骤，镜像体积最小化
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先拷贝依赖清单以利用 Docker 层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝应用源码与内置主题、内置插件
COPY sakunav ./sakunav
COPY themes ./themes
COPY plugins ./plugins

# 数据目录：SQLite 数据库 + 用户上传的主题/插件（挂载卷持久化）
RUN mkdir -p /app/data/themes /app/data/plugins

# 默认环境变量（均可被 docker-compose / 运行时覆盖）
ENV SAKUNAV_HOST=0.0.0.0 \
    SAKUNAV_PORT=8000 \
    SAKUNAV_DATA_DIR=/app/data \
    SAKUNAV_THEMES_DIR=/app/themes \
    SAKUNAV_PLUGINS_DIR=/app/plugins \
    SAKUNAV_EXTRA_THEMES_DIR=/app/data/themes \
    SAKUNAV_EXTRA_PLUGINS_DIR=/app/data/plugins

EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["python", "-m", "sakunav"]
