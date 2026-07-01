#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：写入/修改原始记录到 lesson 文件

输入：
  --vault         Vault 根目录
  --target        班级名或一对一学员名（必填）
  --lesson-num    课次号（必填）
  --student       学员姓名（可选，指定则写入该学员原始记录区域；否则写入班级级别）
  --records       JSON 数组格式的原始记录字符串（如 '["记录1", "记录2"]'）

输出（JSON）：
  {"status": "ok", "data": {"file": "...", "records_written": N}}
"""

import argparse
import sys
import os
import json
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xdf_utils import resolve_vault, resolve_target, read_md_file, format_output


def write_raw_records(lesson_file: Path, records: list[str], student: str | None = None) -> int:
    """
    将原始记录写入 lesson 文件的 ### 原始记录 区域。
    - 如果指定 student，写入该学员 #### 学员名 子区域
    - 否则写入班级级别区域（### 原始记录 下，#### 之前）
    返回写入的记录条数。
    """
    content, fm = read_md_file(lesson_file)
    if not content:
        return 0

    section_marker = "### 原始记录"
    lines = content.split("\n")
    new_lines = []
    in_raw_section = False
    records_written = 0
    inserted = False
    in_target_subsection = False

    # 构建要插入的记录行
    record_lines = [f"- {r}" for r in records]

    if student:
        # 在指定学员的 #### 学员名 子区域下添加记录
        student_header = f"#### {student}"

        for i, line in enumerate(lines):
            stripped = line.strip()

            # 进入原始记录区域
            if stripped == section_marker:
                in_raw_section = True
                new_lines.append(line)
                continue

            # 离开原始记录区域（遇到下一个 ### 标题）
            if in_raw_section and re.match(r"^###\s", stripped):
                # 如果还没插入，说明没找到目标学员，在区域末尾添加
                if not inserted:
                    # 找到该学员，创建子区域
                    new_lines.append(student_header)
                    new_lines.extend(record_lines)
                    new_lines.append("")
                    records_written = len(records)
                    inserted = True
                in_raw_section = False
                new_lines.append(line)
                continue

            if in_raw_section:
                # 检查是否是目标学员的 #### 标题
                if stripped == student_header:
                    in_target_subsection = True
                    new_lines.append(line)
                    # 在标题后立即插入记录
                    new_lines.extend(record_lines)
                    records_written = len(records)
                    inserted = True
                    continue

                # 如果是 #### 标题但不是目标的，结束目标子区域
                if re.match(r"^####\s", stripped):
                    in_target_subsection = False

                # 如果当前不在目标子区域，且之前没插入过，说明学员不存在，在末尾创建
                if not in_target_subsection and not inserted:
                    # 检查是否是原始记录区域的末尾（后面没有更多内容或遇到空行后接其他内容）
                    pass

                new_lines.append(line)
                continue

            new_lines.append(line)

        # 如果遍历完还没插入（学员子区域不存在），在原始记录末尾追加
        if not inserted:
            # 重新处理：在原始记录区域末尾添加学员子区域
            new_lines = []
            in_raw_section = False
            raw_section_ended = False

            for line in lines:
                stripped = line.strip()

                if stripped == section_marker:
                    in_raw_section = True
                    new_lines.append(line)
                    continue

                if in_raw_section and re.match(r"^###\s", stripped):
                    in_raw_section = False
                    if not inserted:
                        # 在区域末尾追加
                        new_lines.append("")
                        new_lines.append(student_header)
                        new_lines.extend(record_lines)
                        records_written = len(records)
                        inserted = True
                    new_lines.append(line)
                    continue

                new_lines.append(line)

            # 文件末尾都没有插入（原始记录在文件最后）
            if not inserted:
                new_lines.append("")
                new_lines.append(student_header)
                new_lines.extend(record_lines)
                records_written = len(records)

    else:
        # 班级级别：写入 ### 原始记录 下，第一个 #### 之前的区域
        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped == section_marker:
                in_raw_section = True
                new_lines.append(line)
                # 在标题后立即插入记录
                new_lines.extend(record_lines)
                records_written = len(records)
                inserted = True
                continue

            if in_raw_section and re.match(r"^###\s", stripped):
                in_raw_section = False
                new_lines.append(line)
                continue

            new_lines.append(line)

        # 如果没找到原始记录区域，追加到文件末尾
        if not inserted:
            new_lines.append("")
            new_lines.append(section_marker)
            new_lines.extend(record_lines)
            records_written = len(records)

    lesson_file.write_text("\n".join(new_lines), encoding="utf-8")
    return records_written


def main():
    parser = argparse.ArgumentParser(description="写入/修改原始记录到 lesson 文件")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", required=True, help="班级名或一对一学员名")
    parser.add_argument("--lesson-num", required=True, type=int, help="课次号")
    parser.add_argument("--student", default=None, help="学员姓名（可选）")
    parser.add_argument("--records", required=True, help="JSON 数组格式的原始记录字符串")
    args = parser.parse_args()

    # 解析 records JSON
    try:
        records = json.loads(args.records)
        if not isinstance(records, list):
            raise ValueError("--records 必须是 JSON 数组")
    except (json.JSONDecodeError, ValueError) as e:
        print(format_output("error", error=f"--records 解析失败: {e}"))
        sys.exit(1)

    if not records:
        print(format_output("error", error="记录列表不能为空"))
        sys.exit(1)

    # 解析 vault
    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    # 定位 lesson 文件
    try:
        target_path = resolve_target(vault, args.target)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    lesson_dir = target_path / f"{args.target} Lesson {args.lesson_num}"
    if not lesson_dir.exists():
        print(format_output("error", error=f"课次目录不存在: {lesson_dir}"))
        sys.exit(1)

    lesson_file = lesson_dir / f"{args.target} Lesson {args.lesson_num}.md"
    if not lesson_file.exists():
        print(format_output("error", error=f"Lesson 文件不存在: {lesson_file}"))
        sys.exit(1)

    # 写入原始记录
    count = write_raw_records(lesson_file, records, args.student)

    print(format_output("ok", data={
        "file": str(lesson_file),
        "records_written": count,
    }))


if __name__ == "__main__":
    main()
