#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：列出所有待提交反馈（全局待办清单）

输入：
  --vault    Vault 根目录

输出（JSON）：
  status: ok | error
  data:
    pending_count: 3
    pending_items: [
      {
        "target": "3164",
        "target_type": "class",
        "lesson_num": 7,
        "date": "2026-05-10",
        "path": "...",
        "reason": "班级反馈未提交; 学员反馈未生成(9/9)"
      }
    ]
"""

import argparse
import sys
import re
from pathlib import Path

from xdf_utils import (
    resolve_vault,
    resolve_target,
    read_md_file,
    list_lesson_dirs,
    check_feedback_file_status,
    is_class_folder,
    is_one_on_one_folder,
    format_output,
)


def main():
    parser = argparse.ArgumentParser(description="列出全局待提交反馈")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    args = parser.parse_args()

    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)

    pending = []

    # 搜索目录：Vault 根目录 + Current Class + Archived
    search_dirs = [vault]
    for subdir_name in ["Current Class", "Archived"]:
        subdir = vault / subdir_name
        if subdir.is_dir():
            search_dirs.append(subdir)

    seen_targets = set()

    for search_dir in search_dirs:
        for sub in search_dir.iterdir():
            if not sub.is_dir():
                continue

            target_name = sub.name
            if target_name in seen_targets:
                continue
            seen_targets.add(target_name)

            target_type = None
            if is_class_folder(sub):
                target_type = "class"
            elif is_one_on_one_folder(sub):
                target_type = "one_on_one"
            else:
                continue

            lesson_dirs = list_lesson_dirs(sub, target_name)
            for lesson_dir in lesson_dirs:
                m = re.search(r"Lesson\s+(\d+)", lesson_dir.name, re.IGNORECASE)
                if not m:
                    continue
                lesson_num = int(m.group(1))

                lesson_file = lesson_dir / f"{target_name} Lesson {lesson_num}.md"
                if not lesson_file.exists():
                    continue

                content, fm = read_md_file(lesson_file)
                need_send = fm.get("need_send_feedback", False)
                if isinstance(need_send, str):
                    need_send = need_send.lower() in ("true", "yes", "1")

                if not need_send:
                    continue

                date_raw = fm.get("Date", "")
                date_str = None
                if date_raw:
                    m2 = re.match(r"(\d{4}-\d{2}-\d{2})", str(date_raw))
                    if m2:
                        date_str = m2.group(1)

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

                fb_file = lesson_dir / f"Feedback {lesson_num}.md"
                fb_status = check_feedback_file_status(fb_file)

                reasons = []
                if target_type == "class":
                    # 班课：检查班级反馈 + 学员反馈
                    if not class_submitted:
                        reasons.append("班级反馈未提交")
                    if not class_has_content:
                        reasons.append("班级反馈内容未生成")
                    if fb_status["exists"] and fb_status["pending"] > 0:
                        reasons.append(f"学员反馈未生成({fb_status['pending']}/{fb_status['students']})")
                elif target_type == "one_on_one":
                    # 一对一：只检查学员反馈（无班级反馈概念）
                    if fb_status["exists"] and fb_status["pending"] > 0:
                        reasons.append(f"学员反馈未生成")
                    elif not fb_status["exists"]:
                        reasons.append("反馈文件不存在")

                if reasons:
                    pending.append({
                        "target": target_name,
                        "target_type": target_type,
                        "lesson_num": lesson_num,
                        "date": date_str,
                        "path": str(lesson_dir),
                        "reason": "; ".join(reasons),
                    })

    pending.sort(key=lambda x: (x["date"] or "", x["target"], x["lesson_num"]))

    print(format_output("ok", data={
        "pending_count": len(pending),
        "pending_items": pending,
    }))


if __name__ == "__main__":
    main()
