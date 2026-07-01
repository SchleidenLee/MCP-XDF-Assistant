#!/usr/bin/env python3
"""
一对一每课记录创建脚本
Replicates Obsidian QuickAdd script: 一对一每课记录1.js
Creates lesson record files for a one-on-one student, one lesson per date provided.
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
    format_output,
    list_lesson_dirs,
)


# 预设时间点映射（课次号 → 时间，一对一有5个时段）
SCHEDULE_TIMES = {
    1: "10:00",
    2: "12:20",
    3: "15:30",
    4: "17:50",
    5: "20:10",
}


def get_time_for_lesson(lesson_num: int, time_str: str | None = None) -> str:
    """根据课次号获取预设时间，如果传了指定时间则用指定的。"""
    if time_str and time_str != "00:00":
        return time_str
    return SCHEDULE_TIMES.get(lesson_num, "10:00")


def get_next_lesson_number(student_folder: Path, student_name: str) -> int:
    """Scan existing lesson dirs for max lesson number, return max+1."""
    existing = list_lesson_dirs(student_folder, student_name)
    max_num = 0
    pattern = re.compile(re.escape(student_name) + r"\s+Lesson\s+(\d+)", re.IGNORECASE)
    for d in existing:
        m = pattern.match(d.name)
        if m:
            n = int(m.group(1))
            if n > max_num:
                max_num = n
    return max_num + 1


def get_course_types(archive_path: Path) -> list[str]:
    """Extract course_type list from archive frontmatter."""
    _, fm = read_md_file(archive_path)
    ct = fm.get("course_type", [])
    if isinstance(ct, str):
        return [ct]
    return ct


def get_course_type_from_archive(archive_path: Path) -> str | None:
    """Get the last course_type from archive, or None."""
    course_types = get_course_types(archive_path)
    if course_types:
        return course_types[-1]
    return None


def generate_nav_content(
    student_name: str,
    lesson_number: int,
    next_lesson: int,
    date_iso: str,
    month: int,
    day: int,
    course_type: str,
) -> str:
    """Generate the navigation/main lesson file content."""
    month_day = f"{month}月{day}日"

    return f"""---
Date: {date_iso}
course_type:
  - {course_type}
tags:
  - "#课程记录"
need_send_feedback: true
archive: "[[{student_name}|📁 档案首页]]"
---
## 📂本节课文件
- [[Note {lesson_number}|📝 课堂笔记]]
- [[Wordlist {lesson_number}|📚 词汇表]]
- [[Grammar Note {lesson_number}|📖 语法笔记]]
- [[Homework {lesson_number}|✍️ 课后作业]]
- [[Quiz {next_lesson}|📋 下节课入门测]]
---
## 📝 学员反馈
- [ ] 提交反馈
- [[Feedback {lesson_number}|💬 课堂反馈]]
### 授课内容

---
## ✍️作业记录
- [ ] 发送作业到家长群
{month_day}阅读作业：

---
## 📌 下次课提醒

- [ ] 准备打印作业
- [ ] 准备入门测

"""


def generate_feedback_content(student_name: str) -> str:
    """Generate the feedback file content."""
    return f"""## 👤 {student_name}


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


def update_one_on_one_archive(
    archive_path: Path,
    student_name: str,
    lesson_number: int,
    lesson_folder_name: str,
    date_str: str,
    course_type: str,
    is_new_tag: bool,
) -> None:
    """Update the one-on-one archive file with lesson link and metadata."""
    content, fm = read_md_file(archive_path)
    if not content:
        return

    new_link = f"- [[{lesson_folder_name}|第 {lesson_number} 课 - {date_str}]]"

    if is_new_tag:
        # Append new course_type to frontmatter course_type list
        new_course_type_line = f'  - "{course_type}"'
        lines = content.split("\n")
        in_course_type_section = False
        last_course_type_index = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "course_type:":
                in_course_type_section = True
                continue
            if in_course_type_section:
                if stripped.startswith("- "):
                    last_course_type_index = i
                elif stripped == "---" or (stripped and not stripped.startswith("-")):
                    break

        if last_course_type_index != -1:
            lines.insert(last_course_type_index + 1, new_course_type_line)
            content = "\n".join(lines)

        # Add new tag block in 课程索引 section
        target_header = "## 📚 课程索引"
        header_pos = content.find(target_header)
        if header_pos != -1:
            section_end_marker = content.find("## 📝 考试记录", header_pos)
            section_end = section_end_marker if section_end_marker != -1 else len(content)
            section_content = content[header_pos:section_end]

            last_divider = section_content.rfind("---")
            if last_divider != -1:
                insert_pos = header_pos + last_divider + 3
                new_block = f"\n\n### 🏷️ {course_type}\n{new_link}\n\n---\n"
                content = content[:insert_pos] + new_block + content[insert_pos:]
    else:
        # Add link before first "---" in existing tag block
        target_header = f"### 🏷️ {course_type}"
        header_pos = content.find(target_header)
        if header_pos != -1:
            after_header = content[header_pos:]
            first_divider = after_header.find("\n---")
            if first_divider != -1:
                insert_pos = header_pos + first_divider
                content = content[:insert_pos] + "\n" + new_link + content[insert_pos:]

    # Always update total_lessons and last_lesson_date
    content = re.sub(
        r"(total_lessons:\s*)\d+", f"\\g<1>{lesson_number}", content
    )
    content = re.sub(
        r'(last_lesson_date:\s*)(null|"[^"]*")', f'\\g<1>"{date_str}"', content
    )

    archive_path.write_text(content, encoding="utf-8")


