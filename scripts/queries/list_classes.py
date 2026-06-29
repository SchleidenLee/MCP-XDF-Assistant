#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：列出所有进行中的班课档案

输入：
  --vault    Vault 根目录

输出（JSON）：
  status: ok | error
  data:
    classes: [
      {
        "name": "3164",
        "course_type": "初级讲义",
        "schedule_type": "weekend",
        "student_count": 5
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
    extract_table_rows,
    list_lesson_dirs,
    is_class_folder,
    format_output,
)


def main():
    parser = argparse.ArgumentParser(description="列出所有进行中的班课")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    classes = []

    # 搜索目录：Vault 根目录 + Current Class + Archived
    search_dirs = [vault]
    for subdir_name in ["Current Class", "Archived"]:
        subdir = vault / subdir_name
        if subdir.is_dir():
            search_dirs.append(subdir)

    for search_dir in search_dirs:
        for sub in search_dir.iterdir():
            if not sub.is_dir():
                continue

            if not is_class_folder(sub):
                continue

            target_name = sub.name
            control_file = sub / f"{target_name}.md"
            content, fm = read_md_file(control_file)

            course_type = ""
            schedule_type = ""

            if fm:
                course_type_list = fm.get("course_type", [])
                if isinstance(course_type_list, list):
                    course_type = ", ".join(str(c) for c in course_type_list)
                else:
                    course_type = str(course_type_list)
                schedule_type = fm.get("schedule_type", "")

            # 统计学员数
            rows = extract_table_rows(content, "姓名")
            student_count = len([r for r in rows if r.get("姓名", "").strip()])

            classes.append({
                "name": target_name,
                "course_type": course_type,
                "schedule_type": schedule_type,
                "student_count": student_count,
            })

    classes.sort(key=lambda x: x["name"])
    print(format_output("ok", data={"classes": classes}))


if __name__ == "__main__":
    main()
