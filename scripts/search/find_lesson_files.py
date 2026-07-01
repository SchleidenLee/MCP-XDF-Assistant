#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：按课次号或日期搜索课次文件

输入：
  --vault        Vault 根目录
  --target       班级名或一对一学员名（必填，如 3164 / 许宸睿）
  --lesson       课次号（精确匹配）
  --date         日期（精确匹配，YYYY-MM-DD）
  --start-date   起始日期（YYYY-MM-DD，与 --end-date 配合使用）
  --end-date     结束日期（YYYY-MM-DD，与 --start-date 配合使用）

  --lesson、--date、--start-date/--end-date 至少指定一种

输出（JSON）：
  status: ok | error
  data:
    lessons: [
      {
        "lesson_num": 1,
        "date": "2026-03-15",
        "path": "...",
        "has_files": {"note": true, "wordlist": true, ...},
        "feedback_status": {...},
        "need_send_feedback": false
      }
    ]
"""

import argparse
import sys
import os
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xdf_utils import (
    resolve_vault,
    resolve_target,
    list_lesson_dirs,
    get_lesson_meta,
    is_class_folder,
    is_one_on_one_folder,
    format_output,
)


def main():
    parser = argparse.ArgumentParser(description="按课次号或日期搜索课次文件")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", required=True, help="班级名或一对一学员名")
    parser.add_argument("--lesson", type=int, default=None, help="课次号（精确匹配）")
    parser.add_argument("--date", type=str, default=None, help="日期（精确匹配，YYYY-MM-DD）")
    parser.add_argument("--start-date", type=str, default=None, help="起始日期（YYYY-MM-DD）")
    parser.add_argument("--end-date", type=str, default=None, help="结束日期（YYYY-MM-DD）")
    args = parser.parse_args()

    # 校验参数
    if not args.lesson and not args.date and not (args.start_date and args.end_date):
        print(format_output("error", error="请至少指定 --lesson、--date 或 --start-date/--end-date"))
        sys.exit(1)

    if (args.start_date and not args.end_date) or (args.end_date and not args.start_date):
        print(format_output("error", error="--start-date 和 --end-date 必须同时指定"))
        sys.exit(1)

    # 日期格式校验
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for d in [args.date, args.start_date, args.end_date]:
        if d and not date_pattern.match(d):
            print(format_output("error", error=f"日期格式错误: {d}，应为 YYYY-MM-DD"))
            sys.exit(1)

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

    target_type = "unknown"
    if is_class_folder(target_path):
        target_type = "class"
    elif is_one_on_one_folder(target_path):
        target_type = "one_on_one"

    lesson_dirs = list_lesson_dirs(target_path, args.target)
    lessons = []

    for lesson_dir in lesson_dirs:
        m = re.search(r"Lesson\s+(\d+)", lesson_dir.name, re.IGNORECASE)
        if not m:
            continue
        lesson_num = int(m.group(1))

        # 按课次号过滤
        if args.lesson is not None and lesson_num != args.lesson:
            continue

        # 读取日期用于日期过滤
        meta = get_lesson_meta(lesson_dir, args.target, lesson_num)
        lesson_date = meta.get("date")

        # 按日期精确匹配过滤
        if args.date and lesson_date != args.date:
            continue

        # 按日期范围过滤
        if args.start_date and args.end_date:
            if lesson_date is None or lesson_date < args.start_date or lesson_date > args.end_date:
                continue

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
