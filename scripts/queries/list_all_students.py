#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：全局列出所有学员（班课+一对一去重）

输入：
  --vault    Vault 根目录

输出（JSON）：
  status: ok | error
  data:
    students: [
      {
        "name": "艾克丹",
        "sources": [
          {"type": "class", "target": "3164"}
        ],
        "lesson_count": 8,
        "last_lesson_date": "2026-06-21"
      }
    ]
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict

from xdf_utils import (
    resolve_vault,
    read_md_file,
    extract_table_rows,
    list_lesson_dirs,
    is_class_folder,
    is_one_on_one_folder,
    format_output,
)


def main():
    parser = argparse.ArgumentParser(description="全局列出所有学员")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    # 学员 -> 来源列表
    student_sources = defaultdict(list)
    student_lesson_count = defaultdict(int)
    student_last_date = defaultdict(lambda: None)

    for sub in vault.iterdir():
        if not sub.is_dir():
            continue

        target_name = sub.name
        if is_class_folder(sub):
            control_file = sub / f"{target_name}.md"
            content, _ = read_md_file(control_file)
            rows = extract_table_rows(content, "姓名")
            for row in rows:
                name = row.get("姓名", "").strip()
                if not name:
                    continue
                student_sources[name].append({"type": "class", "target": target_name})
        elif is_one_on_one_folder(sub):
            student_sources[target_name].append({"type": "one_on_one", "target": target_name})

        # 统计课次数和最后课次日期
        lesson_dirs = list_lesson_dirs(sub, target_name)
        for lesson_dir in lesson_dirs:
            lesson_file = lesson_dir / f"{target_name} Lesson {lesson_dir.name.split()[-1]}.md"
            date_str = None
            if lesson_file.exists():
                _, fm = read_md_file(lesson_file)
                date_raw = fm.get("Date", "")
                if date_raw:
                    import re
                    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(date_raw))
                    if m:
                        date_str = m.group(1)

            # 班课：给所有学员加课次
            if is_class_folder(sub):
                control_file = sub / f"{target_name}.md"
                content, _ = read_md_file(control_file)
                rows = extract_table_rows(content, "姓名")
                for row in rows:
                    name = row.get("姓名", "").strip()
                    if name:
                        student_lesson_count[name] += 1
                        if date_str and (not student_last_date[name] or date_str > student_last_date[name]):
                            student_last_date[name] = date_str
            else:
                # 一对一
                student_lesson_count[target_name] += 1
                if date_str and (not student_last_date[target_name] or date_str > student_last_date[target_name]):
                    student_last_date[target_name] = date_str

    students = []
    for name in sorted(student_sources.keys()):
        students.append({
            "name": name,
            "sources": student_sources[name],
            "lesson_count": student_lesson_count[name],
            "last_lesson_date": student_last_date[name],
        })

    print(format_output("ok", data={
        "students": students,
        "count": len(students),
    }))


if __name__ == "__main__":
    main()
