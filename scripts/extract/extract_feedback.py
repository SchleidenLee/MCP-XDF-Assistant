#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：提取反馈内容（班级反馈 + 学员反馈）

输入：
  --vault    Vault 根目录
  --target   班级名或一对一学员名（必填）
  --lesson   课次号，支持范围（如 1,2,3 或 1-3 或 1,3,5-7）
  --student  学员姓名（可选，不传则提取全部学员反馈）

输出（JSON）：
  status: ok | error
  data:
    target: "3164"
    lessons: [
      {
        "lesson_num": 2,
        "date": "2026-03-22",
        "class_feedback": "本节课班级整体表现优异...",
        "students": [
          {
            "name": "艾克丹",
            "feedback": "该学员在线上课程中能够紧跟课堂节奏..."
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
    resolve_target,
    read_md_file,
    extract_feedback_from_content,
    format_output,
)


def parse_lesson_range(lesson_str: str) -> list[int]:
    """解析课次范围字符串"""
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


def extract_student_feedback(feedback_content: str, student_name: str) -> str:
    """从 Feedback 文件中提取指定学员的反馈总结"""
    pattern = rf"^##(?!\s*#)\s*[👤\s]*{re.escape(student_name)}\s*$"
    match = re.search(pattern, feedback_content, re.MULTILINE)
    if not match:
        return ""

    start = match.start()
    next_section = re.search(r"^##(?!\s*#)", feedback_content[start + 1 :], re.MULTILINE)
    if next_section:
        block = feedback_content[start : start + 1 + next_section.start()]
    else:
        block = feedback_content[start:]

    return extract_feedback_from_content(block)


def main():
    parser = argparse.ArgumentParser(description="提取反馈内容")
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

    try:
        target_path = resolve_target(vault, args.target)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    lesson_numbers = parse_lesson_range(args.lesson)
    results = []

    for num in lesson_numbers:
        lesson_dir = target_path / f"{args.target} Lesson {num}"
        if not lesson_dir.exists():
            continue

        lesson_file = lesson_dir / f"{args.target} Lesson {num}.md"
        date_str = None
        class_feedback = ""

        if lesson_file.exists():
            content, fm = read_md_file(lesson_file)
            date_raw = fm.get("Date", "")
            if date_raw:
                m = re.match(r"(\d{4}-\d{2}-\d{2})", str(date_raw))
                if m:
                    date_str = m.group(1)
            class_feedback = extract_feedback_from_content(content)

        students_fb = []
        fb_file = lesson_dir / f"Feedback {num}.md"
        if fb_file.exists():
            fb_content = fb_file.read_text(encoding="utf-8")
            if args.student:
                fb = extract_student_feedback(fb_content, args.student)
                if fb:
                    students_fb.append({"name": args.student, "feedback": fb})
            else:
                # 只匹配二级标题（## 开头但不是 ###），提取所有学员反馈
                for block_match in re.finditer(r"^##(?!\s*#)\s*[👤\s]*(.+)$", fb_content, re.MULTILINE):
                    name = block_match.group(1).strip()
                    fb = extract_student_feedback(fb_content, name)
                    students_fb.append({"name": name, "feedback": fb})

        results.append({
            "lesson_num": num,
            "date": date_str,
            "class_feedback": class_feedback,
            "students": students_fb,
        })

    print(format_output("ok", data={
        "target": args.target,
        "lessons": results,
    }))


if __name__ == "__main__":
    main()
