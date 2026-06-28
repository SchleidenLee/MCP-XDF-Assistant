#!/usr/bin/env python3
"""
班课每课记录创建脚本
Replicates Obsidian QuickAdd script: 班课每课记录1.js
Creates lesson record files for a class, one lesson per date provided.
"""

import argparse
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
from xdf_utils import (
    resolve_vault,
    read_md_file,
    parse_frontmatter,
    extract_table_rows,
    format_output,
    list_lesson_dirs,
)


# 预设时间点映射（课次号 → 时间）
SCHEDULE_TIMES = {
    1: "10:00",
    2: "12:20",
    3: "15:30",
    4: "17:50",
}


def get_time_for_lesson(lesson_num: int, time_str: str | None = None) -> str:
    """根据课次号获取预设时间，如果传了指定时间则用指定的。"""
    if time_str and time_str != "00:00":
        return time_str
    return SCHEDULE_TIMES.get(lesson_num, "10:00")


def get_next_lesson_number(class_folder: Path, class_name: str) -> int:
    """Scan archive and existing lesson dirs for max lesson number, return max+1."""
    archive = class_folder / f"{class_name}.md"
    max_num = 0

    # Scan archive file for "Lesson N" pattern
    if archive.exists():
        content, _ = read_md_file(archive)
        matches = re.findall(r"Lesson\s+(\d+)", content)
        for m in matches:
            n = int(m)
            if n > max_num:
                max_num = n

    # Also check existing lesson directories
    existing = list_lesson_dirs(class_folder, class_name)
    for d in existing:
        m = re.match(re.escape(class_name) + r"\s+Lesson\s+(\d+)", d.name, re.IGNORECASE)
        if m:
            n = int(m.group(1))
            if n > max_num:
                max_num = n

    return max_num + 1


def get_course_type_from_archive(archive_path: Path) -> str:
    """Read the last curriculum tag from archive frontmatter."""
    content, fm = read_md_file(archive_path)
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    # Filter out fixed tags, return last curriculum tag
    course_tags = [t for t in tags if "#班课档案" not in t]
    if course_tags:
        return course_tags[-1].lstrip("#")
    return "班课"


def get_schedule_type_from_archive(archive_path: Path) -> str:
    """Read schedule_type from archive frontmatter."""
    _, fm = read_md_file(archive_path)
    return fm.get("schedule_type", "full-time")


def get_students_from_archive(class_folder: Path, class_name: str) -> list[str]:
    """Parse student names from the archive markdown table."""
    archive = class_folder / f"{class_name}.md"
    if not archive.exists():
        return []
    content, _ = read_md_file(archive)
    rows = extract_table_rows(content, "姓名")
    return [row.get("姓名", "").strip() for row in rows if row.get("姓名", "").strip()]


def generate_nav_content(
    class_name: str,
    lesson_number: int,
    next_lesson: int,
    date_iso: str,
    date_str: str,
    month: int,
    day: int,
    course_type: str,
    need_send_feedback: bool,
) -> str:
    """Generate the navigation/main lesson file content."""
    need_fb_str = "true" if need_send_feedback else "false"
    month_day = f"{month}月{day}日"

    return f"""---
Date: {date_iso}
course_type:
  - {course_type}
tags:
  - "#课程记录"
need_send_feedback: {need_fb_str}
archive: "[[{class_name}|📁 档案首页]]"
---
## 📂本节课文件
- [[Note {lesson_number}|📝 课堂笔记]]
- [[Wordlist {lesson_number}|📚 词表]]
- [[Grammar Note {lesson_number}|📖 语法笔记]]
- [[Homework {lesson_number}|✍️ 课后作业]]
- [[Quiz {next_lesson}|📋 下节课入门测]]
- [[Feedback {lesson_number}|💬 学员反馈]]
---
## 📝 班级反馈
- [ ] 提交反馈
- [[Feedback {lesson_number}|💬 学员反馈]]

### 授课内容



### 原始记录

#### 出勤



#### 整体表现



#### 作业情况



#### 入门测情况



#### 授课进度


### 反馈总结
<!-- AI_GENERATED_START -->
待生成
<!-- AI_GENERATED_END -->

---

## ✍️作业记录
- [ ] 发送作业到家长群
{month_day}阅读作业：


---
## 📌 下次课提醒

- [ ] 准备打印作业
- [ ] 准备入门测

"""


def generate_feedback_content(students: list[str]) -> str:
    """Generate the feedback file content with sections for each student."""
    sections = []
    for student in students:
        section = f"""## 👤 {student}

### 原始记录

#### 出勤


#### 作业情况


#### 入门测情况


#### 课堂表现


#### 掌握情况


#### 需要加强


### 反馈总结
<!-- AI_GENERATED_START -->
待生成

<!-- AI_GENERATED_END -->

"""
        sections.append(section)
    return "\n".join(sections)


