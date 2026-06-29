#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：按学员汇总多课次原始记录与反馈（生成学员阶段性总结素材）

输入：
  --vault    Vault 根目录
  --student  学员姓名（必填）
  --lessons  课次范围（可选，如 1-5；不传则汇总全部）

输出（JSON）：
  status: ok | error
  data:
    student: "艾克丹"
    total_lessons: 8
    summary: [
      {
        "lesson_num": 2,
        "date": "2026-03-22",
        "target": "3164",
        "type": "class",
        "raw": ["简答题：关键词划分清楚...", "判断题：识别不来..."],
        "feedback": "该学员在线上课程中能够紧跟课堂节奏..."
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
    list_lesson_dirs,
    extract_raw_from_content,
    extract_feedback_from_content,
    is_class_folder,
    is_one_on_one_folder,
    format_output,
)


def parse_lesson_range(lesson_str: str) -> set[int] | None:
    """解析课次范围字符串，返回 None 表示全部"""
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
    return numbers


def extract_student_block(content: str, student_name: str) -> str:
    """从 Feedback 文件中提取指定学员的完整块"""
    pattern = rf"^##\s*[👤\s]*{re.escape(student_name)}\s*$"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return ""
    start = match.start()
    next_section = re.search(r"^##\s", content[start + 1 :], re.MULTILINE)
    if next_section:
        return content[start : start + 1 + next_section.start()]
    return content[start:]


def main():
    parser = argparse.ArgumentParser(description="学员多课次原始记录与反馈汇总")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--student", required=True, help="学员姓名")
    parser.add_argument("--lessons", default=None, help="课次范围（如 1-5，可选）")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    lesson_filter = parse_lesson_range(args.lessons) if args.lessons else None
    summary = []

    # 遍历所有档案（根目录 + Current Class + Archived）
    search_dirs = [vault]
    for subdir_name in ["Current Class", "Archived"]:
        subdir = vault / subdir_name
        if subdir.is_dir():
            search_dirs.append(subdir)

    seen_targets = set()

    for search_dir in search_dirs:
        for sub in search_dir.iterdir():
            if not sub.is_dir():
                continue

            target_name = sub.name
            if target_name in seen_targets:
                continue
            seen_targets.add(target_name)

            target_type = None
            if is_class_folder(sub):
                target_type = "class"
            elif is_one_on_one_folder(sub):
                if args.student not in target_name:
                    continue
                target_type = "one_on_one"
            else:
                continue

            lesson_dirs = list_lesson_dirs(sub, target_name)
            for lesson_dir in lesson_dirs:
                m = re.search(r"Lesson\s+(\d+)", lesson_dir.name, re.IGNORECASE)
                if not m:
                    continue
                lesson_num = int(m.group(1))

                if lesson_filter and lesson_num not in lesson_filter:
                    continue

                lesson_file = lesson_dir / f"{target_name} Lesson {lesson_num}.md"
                date_str = None
                if lesson_file.exists():
                    _, fm = read_md_file(lesson_file)
                    date_raw = fm.get("Date", "")
                    if date_raw:
                        m2 = re.match(r"(\d{4}-\d{2}-\d{2})", str(date_raw))
                        if m2:
                            date_str = m2.group(1)

                # 提取原始记录和反馈
                raw = []
                feedback = ""

                fb_file = lesson_dir / f"Feedback {lesson_num}.md"
                if fb_file.exists():
                    fb_content = fb_file.read_text(encoding="utf-8")
                    block = extract_student_block(fb_content, args.student)
                    if block:
                        raw = extract_raw_from_content(block, "### 原始记录")
                        feedback = extract_feedback_from_content(block)

                # 班课如果没有该学员的块，跳过
                if target_type == "class" and not raw and not feedback:
                    continue

                summary.append({
                    "lesson_num": lesson_num,
                    "date": date_str,
                    "target": target_name,
                    "type": target_type,
                    "raw": raw,
                    "feedback": feedback,
                })

    summary.sort(key=lambda x: (x["date"] or "", x["target"], x["lesson_num"]))

    print(format_output("ok", data={
        "student": args.student,
        "total_lessons": len(summary),
        "summary": summary,
    }))


if __name__ == "__main__":
    main()
