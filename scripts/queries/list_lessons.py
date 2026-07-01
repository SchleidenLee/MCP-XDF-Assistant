#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：列出班级或一对一的全部课次

输入：
  --vault    Vault 根目录
  --target   班级名或一对一学员名（必填，如 3164 / 许宸睿）

输出（JSON）：
  status: ok | error
  data:
    target: "3164"
    target_type: "class" | "one_on_one"
    lessons: [
      {
        "lesson_num": 1,
        "date": "2026-03-15",
        "path": "...",
        "has_files": {"note": true, "wordlist": true, ...},
        "feedback_status": {
          "class_feedback_submitted": false,
          "class_feedback_has_content": true,
          "student_feedback_count": 0,
          "students_with_feedback": 0
        },
        "need_send_feedback": false
      }
    ]
"""

import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xdf_utils import (
    resolve_vault,
    resolve_target,
    list_lesson_dirs,
    get_lesson_meta,
    check_feedback_file_status,
    is_class_folder,
    is_one_on_one_folder,
    format_output,
)


def main():
    parser = argparse.ArgumentParser(description="列出全部课次")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", required=True, help="班级名或一对一学员名")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    # 解析目标路径
    try:
        target_path = resolve_target(vault, args.target)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    # 判断类型
    target_type = "unknown"
    if is_class_folder(target_path):
        target_type = "class"
    elif is_one_on_one_folder(target_path):
        target_type = "one_on_one"

    lesson_dirs = list_lesson_dirs(target_path, args.target)
    lessons = []
    for lesson_dir in lesson_dirs:
        # 从目录名解析课次号
        import re
        m = re.search(r"Lesson\s+(\d+)", lesson_dir.name, re.IGNORECASE)
        if not m:
            continue
        lesson_num = int(m.group(1))
        meta = get_lesson_meta(lesson_dir, args.target, lesson_num)

        # 补充学员反馈文件状态
        fb_file = lesson_dir / f"Feedback {lesson_num}.md"
        fb_status = check_feedback_file_status(fb_file)
        meta["feedback_status"]["student_feedback_count"] = fb_status["students"]
        meta["feedback_status"]["students_with_feedback"] = fb_status["generated"]
        meta["feedback_status"]["students_pending"] = fb_status["pending"]
        meta["path"] = str(lesson_dir)
        lessons.append(meta)

    print(format_output("ok", data={
        "target": args.target,
        "target_type": target_type,
        "lessons": lessons,
        "count": len(lessons),
    }))


if __name__ == "__main__":
    main()