def create_one_on_one_lesson(
    vault_path: str | None,
    student: str,
    dates: list[str],
    time_slots: list[int] | None,
    course_type: str | None,
) -> str:
    try:
        vault = resolve_vault(vault_path)

        student_folder = vault / "Current Class" / student
        if not student_folder.exists():
            return format_output("error", error=f"学员文件夹不存在: {student}")

        archive_path = student_folder / f"{student}.md"
        if not archive_path.exists():
            return format_output("error", error=f"学员档案文件不存在: {archive_path}")

        # Get course_type if not provided
        is_new_tag = False
        if course_type:
            # Check if this course_type already exists
            existing_types = get_course_types(archive_path)
            is_new_tag = course_type not in existing_types
        else:
            course_type = get_course_type_from_archive(archive_path)
            if not course_type:
                return format_output("error", error="未指定课程体系，且档案中无课程体系标签")
            is_new_tag = False

        # Calculate starting lesson number
        lesson_number = get_next_lesson_number(student_folder, student)

        created_lessons = []

        for i, date_time_str in enumerate(dates):
            date_time_str = date_time_str.strip()
            if " " in date_time_str:
                date_part, time_part = date_time_str.split(" ", 1)
            else:
                date_part = date_time_str
                time_part = None

            # 优先使用传入的时间段索引
            slot_index = None
            if time_slots and i < len(time_slots):
                slot_index = time_slots[i]
            
            if slot_index and slot_index in SCHEDULE_TIMES:
                time_part = SCHEDULE_TIMES[slot_index]
            elif not time_part:
                # Fallback to lesson number mapping if no time provided (legacy behavior)
                time_part = get_time_for_lesson(lesson_number)

            # ISO datetime (China timezone +08:00)
            date_iso = f"{date_part}T{time_part}:00+08:00"

            # Month/day without leading zeros
            parts = date_part.split("-")
            month, day = int(parts[1]), int(parts[2])

            next_lesson = lesson_number + 1
            lesson_folder_name = f"{student} Lesson {lesson_number}"
            lesson_folder = student_folder / lesson_folder_name
            lesson_folder.mkdir(parents=True, exist_ok=True)

            # File 1: Navigation
            nav_content = generate_nav_content(
                student, lesson_number, next_lesson,
                date_iso, month, day, course_type,
            )
            nav_path = lesson_folder / f"{student} Lesson {lesson_number}.md"
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
            fb_content = generate_feedback_content(student)
            fb_path = lesson_folder / f"Feedback {lesson_number}.md"
            fb_path.write_text(fb_content, encoding="utf-8")

            # Update archive (only for the last lesson's number and tag status)
            # For multiple dates, we update incrementally
            update_one_on_one_archive(
                archive_path, student, lesson_number, lesson_folder_name,
                date_part, course_type, is_new_tag,
            )

            created_lessons.append({
                "lesson_number": lesson_number,
                "folder": str(lesson_folder),
                "date": date_part,
            })

            # After first lesson of a new tag, subsequent lessons are no longer "new tag"
            if is_new_tag:
                is_new_tag = False

            lesson_number += 1

        return format_output(
            "success",
            data={
                "student_name": student,
                "lessons_created": created_lessons,
                "course_type": course_type,
            },
        )
    except Exception as e:
        return format_output("error", error=str(e))


def main():
    parser = argparse.ArgumentParser(description="一对一每课记录创建")
    parser.add_argument("--vault", default=None, help="Vault path")
    parser.add_argument("--student", required=True, help="Student name")
    parser.add_argument(
        "--dates",
        required=True,
        nargs="+",
        help='Lesson dates (e.g. "2026-06-21 10:00" "2026-06-22 12:20")',
    )
    parser.add_argument(
        "--time-slots",
        type=int,
        nargs="+",
        default=None,
        help="Time slot indices (1-5) for each date. 1=10:00, 2=12:20... Overrides time in dates.",
    )
    parser.add_argument(
        "--course-type",
        default=None,
        help="Course type (optional, read from archive if not provided)",
    )

    args = parser.parse_args()
    result = create_one_on_one_lesson(
        vault_path=args.vault,
        student=args.student,
        dates=args.dates,
        time_slots=args.time_slots,
        course_type=args.course_type,
    )
    print(result)


if __name__ == "__main__":
    main()
