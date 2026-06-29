#!/usr/bin/env python3
"""
测试反馈创建脚本
为班课/一对一新建测试反馈文件夹和文件，并在档案首页追加链接。
"""

import argparse
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xdf_utils import (
    resolve_vault,
    resolve_target,
    format_output,
    is_class_folder,
    is_one_on_one_folder,
)


def create_test_feedback(
    vault_path: str | None,
    target: str,
    test_name: str,
    test_date: str,
) -> str:
    try:
        vault = resolve_vault(vault_path)

        # 1. 查找档案
        try:
            target_path = resolve_target(vault, target)
        except FileNotFoundError:
            return format_output("error", error=f"未找到 {target} 的档案文件")

        archive_file = target_path / f"{target}.md"
        if not archive_file.exists():
            return format_output("error", error=f"未找到 {target} 的档案文件")

        is_class = is_class_folder(target_path)
        is_one_on_one = is_one_on_one_folder(target_path)
        archive_path = archive_file

        # 2. 读取档案内容获取学员名单（班课）
        content = archive_path.read_text(encoding="utf-8")
        students = []

        if is_class:
            # 解析学员表格
            lines = content.split("\n")
            in_table = False
            table_found = False
            for line in lines:
                if "## 👥 学员名单" in line:
                    in_table = True
                    continue
                if in_table and not table_found:
                    if line.startswith("|") and "------" in line:
                        table_found = True
                        continue
                if in_table and table_found and line.startswith("|"):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) > 2:
                        name = parts[1]
                        if name and name != "姓名":
                            students.append(name)
                    continue
                if in_table and table_found and line.strip() == "":
                    break

        if is_one_on_one:
            students = [target]

        if not students:
            return format_output("error", error="未找到学员名单")

        # 3. 创建测试反馈文件夹和文件
        archive_dir = archive_path.parent
        test_folder = archive_dir / test_name
        test_folder.mkdir(parents=True, exist_ok=True)

        test_file = test_folder / f"{test_name}.md"

        # 解析测试日期
        try:
            date_obj = datetime.strptime(test_date, "%Y-%m-%d")
            created_date = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            return format_output("error", error="测试日期格式错误，应为 YYYY-MM-DD")

        # 生成测试反馈内容
        student_blocks = "\n\n".join(
            f"### {s}\n- [ ] 参加结班测\n- [ ] 反馈已写完" for s in students
        )

        test_content = f"""---
tags: ["#测试反馈"]
test_name: "{test_name}"
test_date: "{created_date}"
student_count: {len(students)}
---

## 📋 {test_name}总览

{student_blocks}
"""
        test_file.write_text(test_content, encoding="utf-8")

        # 4. 在档案首页追加链接到「测试反馈」区块下
        link_line = f"- [[{test_name}/{test_name}|📝 {test_name}]]"
        if "## 📋 测试反馈" not in content:
            # 如果区块不存在，新建
            content += f"\n## 📋 测试反馈\n{link_line}\n"
        else:
            # 追加到区块末尾
            parts = content.split("## 📋 测试反馈", 1)
            after_section = parts[1].strip()
            if after_section:
                content = parts[0] + "## 📋 测试反馈\n" + after_section + "\n" + link_line
            else:
                content = parts[0] + "## 📋 测试反馈\n" + link_line + "\n"

        archive_path.write_text(content, encoding="utf-8")

        return format_output(
            "success",
            data={
                "target": target,
                "type": "class" if is_class else "one-on-one",
                "test_name": test_name,
                "test_file": str(test_file),
                "student_count": len(students),
                "students": students,
            },
        )
    except Exception as e:
        return format_output("error", error=str(e))


def main():
    parser = argparse.ArgumentParser(description="测试反馈创建")
    parser.add_argument("--vault", default=None, help="Vault path")
    parser.add_argument("--target", required=True, help="Class name or student name")
    parser.add_argument("--test-name", required=True, help="Test name (e.g. 结班测试)")
    parser.add_argument("--date", required=True, help="Test date (YYYY-MM-DD)")

    args = parser.parse_args()
    result = create_test_feedback(
        vault_path=args.vault,
        target=args.target,
        test_name=args.test_name,
        test_date=args.date,
    )
    print(result)


if __name__ == "__main__":
    main()
