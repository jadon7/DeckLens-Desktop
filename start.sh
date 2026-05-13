#!/bin/bash
# 启动 DeckLens 服务
cd "$(dirname "$0")"
echo "启动 DeckLens..."
echo "浏览器访问: http://localhost:8080"

# 激活虚拟环境
source .venv/bin/activate

open http://localhost:8080
python3 app.py
