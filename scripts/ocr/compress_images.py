#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图像压缩脚本
使用 PIL 压缩图像，限制最大尺寸和质量

输入：
  --images     图像文件路径列表（必填）
  --max-size   最大边长像素（默认 2048）
  --quality    JPEG 质量（默认 85）

输出（JSON）：
  status: ok | error
  data:
    compressed:
      - original: "path"
        compressed: "path"
        original_size: N
        compressed_size: N
"""

import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xdf_utils import format_output

try:
    from PIL import Image
except ImportError:
    print(format_output("error", error="请安装 Pillow: pip install Pillow"))
    sys.exit(1)


def compress_image(image_path: str, max_size: int = 2048, quality: int = 85) -> dict:
    """压缩单张图像，返回压缩信息"""
    original_path = Path(image_path)
    if not original_path.exists():
        raise FileNotFoundError(f"图像文件不存在: {image_path}")

    original_size = original_path.stat().st_size
    img = Image.open(original_path)

    # 如果图像尺寸超过 max_size，进行缩放
    width, height = img.size
    if width > max_size or height > max_size:
        ratio = min(max_size / width, max_size / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        img = img.resize((new_width, new_height), Image.LANCZOS)

    # 生成压缩后的文件路径
    compressed_path = original_path.parent / f"{original_path.stem}_compressed{original_path.suffix}"

    # 保存压缩后的图像
    save_kwargs = {"quality": quality}
    if original_path.suffix.lower() in (".jpg", ".jpeg"):
        save_kwargs["optimize"] = True
    elif original_path.suffix.lower() == ".png":
        save_kwargs["optimize"] = True

    # 转换为 RGB 模式（JPEG 不支持 RGBA）
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
        compressed_path = original_path.parent / f"{original_path.stem}_compressed.jpg"

    img.save(str(compressed_path), **save_kwargs)
    compressed_size = compressed_path.stat().st_size

    return {
        "original": str(original_path),
        "compressed": str(compressed_path),
        "original_size": original_size,
        "compressed_size": compressed_size,
    }


def main():
    parser = argparse.ArgumentParser(description="图像压缩脚本")
    parser.add_argument("--images", nargs="+", required=True, help="图像文件路径列表")
    parser.add_argument("--max-size", type=int, default=2048, help="最大边长像素（默认 2048）")
    parser.add_argument("--quality", type=int, default=85, help="JPEG 质量（默认 85）")
    args = parser.parse_args()

    try:
        compressed = []
        for img_path in args.images:
            result = compress_image(img_path, args.max_size, args.quality)
            compressed.append(result)

        print(format_output("ok", data={"compressed": compressed}))
    except Exception as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
