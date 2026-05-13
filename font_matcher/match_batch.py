"""
match_batch.py — 批量字体匹配接口（供 Node.js 调用）

输入: JSON (stdin 或文件路径)
格式: {"boxes": [{"image_path": "...", "text": "..."}, ...]}

输出: JSON (stdout)
格式: {"results": [{"font_id": "...", "pptx_name": "...", "category": "...", "confidence": 0.85}, ...]}

用法:
  echo '{"boxes":[...]}' | python3 match_batch.py
  python3 match_batch.py input.json
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from font_matcher import match_font_from_file


def main():
    # 读取输入
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        with open(sys.argv[1], "r") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    boxes = data.get("boxes", [])
    results = []

    for box in boxes:
        image_path = box.get("image_path", "")
        text = box.get("text", "")

        if not image_path or not os.path.exists(image_path):
            results.append({
                "font_id": "misans-regular",
                "pptx_name": "MiSans",
                "category": "heiti",
                "confidence": 0.0,
                "error": f"image not found: {image_path}",
            })
            continue

        try:
            result = match_font_from_file(image_path, text)
            results.append(result)
        except Exception as e:
            results.append({
                "font_id": "misans-regular",
                "pptx_name": "MiSans",
                "category": "heiti",
                "confidence": 0.0,
                "error": str(e),
            })

    output = {"results": results}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
