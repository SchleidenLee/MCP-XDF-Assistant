#!/usr/bin/env python3
"""
图片压缩脚本 - 使用 ffmpeg 压缩答题卡图片
目标：压缩到 2MB 以下，最大边长 2048px
"""

import subprocess
import os
from pathlib import Path


def compress_image(input_path, output_path=None):
    """压缩单张图片"""
    input_path = Path(input_path)
    
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}.jpg"
    else:
        output_path = Path(output_path)
    
    cmd = [
        'ffmpeg',
        '-i', str(input_path),
        '-vf', "scale='if(gt(iw,ih),min(2048,iw),-1)':'if(gt(iw,ih),-1,min(2048,ih))'",
        '-q:v', '2',
        '-y',
        str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        size_mb = output_path.stat().st_size / 1024 / 1024
        return str(output_path), size_mb
    else:
        return None, 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description='压缩答题卡图片')
    parser.add_argument('--input-dir', required=True, help='输入目录')
    parser.add_argument('--output-dir', required=True, help='输出目录')
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    images = list(input_dir.glob('*.jpg')) + list(input_dir.glob('*.jpeg')) + list(input_dir.glob('*.png'))
    
    if not images:
        print(f"❌ 未找到图片文件")
        return
    
    print(f"📦 找到 {len(images)} 张图片，开始压缩...")
    
    for idx, img in enumerate(sorted(images), 1):
        output_path = output_dir / f"{img.stem}.jpg"
        _, size_mb = compress_image(img, output_path)
        print(f"[{idx}/{len(images)}] {img.name} → {size_mb:.2f}MB")
    
    print(f"\n✅ 压缩完成！输出目录：{output_dir}")


if __name__ == '__main__':
    main()
