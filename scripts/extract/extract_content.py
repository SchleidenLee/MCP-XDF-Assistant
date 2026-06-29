#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：提取课程文件中的特定内容

输入：
  --vault     Vault 根目录
  --target    班级名或一对一学员名（必填）
  --lesson-num 课次号（必填）
  --type      提取类型：raw_record | feedback_summary | teaching_content | all（默认 all）

输出（JSON）：
  status: ok | error
  data:
    lesson: 2
    type: "all"
    content:
      raw_record: [...]
      feedback_summary: "..."
      teaching_content: "..."
"""

import argparse
import sys
import re

from xdf_utils import (
    resolve_vault,
    resolve_target,
    read_md_file,
    extract_raw_from_content,
    extract_feedback_from_content,
    format_output,
)


def extract_teaching_content(content: str) -> str:
    """提取 ### 授课内容 下的内容，直到下一个 ### 级别标题"""
    lines = content.split("\n")
    result_lines = []
    in_section = False

    for line in lines:
        stripped = line.strip()
        if stripped == "### 授课内容":
            in_section = True
            continue
        if in_section:
            if re.match(r"^###\s", stripped):
                break
            result_lines.append(line)

    return "\n".join(result_lines).strip()


def main():
    parser = argparse.ArgumentParser(description="提取课程文件中的特定内容")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", required=True, help="班级名或一对一学员名")
    parser.add_argument("--lesson-num", type=int, required=True, help="课次号")
    parser.add_argument(
        "--type",
        type=str,
        default="all",
        choices=["raw_record", "feedback_summary", "teaching_content", "all"],
        help="提取类型（默认 all）",
    )
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

    lesson_dir = target_path / f"{args.target} Lesson {args.lesson_num}"
    if not lesson_dir.exists():
        print(format_output("error", error=f"课程目录不存在: {lesson_dir.name}"))
        sys.exit(1)

    lesson_file = lesson_dir / f"{args.target} Lesson {args.lesson_num}.md"
    if not lesson_file.exists():
        print(format_output("error", error=f"课程文件不存在: {lesson_file.name}"))
        sys.exit(1)

    content, fm = read_md_file(lesson_file)

    # 根据类型提取内容
    raw_record = extract_raw_from_content(content, "### 原始记录")
    feedback_summary = extract_feedback_from_content(content)
    teaching_content = extract_teaching_content(content)

    content_data = {}
    if args.type == "all":
        content_data = {
            "raw_record": raw_record,
            "feedback_summary": feedback_summary,
            "teaching_content": teaching_content,
        }
    elif args.type == "raw_record":
        content_data = {"raw_record": raw_record}
    elif args.type == "feedback_summary":
        content_data = {"feedback_summary": feedback_summary}
    elif args.type == "teaching_content":
        content_data = {"teaching_content": teaching_content}

    print(format_output("ok", data={
        "lesson": args.lesson_num,
        "type": args.type,
        "content": content_data,
    }))


if __name__ == "__main__":
    main()
