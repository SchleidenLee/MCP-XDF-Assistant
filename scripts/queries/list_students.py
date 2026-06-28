#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：列出指定班级中的学员

输入：
  --vault    Vault 根目录
  --class    班级名称（必填，如 3164）

输出（JSON）：
  status: ok | error
  data:
    class_name: "3164"
    students: [
      {
        "姓名": "艾克丹",
        "学校": "",
        "年级": "",
        "英语程度": "",
        "目标分数": "",
        "已上课程": "",
        "备注": ""
      }
    ]
"""

import argparse
import sys
from pathlib import Path

from xdf_utils import resolve_vault, read_md_file, extract_table_rows, format_output


def main():
    parser = argparse.ArgumentParser(description="列出班级学员")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--class", dest="class_name", required=True, help="班级名称")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    class_dir = vault / args.class_name
    control_file = class_dir / f"{args.class_name}.md"

    if not control_file.exists():
        print(format_output("error", error=f"班级 '{args.class_name}' 不存在"))
        sys.exit(1)

    content, fm = read_md_file(control_file)
    students = extract_table_rows(content, "姓名")

    print(format_output("ok", data={
        "class_name": args.class_name,
        "students": students,
        "count": len(students),
    }))


if __name__ == "__main__":
    main()
