#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：写入反馈内容到 lesson 文件或 Feedback 文件

输入：
  --vault         Vault 根目录
  --target        班级名或一对一学员名（必填）
  --lesson-num    课次号（必填）
  --feedback-type class_feedback 或 student_feedback（必填）
  --content       反馈文本
  --student-name  学员姓名（student_feedback 时必填）
  --json-file     JSON 文件路径（可选，用于批量写入）

输出（JSON）：
  {"status": "ok", "data": {"file": "...", "updated": true}}
"""

import argparse
import json
import re
import sys
from pathlib import Path

from xdf_utils import resolve_vault, resolve_target, format_output

AI_START = "<!-- AI_GENERATED_START -->"
AI_END = "<!-- AI_GENERATED_END -->"


def write_class_feedback(lesson_file: Path, content: str) -> bool:
    """
    将班级反馈写入 lesson 文件的 ### 反馈总结 区块。
    若 AI_GENERATED_START/END 标记存在则替换中间内容，否则在 ### 反馈总结 下插入。
    返回是否成功写入。
    """
    text = lesson_file.read_text(encoding="utf-8")

    # 尝试替换已有标记内的内容
    pattern = re.compile(
        r"(###\s*反馈总结\s*\n.*?)" + re.escape(AI_START) + r".*?" + re.escape(AI_END),
        re.DOTALL | re.IGNORECASE,
    )

    if pattern.search(text):
        replacement = rf"\g<1>{AI_START}\n{content}\n{AI_END}"
        text = pattern.sub(replacement, text)
    else:
        # 标记不存在，在 ### 反馈总结 下插入
        header_pattern = re.compile(r"(###\s*反馈总结\s*\n)", re.IGNORECASE)
        if header_pattern.search(text):
            insertion = rf"\g<1>{AI_START}\n{content}\n{AI_END}\n"
            text = header_pattern.sub(insertion, text)
        else:
            # 连 ### 反馈总结 都不存在，追加到文件末尾
            text += f"\n### 反馈总结\n{AI_START}\n{content}\n{AI_END}\n"

    lesson_file.write_text(text, encoding="utf-8")
    return True


def _normalize_name(s: str) -> str:
    """归一化学员名字：去 emoji、去空格"""
    return s.replace("\U0001f464", "").strip()  # 👤


def write_student_feedback(feedback_file: Path, student_name: str, content: str) -> bool:
    """
    将学员反馈写入 Feedback N.md 中对应 ## 学员名 区块的 AI_GENERATED 标记内。
    若标记不存在则在该学员的 ### 反馈总结 下插入。
    返回是否成功写入。
    """
    text = feedback_file.read_text(encoding="utf-8")
    target_name = _normalize_name(student_name)

    # 按二级标题（## 但不是 ###）分割学员块，找到匹配的学员
    blocks = re.split(r"(?=^##(?!\s*#))", text, flags=re.MULTILINE)

    matched_idx = None
    for i, block in enumerate(blocks):
        header_match = re.match(r"^##(?!\s*#)\s*[👤\s]*(.+?)\s*$", block, re.MULTILINE)
        if header_match:
            block_name = _normalize_name(header_match.group(1))
            if block_name == target_name:
                matched_idx = i
                break

    if matched_idx is None:
        return False

    student_block = blocks[matched_idx]

    # 在学生块内替换或插入 AI_GENERATED 标记
    marker_pattern = re.compile(
        r"(###\s*反馈总结\s*\n)(.*?)" + re.escape(AI_START) + r".*?" + re.escape(AI_END),
        re.DOTALL | re.IGNORECASE,
    )

    if marker_pattern.search(student_block):
        replacement = rf"\g<1>\g<2>{AI_START}\n{content}\n{AI_END}"
        student_block = marker_pattern.sub(replacement, student_block)
    else:
        header_pattern = re.compile(r"(###\s*反馈总结\s*\n)", re.IGNORECASE)
        if header_pattern.search(student_block):
            insertion = rf"\g<1>{AI_START}\n{content}\n{AI_END}\n"
            student_block = header_pattern.sub(insertion, student_block)
        else:
            # 无 ### 反馈总结，追加到学员块末尾
            student_block += f"\n### 反馈总结\n{AI_START}\n{content}\n{AI_END}\n"

    blocks[matched_idx] = student_block
    text = "".join(blocks)
    feedback_file.write_text(text, encoding="utf-8")
    return True


def process_json_batch(target_path: Path, target: str, lesson_num: int, json_file: Path) -> list[dict]:
    """
    从 JSON 文件批量写入反馈。
    期望 JSON 格式：
    {
      "class_feedback": "...",       # 可选，班级反馈
      "students": [                   # 可选，学员反馈列表
        {"name": "学员名", "feedback": "..."},
        ...
      ]
    }
    """
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []
    lesson_dir = target_path / f"{target} Lesson {lesson_num}"
    lesson_file = lesson_dir / f"{target} Lesson {lesson_num}.md"
    feedback_file = lesson_dir / f"Feedback {lesson_num}.md"

    # 写入班级反馈
    if data.get("class_feedback") and lesson_file.exists():
        updated = write_class_feedback(lesson_file, data["class_feedback"].strip())
        results.append({
            "type": "class_feedback",
            "file": str(lesson_file),
            "updated": updated,
        })

    # 写入学员反馈
    if data.get("students") and feedback_file.exists():
        for student in data["students"]:
            name = student.get("name", "").strip()
            fb = student.get("feedback", "").strip()
            if name and fb:
                updated = write_student_feedback(feedback_file, name, fb)
                results.append({
                    "type": "student_feedback",
                    "student": name,
                    "file": str(feedback_file),
                    "updated": updated,
                })

    return results


def main():
    parser = argparse.ArgumentParser(description="写入反馈内容到 lesson 文件或 Feedback 文件")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", required=True, help="班级名或一对一学员名")
    parser.add_argument("--lesson-num", required=True, type=int, help="课次号")
    parser.add_argument(
        "--feedback-type",
        choices=["class_feedback", "student_feedback"],
        default=None,
        help="反馈类型（使用 --json-file 时可忽略）",
    )
    parser.add_argument("--content", default="", help="反馈文本")
    parser.add_argument("--student-name", default=None, help="学员姓名（student_feedback 时必填）")
    parser.add_argument("--json-file", default=None, help="JSON 文件路径（可选，用于批量写入）")
    args = parser.parse_args()

    # 参数校验
    if args.json_file:
        # JSON 批量模式
        try:
            vault = resolve_vault(args.vault)
        except FileNotFoundError as e:
            print(format_output("error", error=str(e)))
            sys.exit(1)

        try:
            target_path = resolve_target(vault, args.target)
        except FileNotFoundError as e:
            print(format_output("error", error=str(e)))
            sys.exit(1)

        json_path = Path(args.json_file)
        if not json_path.exists():
            print(format_output("error", error=f"JSON 文件不存在: {args.json_file}"))
            sys.exit(1)

        results = process_json_batch(target_path, args.target, args.lesson_num, json_path)
        if not results:
            print(format_output("error", error="JSON 文件中无有效反馈数据或文件不存在"))
            sys.exit(1)

        print(format_output("ok", data={"results": results}))
        return

    # 单条写入模式
    if not args.json_file:
        if not args.feedback_type:
            print(format_output("error", error="必须提供 --feedback-type 或使用 --json-file"))
            sys.exit(1)
        if not args.content.strip():
            print(format_output("error", error="必须提供 --content"))
            sys.exit(1)

    if args.feedback_type == "student_feedback" and not args.student_name:
        print(format_output("error", error="student_feedback 模式必须提供 --student-name"))
        sys.exit(1)

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    try:
        target_path = resolve_target(vault, args.target)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    lesson_dir = target_path / f"{args.target} Lesson {args.lesson_num}"
    if not lesson_dir.exists():
        print(format_output("error", error=f"课次目录不存在: {lesson_dir}"))
        sys.exit(1)

    content = args.content.strip()
    updated = False
    target_file = ""

    if args.feedback_type == "class_feedback":
        lesson_file = lesson_dir / f"{args.target} Lesson {args.lesson_num}.md"
        if not lesson_file.exists():
            print(format_output("error", error=f"Lesson 文件不存在: {lesson_file}"))
            sys.exit(1)
        target_file = str(lesson_file)
        updated = write_class_feedback(lesson_file, content)

    elif args.feedback_type == "student_feedback":
        feedback_file = lesson_dir / f"Feedback {args.lesson_num}.md"
        if not feedback_file.exists():
            print(format_output("error", error=f"Feedback 文件不存在: {feedback_file}"))
            sys.exit(1)
        target_file = str(feedback_file)
        updated = write_student_feedback(feedback_file, args.student_name, content)
        if not updated:
            print(format_output("error", error=f"在 Feedback 文件中未找到学员: {args.student_name}"))
            sys.exit(1)

    print(format_output("ok", data={"file": target_file, "updated": updated}))


if __name__ == "__main__":
    main()
