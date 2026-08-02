#!/usr/bin/env bash
# 离线交付辅助：在【能上网】的机器上准备离线包
# 1) 下载后端 Python 依赖 wheels
# 2) 导出 Docker 镜像 tar（可选，若目标机有 Docker）
# 3) 构建前端产物
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$(pwd)"

echo "==> [1/3] 下载后端依赖 wheels 到 backend/wheels/"
mkdir -p backend/wheels
pip download -r backend/requirements.txt -d backend/wheels

echo "==> [2/3] 构建前端产物 frontend/dist/"
if command -v npm &>/dev/null; then
  (cd frontend && npm ci && npm run build)
else
  echo "   未检测到 npm，请手动在 frontend/ 执行 npm ci && npm run build"
fi

echo "==> [3/3] 导出基础镜像 tar 到 deploy/offline/images/"
mkdir -p deploy/offline/images
if command -v docker &>/dev/null; then
  docker pull postgres:14 nginx:alpine python:3.11-slim
  docker save postgres:14 nginx:alpine python:3.11-slim -o deploy/offline/images/base-images.tar
  echo "   已导出 base-images.tar（内网用 docker load -i 导入）"
else
  echo "   未检测到 docker，跳过镜像导出（离线/原生部署不需要）"
fi

echo ""
echo "✅ 离线物料准备完成。打包以下内容为交付包："
echo "   backend/  frontend/dist/  db/  deploy/  docker-compose.yml  README.md"
