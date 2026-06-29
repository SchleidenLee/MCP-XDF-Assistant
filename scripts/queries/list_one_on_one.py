#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：列出所有一对一学员

输入：
  --vault    Vault 根目录

输出（JSON）：
  status: ok | error
  data:
    students: [
      {
        "name": "许宸睿",
        "path": "...",
        "lesson_count": 1,
        "course_type": "L2教材",
        "schedule_type": "full-time",
        "status": "active",
        "total_lessons": 1,
        "last_lesson_date": "2026-06-22"
      }
    ]
"""

import argparse
import sys
from pathlib import Path

from xdf_utils import (
    resolve_vault,
    resolve_target,
    read_md_file,
    list_lesson_dirs,
    format_output,
    is_one_on_one_folder,
)


def main():
    parser = argparse.ArgumentParser(description="列出所有一对一学员")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    students = []
    # 搜索目录：Vault 根目录 + Current Class + Archived
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

            if not is_one_on_one_folder(sub):
                continue

            control_file = sub / f"{target_name}.md"
            _, fm = read_md_file(control_file)

            lessons = list_lesson_dirs(sub, target_name)

            # 提取课型标签
            tags = fm.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]
            course_tags = [
                t.lstrip("#") for t in tags
                if t and "学员档案" not in t and "一对一" not in t
            ]
            course_type = course_tags[0] if course_tags else ""

            students.append({
                "name": target_name,
                "path": str(sub),
                "lesson_count": len(lessons),
                "course_type": course_type,
                "schedule_type": fm.get("schedule_type", ""),
                "status": fm.get("status", ""),
                "total_lessons": int(fm.get("total_lessons", 0) or 0),
                "last_lesson_date": fm.get("last_lesson_date", ""),
            })

    students.sort(key=lambda x: x["name"])
    print(format_output("ok", data={"students": students, "count": len(students)}))


if __name__ == "__main__":
    main()
