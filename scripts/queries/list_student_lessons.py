#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：跨档案列出指定学员的全部课次（班课+一对一）

输入：
  --vault    Vault 根目录
  --student  学员姓名（必填，支持模糊匹配）

输出（JSON）：
  status: ok | error
  data:
    student: "艾克丹"
    lessons: [
      {
        "type": "class",
        "target_name": "3164",
        "lesson_num": 1,
        "date": "2026-03-15",
        "path": "...",
        "has_feedback_file": true
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
    is_class_folder,
    is_one_on_one_folder,
    format_output,
)


def find_student_lessons(vault: Path, student_name: str) -> list[dict]:
    """遍历所有档案，查找包含该学员的课次"""
    results = []
    # 遍历 Vault 下所有一级目录
    for target_dir in vault.iterdir():
        if not target_dir.is_dir():
            continue

        target_name = target_dir.name
        target_type = None
        if is_class_folder(target_dir):
            target_type = "class"
        elif is_one_on_one_folder(target_dir):
            # 一对一目录名就是学员名，直接匹配
            if student_name not in target_name:
                continue
            target_type = "one_on_one"
        else:
            continue

        lesson_dirs = list_lesson_dirs(target_dir, target_name)
        for lesson_dir in lesson_dirs:
            m = re.search(r"Lesson\s+(\d+)", lesson_dir.name, re.IGNORECASE)
            if not m:
                continue
            lesson_num = int(m.group(1))

            # 对于班课，需要确认 Feedback 文件中确实包含该学员
            if target_type == "class":
                fb_file = lesson_dir / f"Feedback {lesson_num}.md"
                if not fb_file.exists():
                    continue
                content = fb_file.read_text(encoding="utf-8")
                # 用正则匹配二级标题 ## 👤 学员名 或 ## 学员名（排除 ###）
                pattern = rf"^##(?!\s*#)\s*[👤\s]*{re.escape(student_name)}\s*$"
                if not re.search(pattern, content, re.MULTILINE):
                    continue

            # 读取课次日期
            lesson_file = lesson_dir / f"{target_name} Lesson {lesson_num}.md"
            date_str = None
            if lesson_file.exists():
                _, fm = read_md_file(lesson_file)
                date_raw = fm.get("Date", "")
                if date_raw:
                    m2 = re.match(r"(\d{4}-\d{2}-\d{2})", str(date_raw))
                    if m2:
                        date_str = m2.group(1)

            results.append({
                "type": target_type,
                "target_name": target_name,
                "lesson_num": lesson_num,
                "date": date_str,
                "path": str(lesson_dir),
                "has_feedback_file": (lesson_dir / f"Feedback {lesson_num}.md").exists(),
            })

    # 按日期排序
    results.sort(key=lambda x: (x["date"] or "", x["target_name"], x["lesson_num"]))
    return results


def main():
    parser = argparse.ArgumentParser(description="跨档案列出学员课次")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--student", required=True, help="学员姓名")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    lessons = find_student_lessons(vault, args.student)
    print(format_output("ok", data={
        "student": args.student,
        "lessons": lessons,
        "count": len(lessons),
    }))


if __name__ == "__main__":
    main()
