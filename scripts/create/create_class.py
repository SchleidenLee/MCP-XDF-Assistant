#!/usr/bin/env python3
"""
班课档案创建脚本
Replicates Obsidian QuickAdd script: 班课档案1.js
Creates a class archive folder and markdown file with student roster.
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xdf_utils import resolve_vault, format_output


DEFAULT_TIME = "10:00"


def create_class(
    vault_path: str | None,
    class_name: str,
    first_class_date: str,
    first_class_time: str | None = None,
    schedule_type: str = "weekend",
    course_type: str = "",
    students: str = "",
) -> str:
    try:
        vault = resolve_vault(vault_path)

        # Default time to 10:00 if not provided
        if not first_class_time:
            first_class_time = DEFAULT_TIME

        student_list = [s.strip() for s in students.split(",") if s.strip()]
        if not student_list:
            return format_output("error", error="学员名单不能为空")

        # Create class folder in Current Class/
        class_folder = vault / "Current Class" / class_name
        class_folder.mkdir(parents=True, exist_ok=True)

        # Generate student table rows
        student_rows = "\n".join(
            f"| {name} | | | | | | |" for name in student_list
        )

        # Build archive content
        content = f"""---
first_class_time: "{first_class_date} {first_class_time}"
schedule_type: "{schedule_type}"
course_type:
  - "{course_type}"
tags: ["#班课档案"]
status: "active"
student_count: {len(student_list)}
last_lesson_date: null
---

## 👥 学员名单

| 姓名 | 学校 | 年级 | 英语程度 | 目标分数 | 已上课程 | 考试时间 | 考试成绩 | 备注 |
|------|------|------|----------|----------|----------|----------|----------|------|
{student_rows}

---

## 📝 班级备注
<!-- 在此记录班级注意事项 -->

---

## 📅 课程记录索引
<!-- 每次课后在这里增加课程链接 -->


---

## 📋 测试反馈
"""

        # Create archive file
        archive_file = class_folder / f"{class_name}.md"
        archive_file.write_text(content, encoding="utf-8")

        return format_output(
            "success",
            data={
                "class_name": class_name,
                "folder_path": str(class_folder),
                "archive_path": str(archive_file),
                "student_count": len(student_list),
                "students": student_list,
            },
        )
    except Exception as e:
        return format_output("error", error=str(e))


def main():
    parser = argparse.ArgumentParser(description="班课档案创建")
    parser.add_argument("--vault", default=None, help="Vault path")
    parser.add_argument("--class-name", required=True, help="Class name (e.g. 3164)")
    parser.add_argument(
        "--first-class-date", required=True, help="First class date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--first-class-time", default=None, help="First class time (HH:MM), default 10:00"
    )
    parser.add_argument(
        "--schedule-type",
        required=True,
        choices=["weekend", "full-time"],
        help="Schedule type",
    )
    parser.add_argument("--course-type", required=True, help="Course type (e.g. L2教材)")
    parser.add_argument(
        "--students", required=True, help="Comma-separated student names"
    )

    args = parser.parse_args()
    result = create_class(
        vault_path=args.vault,
        class_name=args.class_name,
        first_class_date=args.first_class_date,
        first_class_time=args.first_class_time,
        schedule_type=args.schedule_type,
        course_type=args.course_type,
        students=args.students,
    )
    print(result)


if __name__ == "__main__":
    main()
