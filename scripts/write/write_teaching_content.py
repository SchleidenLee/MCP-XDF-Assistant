#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：写入授课内容到 lesson 文件

输入：
  --vault         Vault 根目录
  --target        班级名或一对一学员名（必填）
  --lesson-num    课次号（必填）
  --content       授课内容文本

输出（JSON）：
  {"status": "ok", "data": {"file": "...", "updated": true}}
"""

import argparse
import re
import sys
from pathlib import Path

from xdf_utils import resolve_vault, resolve_target, read_md_file, format_output


def write_teaching_content(lesson_file: Path, content: str) -> bool:
    """
    将授课内容写入 lesson 文件的 ### 授课内容 区域。
    若该区域存在则替换内容，否则在文件中插入。
    返回是否成功写入。
    """
    text = lesson_file.read_text(encoding="utf-8")
    section_header = "### 授课内容"

    # 查找 ### 授课内容 区域：从标题开始到下一个 ### 标题之前
    lines = text.split("\n")
    new_lines = []
    in_section = False
    section_found = False
    replaced = False

    for line in lines:
        stripped = line.strip()

        if stripped == section_header:
            section_found = True
            in_section = True
            new_lines.append(line)
            # 在标题后插入新内容
            for content_line in content.split("\n"):
                new_lines.append(content_line)
            replaced = True
            continue

        if in_section:
            # 遇到下一个 ### 标题，结束区域
            if re.match(r"^###\s", stripped):
                in_section = False
                new_lines.append(line)
                continue
            # 跳过原有内容（已被替换）
            continue

        new_lines.append(line)

    if not section_found:
        # 如果 ### 授课内容 不存在，追加到文件末尾
        new_lines.append("")
        new_lines.append(section_header)
        for content_line in content.split("\n"):
            new_lines.append(content_line)
        new_lines.append("")

    lesson_file.write_text("\n".join(new_lines), encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description="写入授课内容到 lesson 文件")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", required=True, help="班级名或一对一学员名")
    parser.add_argument("--lesson-num", required=True, type=int, help="课次号")
    parser.add_argument("--content", required=True, help="授课内容文本")
    args = parser.parse_args()

    if not args.content.strip():
        print(format_output("error", error="必须提供 --content"))
        sys.exit(1)

    # 解析 vault
    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    # 定位 lesson 文件
    try:
        target_path = resolve_target(vault, args.target)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    lesson_dir = target_path / f"{args.target} Lesson {args.lesson_num}"
    if not lesson_dir.exists():
        print(format_output("error", error=f"课次目录不存在: {lesson_dir}"))
        sys.exit(1)

    lesson_file = lesson_dir / f"{args.target} Lesson {args.lesson_num}.md"
    if not lesson_file.exists():
        print(format_output("error", error=f"Lesson 文件不存在: {lesson_file}"))
        sys.exit(1)

    # 写入授课内容
    updated = write_teaching_content(lesson_file, args.content)

    print(format_output("ok", data={
        "file": str(lesson_file),
        "updated": updated,
    }))


if __name__ == "__main__":
    main()
