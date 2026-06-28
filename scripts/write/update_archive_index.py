#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：更新班级/一对一档案首页的课程记录索引

输入：
  --vault         Vault 根目录
  --target        班级名或一对一学员名（必填）
  --lesson-num    课次号（必填）
  --date          课程日期（YYYY-MM-DD）
  --action        add 或 remove（必填）

输出（JSON）：
  {"status": "ok", "data": {"file": "...", "updated": true}}
"""

import argparse
import re
import sys
from pathlib import Path

from xdf_utils import (
    resolve_vault,
    read_md_file,
    is_class_folder,
    is_one_on_one_folder,
    format_output,
)


def add_class_lesson_link(content: str, class_name: str, lesson_num: int, date_str: str) -> str:
    """在班课档案的 ## 📅 课程记录索引 区域添加课程链接"""
    lesson_folder = f"{class_name} Lesson {lesson_num}"
    lesson_link = f"- [[{lesson_folder}|📖 Lesson {lesson_num} - {date_str}]]"

    # 检查是否已存在
    if lesson_link in content:
        return content

    index_header = "## 📅 课程记录索引"
    header_pos = content.find(index_header)
    if header_pos == -1:
        return content

    after_header = content[header_pos:]
    divider_pos = after_header.find("\n---")
    if divider_pos == -1:
        # 没有分隔符，追加到区域末尾（遇到下一个 ## 或文件末尾）
        next_section = re.search(r"\n##\s", after_header)
        if next_section:
            insert_pos = header_pos + next_section.start()
        else:
            insert_pos = len(content)
        content = content[:insert_pos] + "\n" + lesson_link + content[insert_pos:]
    else:
        # 在 --- 之前插入
        insert_pos = header_pos + divider_pos
        content = content[:insert_pos] + "\n" + lesson_link + content[insert_pos:]

    # 更新 last_lesson_date
    content = re.sub(
        r'(last_lesson_date:\s*)(null|"[^"]*")', f'\\g<1>"{date_str}"', content
    )

    return content


def remove_class_lesson_link(content: str, class_name: str, lesson_num: int) -> str:
    """从班课档案的 ## 📅 课程记录索引 区域移除课程链接"""
    lesson_folder = f"{class_name} Lesson {lesson_num}"
    lesson_link = f"- [[{lesson_folder}|📖 Lesson {lesson_num} - "

    lines = content.split("\n")
    new_lines = []
    for line in lines:
        if lesson_link in line and lesson_folder in line:
            continue  # 跳过要删除的行
        new_lines.append(line)

    return "\n".join(new_lines)


def add_one_on_one_lesson_link(
    content: str, student_name: str, lesson_num: int, date_str: str
) -> str:
    """在一对一档案的 ## 📅 课程记录索引 区域添加课程链接"""
    lesson_folder = f"{student_name} Lesson {lesson_num}"
    new_link = f"- [[{lesson_folder}|第 {lesson_num} 课 - {date_str}]]"

    # 检查是否已存在
    if new_link in content:
        return content

    # 尝试在 ## 📅 课程记录索引 区域添加
    index_header = "## 📅 课程记录索引"
    header_pos = content.find(index_header)

    if header_pos != -1:
        after_header = content[header_pos:]
        # 找到区域末尾（下一个 ## 标题或 --- 或文件末尾）
        next_section = re.search(r"\n##\s", after_header[len("## 📅 课程记录索引"):])
        if next_section:
            insert_pos = header_pos + len("## 📅 课程记录索引") + next_section.start()
        else:
            insert_pos = len(content)
        content = content[:insert_pos] + "\n" + new_link + content[insert_pos:]
    else:
        # 退而求其次，追加到文件末尾
        content += f"\n## 📅 课程记录索引\n{new_link}\n"

    # 更新 last_lesson_date
    content = re.sub(
        r'(last_lesson_date:\s*)(null|"[^"]*")', f'\\g<1>"{date_str}"', content
    )

    return content


def remove_one_on_one_lesson_link(content: str, student_name: str, lesson_num: int) -> str:
    """从一对一档案的 ## 📅 课程记录索引 区域移除课程链接"""
    lesson_folder = f"{student_name} Lesson {lesson_num}"
    lesson_link = f"- [[{lesson_folder}|第 {lesson_num} 课 - "

    lines = content.split("\n")
    new_lines = []
    for line in lines:
        if lesson_link in line and lesson_folder in line:
            continue  # 跳过要删除的行
        new_lines.append(line)

    return "\n".join(new_lines)


def main():
    parser = argparse.ArgumentParser(description="更新档案首页的课程记录索引")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", required=True, help="班级名或一对一学员名")
    parser.add_argument("--lesson-num", required=True, type=int, help="课次号")
    parser.add_argument("--date", type=str, default=None, help="课程日期（YYYY-MM-DD）")
    parser.add_argument("--action", required=True, choices=["add", "remove"], help="添加或移除索引")
    args = parser.parse_args()

    if args.action == "add" and not args.date:
        print(format_output("error", error="add 操作必须提供 --date"))
        sys.exit(1)

    # 日期格式校验
    if args.date and not re.match(r"^\d{4}-\d{2}-\d{2}$", args.date):
        print(format_output("error", error=f"日期格式错误: {args.date}，应为 YYYY-MM-DD"))
        sys.exit(1)

    # 解析 vault
    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    # 定位档案文件
    target_path = vault / args.target
    if not target_path.exists():
        print(format_output("error", error=f"目标 '{args.target}' 不存在"))
        sys.exit(1)

    # 判断目标类型
    target_type = None
    if is_class_folder(target_path):
        target_type = "class"
    elif is_one_on_one_folder(target_path):
        target_type = "one_on_one"
    else:
        print(format_output("error", error=f"目标 '{args.target}' 不是有效的班课或一对一档案"))
        sys.exit(1)

    # 定位档案主文件
    archive_file = target_path / f"{args.target}.md"
    if not archive_file.exists():
        print(format_output("error", error=f"档案文件不存在: {archive_file}"))
        sys.exit(1)

    content, fm = read_md_file(archive_file)
    if not content:
        print(format_output("error", error=f"档案文件内容为空: {archive_file}"))
        sys.exit(1)

    # 执行操作
    if args.action == "add":
        if target_type == "class":
            new_content = add_class_lesson_link(content, args.target, args.lesson_num, args.date)
        else:
            new_content = add_one_on_one_lesson_link(content, args.target, args.lesson_num, args.date)
    else:  # remove
        if target_type == "class":
            new_content = remove_class_lesson_link(content, args.target, args.lesson_num)
        else:
            new_content = remove_one_on_one_lesson_link(content, args.target, args.lesson_num)

    if new_content == content:
        print(format_output("ok", data={
            "file": str(archive_file),
            "updated": False,
        }))
        return

    archive_file.write_text(new_content, encoding="utf-8")

    print(format_output("ok", data={
        "file": str(archive_file),
        "updated": True,
    }))


if __name__ == "__main__":
    main()
