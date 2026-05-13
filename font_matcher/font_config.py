"""
font_config.py — 字体配置表
定义 24 个目标字体的路径、分类、PPT 中使用的字体名
"""

import os

EAGLE_DIR = os.path.expanduser("~/Library/Fonts/EagleApp")

# 字体注册表
# key: 内部 ID
# path: 字体文件路径
# pptx_name: 写入 PPT 时使用的字体名（需要用户机器上也有该字体才能正确显示）
# category: heiti / songti / maobi / digit
# weight_hint: 预期粗细等级 (1=最细, 9=最粗)，用于排序参考
FONT_REGISTRY = {
    # ─── 黑体类 (12) ───
    "dream-sans-w3": {
        "path": os.path.join(EAGLE_DIR, "f690928f8fa5d1deba105ff911ad3354.ttc"),
        "pptx_name": "Dream Han Sans SC W3",
        "category": "heiti",
        "weight_hint": 2,
    },
    "dream-sans-w8": {
        "path": os.path.join(EAGLE_DIR, "a1b1eed376f3011a946beeee4bd5926a.ttc"),
        "pptx_name": "Dream Han Sans SC W8",
        "category": "heiti",
        "weight_hint": 4,
    },
    "dream-sans-w17": {
        "path": os.path.join(EAGLE_DIR, "2a1f641e06fbbf03d3be6ff6ef687488.ttc"),
        "pptx_name": "Dream Han Sans SC W17",
        "category": "heiti",
        "weight_hint": 7,
    },
    "dream-sans-w21": {
        "path": os.path.join(EAGLE_DIR, "a6634573dfc62727d37c0dd576fd5cc1.ttc"),
        "pptx_name": "Dream Han Sans SC W21",
        "category": "heiti",
        "weight_hint": 9,
    },
    "alibaba-light": {
        "path": os.path.join(EAGLE_DIR, "AlibabaPuHuiTi_2_45_Light.ttf"),
        "pptx_name": "Alibaba PuHuiTi 2.0 45 Light",
        "category": "heiti",
        "weight_hint": 2,
    },
    "alibaba-bold": {
        "path": os.path.join(EAGLE_DIR, "AlibabaPuHuiTi_2_75_SemiBold.ttf"),
        "pptx_name": "Alibaba PuHuiTi 2.0 75 SemiBold",
        "category": "heiti",
        "weight_hint": 6,
    },
    "misans-regular": {
        "path": os.path.join(EAGLE_DIR, "MiSans-Regular.ttf"),
        "pptx_name": "MiSans",
        "category": "heiti",
        "weight_hint": 4,
    },
    "misans-bold": {
        "path": os.path.join(EAGLE_DIR, "MiSans-Bold.ttf"),
        "pptx_name": "MiSans Bold",
        "category": "heiti",
        "weight_hint": 7,
    },
    "misans-demibold": {
        "path": os.path.join(EAGLE_DIR, "MiSans-Demibold.ttf"),
        "pptx_name": "MiSans Demibold",
        "category": "heiti",
        "weight_hint": 5,
    },
    "monotitl": {
        "path": os.path.join(EAGLE_DIR, "MonuTitl-CnMd.ttf"),
        "pptx_name": "MonuTitl CnMd",
        "category": "heiti",
        "weight_hint": 5,
    },
    "smiley-sans": {
        "path": os.path.join(EAGLE_DIR, "SmileySans-Oblique.ttf"),
        "pptx_name": "Smiley Sans Oblique",
        "category": "heiti",
        "weight_hint": 5,
    },
    "misans-heavy": {
        "path": os.path.join(EAGLE_DIR, "MiSans-Heavy.ttf"),
        "pptx_name": "MiSans Heavy",
        "category": "heiti",
        "weight_hint": 8,
    },

    # ─── 宋体类 (6) ───
    "dream-serif-w3": {
        "path": os.path.join(EAGLE_DIR, "DreamHanSerifCN-W3.ttf"),
        "pptx_name": "Dream Han Serif CN W3",
        "category": "songti",
        "weight_hint": 2,
    },
    "dream-serif-w8": {
        "path": os.path.join(EAGLE_DIR, "DreamHanSerifCN-W8.ttf"),
        "pptx_name": "Dream Han Serif CN W8",
        "category": "songti",
        "weight_hint": 4,
    },
    "dream-serif-w17": {
        "path": os.path.join(EAGLE_DIR, "DreamHanSerifCN-W17.ttf"),
        "pptx_name": "Dream Han Serif CN W17",
        "category": "songti",
        "weight_hint": 7,
    },
    "xinyi-jixiang-song": {
        "path": os.path.join(EAGLE_DIR, "Fontquan-XinYiJiXiangSong-Regular.ttf"),
        "pptx_name": "Fontquan-XinYiJiXiangSong",
        "category": "songti",
        "weight_hint": 4,
    },
    "houzun-song": {
        "path": os.path.join(EAGLE_DIR, "HouZunSongTi.ttf"),
        "pptx_name": "HouZunSongTi",
        "category": "songti",
        "weight_hint": 4,
    },
    "flower-fangsong": {
        "path": os.path.join(EAGLE_DIR, "FlowerFangSong-.ttf"),
        "pptx_name": "FlowerFangSong",
        "category": "songti",
        "weight_hint": 3,
    },

    # ─── 毛笔/楷书类 (1) ───
    "lxgw-wenkai": {
        "path": "/Users/sunyi/Desktop/CodeX Project/非主线任务/fonts/LXGWWenKai/LXGWWenKai-Regular.ttf",
        "pptx_name": "LXGW WenKai",
        "category": "maobi",
        "weight_hint": 4,
    },

    # ─── 数字/英文特殊字体 (5) ───
    "oswald": {
        "path": "/Library/Fonts/Oswald/Oswald-VariableFont_wght.ttf",
        "pptx_name": "Oswald",
        "category": "digit",
        "weight_hint": 5,
    },
    "bebas-neue": {
        "path": "/Library/Fonts/Bebas_Neue/BebasNeue-Regular.ttf",
        "pptx_name": "Bebas Neue",
        "category": "digit",
        "weight_hint": 6,
    },
    "d-din": {
        "path": os.path.join(EAGLE_DIR, "D-DIN.ttf"),
        "pptx_name": "D-DIN",
        "category": "digit",
        "weight_hint": 4,
    },
    "roboto-mono": {
        "path": "/Users/sunyi/Desktop/CodeX Project/非主线任务/fonts/RobotoMono/RobotoMono-Regular.ttf",
        "pptx_name": "Roboto Mono",
        "category": "digit",
        "weight_hint": 4,
    },
    "montserrat": {
        "path": "/Library/Fonts/Montserrat/Montserrat-VariableFont_wght.ttf",
        "pptx_name": "Montserrat",
        "category": "digit",
        "weight_hint": 5,
    },
    # Roboto Mono 缺失，用 D-DIN 兜底等宽场景
}