def update_class_archive(
    archive_path: Path,
    class_name: str,
    lesson_number: int,
    lesson_folder_name: str,
    date_str: str,
) -> None:
    """Update the class archive file with lesson link and metadata."""
    content, fm = read_md_file(archive_path)
    if not content:
        return

    lesson_link = f"- [[{lesson_folder_name}|📖 Lesson {lesson_number} - {date_str}]]"

    # Check if link already exists
    if lesson_link not in content:
        # Insert before "\n---" under "## 📅 课程记录索引"
        index_header = "## 📅 课程记录索引"
        header_pos = content.find(index_header)
        if header_pos != -1:
            after_header = content[header_pos:]
            divider_pos = after_header.find("\n---")
            if divider_pos != -1:
                insert_pos = header_pos + divider_pos
                content = content[:insert_pos] + "\n" + lesson_link + content[insert_pos:]

        # Update total_lessons and last_lesson_date in frontmatter
        content = re.sub(
            r"(total_lessons:\s*)\d+", f"\\g<1>{lesson_number}", content
        )
        content = re.sub(
            r'(last_lesson_date:\s*)(null|"[^"]*")', f'\\g<1>"{date_str}"', content
        )

        archive_path.write_text(content, encoding="utf-8")


def create_class_lesson(
    vault_path: str | None,
    class_name: str,
    dates: list[str],
    course_type: str | None,
) -> str:
    try:
        vault = resolve_vault(vault_path)

        class_folder = vault / "Current Class" / class_name
        if not class_folder.exists():
            return format_output("error", error=f"班级文件夹不存在: {class_name}")

        archive_path = class_folder / f"{class_name}.md"
        if not archive_path.exists():
            return format_output("error", error=f"班级档案文件不存在: {archive_path}")

        # Get students from archive
        students = get_students_from_archive(class_folder, class_name)

        # Get schedule_type for feedback calculation
        schedule_type = get_schedule_type_from_archive(archive_path)

        # Get course_type if not provided
        if not course_type:
            course_type = get_course_type_from_archive(archive_path)

        # Calculate starting lesson number
        lesson_number = get_next_lesson_number(class_folder, class_name)

        created_lessons = []

        for date_time_str in dates:
            # Parse date and time
            date_time_str = date_time_str.strip()
            if " " in date_time_str:
                date_part, time_part = date_time_str.split(" ", 1)
            else:
                date_part = date_time_str
                time_part = None

            # Get preset time based on lesson number
            time_part = get_time_for_lesson(lesson_number, time_part)

            # Calculate ISO datetime (China timezone +08:00)
            date_iso = f"{date_part}T{time_part}:00+08:00"

            # Extract month/day without leading zeros
            parts = date_part.split("-")
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])

            # Determine need_send_feedback
            need_send_feedback = schedule_type == "weekend" or lesson_number % 2 == 0

            next_lesson = lesson_number + 1
            lesson_folder_name = f"{class_name} Lesson {lesson_number}"
            lesson_folder = class_folder / lesson_folder_name
            lesson_folder.mkdir(parents=True, exist_ok=True)

            # File 1: Navigation
            nav_content = generate_nav_content(
                class_name, lesson_number, next_lesson,
                date_iso, date_part, month, day,
                course_type, need_send_feedback,
            )
            nav_path = lesson_folder / f"{class_name} Lesson {lesson_number}.md"
            nav_path.write_text(nav_content, encoding="utf-8")

            # Files 2-6: Empty
            empty_files = [
                f"Note {lesson_number}.md",
                f"Wordlist {lesson_number}.md",
                f"Grammar Note {lesson_number}.md",
                f"Homework {lesson_number}.md",
                f"Quiz {next_lesson}.md",
            ]
            for fname in empty_files:
                (lesson_folder / fname).write_text("", encoding="utf-8")

            # File 7: Feedback
            fb_content = generate_feedback_content(students)
            fb_path = lesson_folder / f"Feedback {lesson_number}.md"
            fb_path.write_text(fb_content, encoding="utf-8")

            # Update archive
            update_class_archive(archive_path, class_name, lesson_number, lesson_folder_name, date_part)

            created_lessons.append({
                "lesson_number": lesson_number,
                "folder": str(lesson_folder),
                "date": date_part,
            })

            lesson_number += 1

        return format_output(
            "success",
            data={
                "class_name": class_name,
                "lessons_created": created_lessons,
                "course_type": course_type,
                "students": students,
            },
        )
    except Exception as e:
        return format_output("error", error=str(e))


def main():
    parser = argparse.ArgumentParser(description="班课每课记录创建")
    parser.add_argument("--vault", default=None, help="Vault path")
    parser.add_argument("--class", dest="class_name", required=True, help="Class name")
    parser.add_argument(
        "--dates",
        required=True,
        nargs="+",
        help='Lesson dates (e.g. "2026-06-21 10:00" "2026-06-22 12:20")',
    )
    parser.add_argument(
        "--course-type",
        default=None,
        help="Course type (optional, read from archive if not provided)",
    )

    args = parser.parse_args()
    result = create_class_lesson(
        vault_path=args.vault,
        class_name=args.class_name,
        dates=args.dates,
        course_type=args.course_type,
    )
    print(result)


if __name__ == "__main__":
    main()
