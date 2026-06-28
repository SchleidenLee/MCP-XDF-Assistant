#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：提取原始记录

输入：
  --vault    Vault 根目录
  --target   班级名或一对一学员名（必填）
  --lesson   课次号，支持范围（如 1,2,3 或 1-3 或 1,3,5-7）
  --student  学员姓名（可选，指定则只提取该学员的原始记录；一对一可省略）

输出（JSON）：
  status: ok | error
  data:
    target: "3164"
    lessons: [
      {
        "lesson_num": 2,
        "date": "2026-03-22",
        "class_raw": ["班级整体表现好...", "作业基本全员完成..."],
        "students": [
          {
            "name": "艾克丹",
            "raw": ["简答题：关键词划分清楚...", "判断题：识别不来..."]
          }
        ]
      }
    ]
"""

import argparse
import sys
import re
from pathlib import Path

from xdf_utils import (
    resolve_vault,
    read_md_file,
    list_lesson_dirs,
    extract_raw_from_content,
    format_output,
    is_class_folder,
    is_one_on_one_folder,
)


def parse_lesson_range(lesson_str: str) -> list[int]:
    """解析课次范围字符串，如 '1,2,3' 或 '1-3' 或 '1,3,5-7'"""
    numbers = set()
    for part in lesson_str.split(","):
        part = part.strip()
        if "-" in part:
            start, _, end = part.partition("-")
            try:
                for i in range(int(start), int(end) + 1):
                    numbers.add(i)
            except ValueError:
                continue
        else:
            try:
                numbers.add(int(part))
            except ValueError:
                continue
    return sorted(numbers)


def extract_student_raw(feedback_content: str, student_name: str) -> list[str]:
    """从 Feedback 文件中提取指定学员的原始记录"""
    pattern = rf"^##\s*[👤\s]*{re.escape(student_name)}\s*$"
    match = re.search(pattern, feedback_content, re.MULTILINE)
    if not match:
        return []

    start = match.start()
    next_section = re.search(r"^##\s", feedback_content[start + 1 :], re.MULTILINE)
    if next_section:
        block = feedback_content[start : start + 1 + next_section.start()]
    else:
        block = feedback_content[start:]

    return extract_raw_from_content(block, "### 原始记录")


def main():
    parser = argparse.ArgumentParser(description="提取原始记录")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", required=True, help="班级名或一对一学员名")
    parser.add_argument("--lesson", required=True, help="课次号或范围（如 1-3,5）")
    parser.add_argument("--student", default=None, help="学员姓名（可选）")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    target_path = vault / args.target
    if not target_path.exists():
        print(format_output("error", error=f"目标 '{args.target}' 不存在"))
        sys.exit(1)

    target_type = "unknown"
    if is_class_folder(target_path):
        target_type = "class"
    elif is_one_on_one_folder(target_path):
        target_type = "one_on_one"

    lesson_numbers = parse_lesson_range(args.lesson)
    results = []

    for num in lesson_numbers:
        lesson_dir = target_path / f"{args.target} Lesson {num}"
        if not lesson_dir.exists():
            continue

        lesson_file = lesson_dir / f"{args.target} Lesson {num}.md"
        date_str = None
        class_raw = []

        if lesson_file.exists():
            content, fm = read_md_file(lesson_file)
            date_raw = fm.get("Date", "")
            if date_raw:
                m = re.match(r"(\d{4}-\d{2}-\d{2})", str(date_raw))
                if m:
                    date_str = m.group(1)
            class_raw = extract_raw_from_content(content, "### 原始记录")

        # 提取学员原始记录
        students_raw = []
        fb_file = lesson_dir / f"Feedback {num}.md"

        if fb_file.exists():
            fb_content = fb_file.read_text(encoding="utf-8")
            if args.student:
                raw = extract_student_raw(fb_content, args.student)
                if raw:
                    students_raw.append({"name": args.student, "raw": raw})
            else:
                # 提取所有学员
                for block_match in re.finditer(r"^##\s*[👤\s]*(.+)$", fb_content, re.MULTILINE):
                    name = block_match.group(1).strip()
                    raw = extract_student_raw(fb_content, name)
                    if raw:
                        students_raw.append({"name": name, "raw": raw})

        # 一对一模式下，如果没有指定 student，默认就是学员本人
        if target_type == "one_on_one" and not args.student:
            if students_raw:
                students_raw[0]["name"] = args.target

        results.append({
            "lesson_num": num,
            "date": date_str,
            "class_raw": class_raw,
            "students": students_raw,
        })

    print(format_output("ok", data={
        "target": args.target,
        "target_type": target_type,
        "lessons": results,
    }))


if __name__ == "__main__":
    main()
