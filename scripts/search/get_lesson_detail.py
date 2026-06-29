#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：获取单次课的完整详情

输入：
  --vault    Vault 根目录
  --target   班级名或一对一学员名（必填）
  --lesson   课次号（必填）

输出（JSON）：
  status: ok | error
  data:
    target: "3164"
    lesson_num: 2
    date: "2026-03-22"
    target_type: "class"
    path: "..."
    frontmatter: {...}
    files: {
      "note": {"exists": true, "content_preview": "..."},
      "wordlist": {"exists": true, "content_preview": "..."},
      "grammar": {"exists": true, "content_preview": "..."},
      "homework": {"exists": true, "content_preview": "..."},
      "quiz": {"exists": true, "content_preview": "..."},
      "feedback": {"exists": true, "content_preview": "..."}
    },
    class_feedback: "...",
    student_feedbacks: [{"name": "...", "feedback": "..."}]
"""

import argparse
import sys
import re
from pathlib import Path

from xdf_utils import (
    resolve_vault,
    resolve_target,
    read_md_file,
    extract_feedback_from_content,
    is_class_folder,
    is_one_on_one_folder,
    format_output,
)


def preview(content: str, max_len: int = 200) -> str:
    """生成内容预览"""
    text = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    text = re.sub(r"#+\s*", "", text)
    text = text.replace("\n", " ").strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")


def main():
    parser = argparse.ArgumentParser(description="获取单次课完整详情")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", required=True, help="班级名或一对一学员名")
    parser.add_argument("--lesson", required=True, type=int, help="课次号")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    # 解析目标路径
    try:
        target_path = resolve_target(vault, args.target)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    target_type = "unknown"
    if is_class_folder(target_path):
        target_type = "class"
    elif is_one_on_one_folder(target_path):
        target_type = "one_on_one"

    lesson_dir = target_path / f"{args.target} Lesson {args.lesson}"
    if not lesson_dir.exists():
        print(format_output("error", error=f"课次 '{args.target} Lesson {args.lesson}' 不存在"))
        sys.exit(1)

    num = args.lesson
    lesson_file = lesson_dir / f"{args.target} Lesson {num}.md"
    content, fm = read_md_file(lesson_file) if lesson_file.exists() else ("", {})

    date_str = None
    date_raw = fm.get("Date", "")
    if date_raw:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", str(date_raw))
        if m:
            date_str = m.group(1)

    # 文件详情
    files = {}
    for name, fname in [
        ("note", f"Note {num}.md"),
        ("wordlist", f"Wordlist {num}.md"),
        ("grammar", f"Grammar Note {num}.md"),
        ("homework", f"Homework {num}.md"),
        ("quiz", f"Quiz {num + 1}.md"),
        ("feedback", f"Feedback {num}.md"),
    ]:
        fpath = lesson_dir / fname
        exists = fpath.exists()
        files[name] = {
            "exists": exists,
            "path": str(fpath),
            "content_preview": preview(fpath.read_text(encoding="utf-8")) if exists else "",
        }

    # 班级反馈
    class_feedback = extract_feedback_from_content(content)

    # 学员反馈
    student_feedbacks = []
    fb_file = lesson_dir / f"Feedback {num}.md"
    if fb_file.exists():
        fb_content = fb_file.read_text(encoding="utf-8")
        # 只匹配二级标题（## 开头但不是 ###），提取学员块
        for block_match in re.finditer(r"^##(?!\s*#)\s*[👤\s]*(.+)$", fb_content, re.MULTILINE):
            name = block_match.group(1).strip()
            start = block_match.start()
            next_section = re.search(r"^##(?!\s*#)", fb_content[start + 1 :], re.MULTILINE)
            if next_section:
                block = fb_content[start : start + 1 + next_section.start()]
            else:
                block = fb_content[start:]
            fb = extract_feedback_from_content(block)
            student_feedbacks.append({"name": name, "feedback": fb})

    print(format_output("ok", data={
        "target": args.target,
        "target_type": target_type,
        "lesson_num": num,
        "date": date_str,
        "path": str(lesson_dir),
        "frontmatter": fm,
        "files": files,
        "class_feedback": class_feedback,
        "student_feedbacks": student_feedbacks,
    }))


if __name__ == "__main__":
    main()
