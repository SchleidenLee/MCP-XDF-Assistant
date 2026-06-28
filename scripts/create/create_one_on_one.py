#!/usr/bin/env python3
"""
一对一档案创建脚本
Replicates Obsidian QuickAdd script: 一对一建档1.js
Creates a one-on-one student archive folder and markdown file.
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xdf_utils import resolve_vault, format_output


DEFAULT_TIME = "10:00"


def create_one_on_one(
    vault_path: str | None,
    student: str,
    first_class_date: str,
    first_class_time: str | None = None,
    schedule_type: str = "full-time",
    course_type: str = "",
) -> str:
    try:
        vault = resolve_vault(vault_path)

        # Default time to 10:00 if not provided
        if not first_class_time:
            first_class_time = DEFAULT_TIME

        # Create student folder in Current Class/
        student_folder = vault / "Current Class" / student
        student_folder.mkdir(parents=True, exist_ok=True)

        # Build frontmatter tags as YAML list
        tags = ["#学员档案", "#一对一"]
        tags_yaml = "\n".join(f'  - "{tag}"' for tag in tags)

        frontmatter = f"""---
first_class_date: "{first_class_date} {first_class_time}"
course_type:
  - "{course_type}"
status: "active"
schedule_type: "{schedule_type}"
total_lessons: 0
tags:
{tags_yaml}
---
"""

        # Build body content
        body = f"""## 📚 课程索引

### 🏷️ {course_type}
- *暂无课程记录，等待生成第 1 课...*

---

## 📝 考试记录

| 次数 | 考试时间 | 考试成绩 |
|------|----------|----------|
| 第一次 | | |
| 第二次 | | |
| 第三次 | | |

---


## 📈 成长轨迹 (手动记录)
- **{first_class_date}**: 档案建立。


---

## 📋 测试反馈

## 📝 备注
"""

        full_content = frontmatter + body

        # Create archive file
        archive_file = student_folder / f"{student}.md"
        archive_file.write_text(full_content, encoding="utf-8")

        return format_output(
            "success",
            data={
                "student_name": student,
                "folder_path": str(student_folder),
                "archive_path": str(archive_file),
            },
        )
    except Exception as e:
        return format_output("error", error=str(e))


def main():
    parser = argparse.ArgumentParser(description="一对一档案创建")
    parser.add_argument("--vault", default=None, help="Vault path")
    parser.add_argument("--student", required=True, help="Student name")
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

    args = parser.parse_args()
    result = create_one_on_one(
        vault_path=args.vault,
        student=args.student,
        first_class_date=args.first_class_date,
        first_class_time=args.first_class_time,
        schedule_type=args.schedule_type,
        course_type=args.course_type,
    )
    print(result)


if __name__ == "__main__":
    main()
