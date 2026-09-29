.PHONY: setup test dev docker up clean

## 初始化本地开发环境（venv + 依赖）
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt -e ".[dev]"

## 运行测试
test:
	.venv/bin/python -m pytest tests -q

## 本地开发启动（http://127.0.0.1:8000）
dev:
	.venv/bin/python -m sakunav

## 构建 Docker 镜像
docker:
	docker build -t sakunav:latest .

## 以 docker compose 启动（默认端口 8080）
up:
	docker compose up -d --build

## 停止并清理
clean:
	docker compose down --remove-orphans
