#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：查看反馈提交状态

输入：
  --vault         Vault 根目录
  --target        班级名或一对一学员名（可选，不传则检查全局）
  --date          指定日期（YYYY-MM-DD，可选）
  --date-start    日期段起始（可选）
  --date-end      日期段结束（可选）

输出（JSON）：
  status: ok | error
  data:
    pending_items: [
      {
        "target": "3164",
        "target_type": "class",
        "lesson_num": 7,
        "date": "2026-05-10",
        "path": "...",
        "need_send_feedback": true,
        "class_feedback_pending": true,
        "students_pending": 9,
        "students_total": 9,
        "reason": "班级反馈未提交 / 学员反馈未生成"
      }
    ],
    submitted_items: [...]
"""

import argparse
import sys
import re
from pathlib import Path
from datetime import datetime

from xdf_utils import (
    resolve_vault,
    read_md_file,
    list_lesson_dirs,
    check_feedback_file_status,
    is_class_folder,
    is_one_on_one_folder,
    format_output,
)


def parse_date(date_str: str) -> datetime | None:
    """解析日期字符串"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def check_target(vault: Path, target_name: str, date_start: datetime | None, date_end: datetime | None) -> tuple[list, list]:
    """检查单个目标的反馈状态，返回 (pending_items, submitted_items)"""
    target_path = vault / target_name
    if not target_path.exists():
        return [], []

    target_type = "unknown"
    if is_class_folder(target_path):
        target_type = "class"
    elif is_one_on_one_folder(target_path):
        target_type = "one_on_one"

    lesson_dirs = list_lesson_dirs(target_path, target_name)
    pending = []
    submitted = []

    for lesson_dir in lesson_dirs:
        m = re.search(r"Lesson\s+(\d+)", lesson_dir.name, re.IGNORECASE)
        if not m:
            continue
        lesson_num = int(m.group(1))

        lesson_file = lesson_dir / f"{target_name} Lesson {lesson_num}.md"
        if not lesson_file.exists():
            continue

        content, fm = read_md_file(lesson_file)
        date_raw = fm.get("Date", "")
        date_str = None
        lesson_date = None
        if date_raw:
            m2 = re.match(r"(\d{4}-\d{2}-\d{2})", str(date_raw))
            if m2:
                date_str = m2.group(1)
                lesson_date = parse_date(date_str)

        # 日期过滤
        if date_start and lesson_date and lesson_date < date_start:
            continue
        if date_end and lesson_date and lesson_date > date_end:
            continue
        if not date_start and not date_end and args.date:
            target_date = parse_date(args.date)
            if target_date and lesson_date and lesson_date != target_date:
                continue

        need_send = fm.get("need_send_feedback", False)
        if isinstance(need_send, str):
            need_send = need_send.lower() in ("true", "yes", "1")

        # 检查班级反馈状态
        class_submitted = bool(re.search(r"-\s*\[x\]\s*提交反馈", content, re.IGNORECASE))
        class_has_content = False
        class_fb_match = re.search(
            r"###\s*反馈总结\s*\n<!--\s*AI_GENERATED_START\s*-->(.*?)<!--\s*AI_GENERATED_END\s*-->",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if class_fb_match:
            inner = class_fb_match.group(1).strip()
            class_has_content = inner and inner not in ("待生成", "")

        # 检查学员反馈文件
        fb_file = lesson_dir / f"Feedback {lesson_num}.md"
        fb_status = check_feedback_file_status(fb_file)

        # 判定是否 pending
        reasons = []
        if need_send and not class_submitted:
            reasons.append("班级反馈未提交")
        if need_send and not class_has_content:
            reasons.append("班级反馈内容未生成")
        if fb_status["exists"] and fb_status["pending"] > 0:
            reasons.append(f"学员反馈未生成({fb_status['pending']}/{fb_status['students']})")

        item = {
            "target": target_name,
            "target_type": target_type,
            "lesson_num": lesson_num,
            "date": date_str,
            "path": str(lesson_dir),
            "need_send_feedback": need_send,
            "class_feedback_submitted": class_submitted,
            "class_feedback_has_content": class_has_content,
            "students_total": fb_status["students"],
            "students_generated": fb_status["generated"],
            "students_pending": fb_status["pending"],
        }

        if reasons:
            item["reason"] = "; ".join(reasons)
            pending.append(item)
        else:
            submitted.append(item)

    return pending, submitted


def main():
    global args
    parser = argparse.ArgumentParser(description="查看反馈提交状态")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", default=None, help="班级名或一对一学员名（可选，不传则全局检查）")
    parser.add_argument("--date", default=None, help="指定日期（YYYY-MM-DD）")
    parser.add_argument("--date-start", default=None, help="日期段起始（YYYY-MM-DD）")
    parser.add_argument("--date-end", default=None, help="日期段结束（YYYY-MM-DD）")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    date_start = parse_date(args.date_start) if args.date_start else None
    date_end = parse_date(args.date_end) if args.date_end else None
    if args.date and not date_start:
        date_start = parse_date(args.date)
        date_end = date_start

    all_pending = []
    all_submitted = []

    if args.target:
        p, s = check_target(vault, args.target, date_start, date_end)
        all_pending.extend(p)
        all_submitted.extend(s)
    else:
        # 全局检查：遍历所有班课和一对一
        for sub in vault.iterdir():
            if not sub.is_dir():
                continue
            if is_class_folder(sub) or is_one_on_one_folder(sub):
                p, s = check_target(vault, sub.name, date_start, date_end)
                all_pending.extend(p)
                all_submitted.extend(s)

    # 按日期排序
    all_pending.sort(key=lambda x: (x["date"] or "", x["target"], x["lesson_num"]))
    all_submitted.sort(key=lambda x: (x["date"] or "", x["target"], x["lesson_num"]))

    print(format_output("ok", data={
        "pending_count": len(all_pending),
        "submitted_count": len(all_submitted),
        "pending_items": all_pending,
        "submitted_items": all_submitted,
    }))


if __name__ == "__main__":
    main()
