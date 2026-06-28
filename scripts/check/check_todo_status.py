#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子脚本：检查课程文件中的待办框状态
支持检查：提交反馈、发送作业、结班测参与等

输入：
  --vault         Vault 根目录
  --target        班级名或一对一学员名（必填）
  --lesson-num    课次号（可选，不传则检查所有课次）

输出（JSON）：
  {"status": "ok", "data": {"target": "...", "todos": [...]}}
"""

import argparse
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xdf_utils import (
    resolve_vault,
    format_output,
    is_class_folder,
    is_one_on_one_folder,
    list_lesson_dirs,
    read_md_file,
)


def check_todos_in_file(path: str, file_type: str = "lesson") -> dict:
    """检查单个文件中的待办框状态"""
    from pathlib import Path
    
    p = Path(path)
    if not p.exists():
        return {"file": path, "exists": False, "todos": []}
    
    content = p.read_text(encoding="utf-8")
    todos = []
    
    # 通用待办框匹配：- [x] 或 - [ ]
    todo_pattern = re.compile(r'- \[([ xX])\]\s*(.+)', re.IGNORECASE)
    
    for match in todo_pattern.finditer(content):
        checked = match.group(1).lower() == 'x'
        label = match.group(2).strip()
        
        # 分类标签
        category = "other"
        if "提交反馈" in label:
            category = "feedback_submit"
        elif "发送作业" in label:
            category = "homework_send"
        elif "参加结班测" in label:
            category = "final_test_attend"
        elif "反馈已写完" in label:
            category = "final_feedback_written"
        
        todos.append({
            "label": label,
            "checked": checked,
            "category": category,
        })
    
    return {
        "file": path,
        "file_type": file_type,
        "exists": True,
        "todos": todos,
        "total": len(todos),
        "completed": sum(1 for t in todos if t["checked"]),
    }


def check_lesson_todos(vault, target: str, lesson_num: int) -> dict:
    """检查单节课的所有待办框"""
    lesson_dir = vault / target / f"{target} Lesson {lesson_num}"
    if not lesson_dir.exists():
        return {"lesson": lesson_num, "error": f"课次目录不存在: {lesson_dir}"}
    
    results = {
        "lesson": lesson_num,
        "lesson_dir": str(lesson_dir),
        "need_send_feedback": False,
        "files": {},
        "summary": {
            "total_todos": 0,
            "completed_todos": 0,
            "pending_todos": 0,
        },
    }
    
    # 检查课次主文件
    lesson_file = lesson_dir / f"{target} Lesson {lesson_num}.md"
    if lesson_file.exists():
        # 读取 need_send_feedback
        _, fm = read_md_file(lesson_file)
        results["need_send_feedback"] = fm.get("need_send_feedback", False) in (True, "true", "True")
        
        file_result = check_todos_in_file(str(lesson_file), "lesson_main")
        results["files"]["lesson_main"] = file_result
    
    # 检查 Feedback 文件
    feedback_file = lesson_dir / f"Feedback {lesson_num}.md"
    if feedback_file.exists():
        file_result = check_todos_in_file(str(feedback_file), "feedback")
        results["files"]["feedback"] = file_result
    
    # 汇总统计
    for file_data in results["files"].values():
        if file_data["exists"]:
            results["summary"]["total_todos"] += file_data["total"]
            results["summary"]["completed_todos"] += file_data["completed"]
    
    results["summary"]["pending_todos"] = results["summary"]["total_todos"] - results["summary"]["completed_todos"]
    
    return results


def check_all_lessons_todos(vault, target: str) -> list:
    """检查所有课次的待办框"""
    target_path = vault / target
    if not target_path.exists():
        return []
    
    lessons = list_lesson_dirs(target_path, target)
    results = []
    
    for lesson_dir in lessons:
        # 提取课次号
        m = re.search(rf"{re.escape(target)}\s+Lesson\s+(\d+)", lesson_dir.name, re.IGNORECASE)
        if m:
            lesson_num = int(m.group(1))
            results.append(check_lesson_todos(vault, target, lesson_num))
    
    return results


def main():
    parser = argparse.ArgumentParser(description="检查课程文件中的待办框状态")
    parser.add_argument("--vault", default=None, help="Vault 根目录")
    parser.add_argument("--target", required=True, help="班级名或学员名")
    parser.add_argument("--lesson-num", type=int, default=None, help="课次号（不传则检查所有课次）")
    parser.add_argument(
        "--category",
        choices=["feedback_submit", "homework_send", "final_test_attend", "final_feedback_written", "all"],
        default="all",
        help="只检查指定类别的待办（默认全部）",
    )
    
    args = parser.parse_args()
    
    try:
        vault = resolve_vault(args.vault)
    except FileNotFoundError as e:
        print(format_output("error", error=str(e)))
        sys.exit(1)
    
    # 检查目标是否存在
    target_path = vault / args.target
    if not target_path.exists():
        print(format_output("error", error=f"目标 '{args.target}' 不存在"))
        sys.exit(1)
    
    if args.lesson_num:
        # 检查指定课次
        result = check_lesson_todos(vault, args.target, args.lesson_num)
        # 按类别过滤
        if args.category != "all":
            for file_data in result.get("files", {}).values():
                if file_data["exists"]:
                    todos = file_data["todos"]
                    # 如果不需要写反馈，排除反馈类待办
                    if not result.get("need_send_feedback", False) and file_data["file_type"] == "lesson_main":
                        todos = [t for t in todos if t["category"] != "feedback_submit"]
                    file_data["todos"] = [t for t in todos if t["category"] == args.category]
                    file_data["total"] = len(file_data["todos"])
                    file_data["completed"] = sum(1 for t in file_data["todos"] if t["checked"])
            result["summary"]["total_todos"] = sum(f["total"] for f in result["files"].values())
            result["summary"]["completed_todos"] = sum(f["completed"] for f in result["files"].values())
            result["summary"]["pending_todos"] = result["summary"]["total_todos"] - result["summary"]["completed_todos"]
        print(format_output("ok", data=result))
    else:
        # 检查所有课次
        results = check_all_lessons_todos(vault, args.target)
        
        # 按类别过滤
        if args.category != "all":
            for r in results:
                if "files" in r:
                    for file_data in r["files"].values():
                        if file_data["exists"]:
                            todos = file_data["todos"]
                            # 如果不需要写反馈，排除反馈类待办
                            if not r.get("need_send_feedback", False) and file_data["file_type"] == "lesson_main":
                                todos = [t for t in todos if t["category"] != "feedback_submit"]
                            file_data["todos"] = [t for t in todos if t["category"] == args.category]
                            file_data["total"] = len(file_data["todos"])
                            file_data["completed"] = sum(1 for t in file_data["todos"] if t["checked"])
                    r["summary"]["total_todos"] = sum(f["total"] for f in r["files"].values())
                    r["summary"]["completed_todos"] = sum(f["completed"] for f in r["files"].values())
                    r["summary"]["pending_todos"] = r["summary"]["total_todos"] - r["summary"]["completed_todos"]
        
        # 计算全局统计
        total = sum(r["summary"]["total_todos"] for r in results if "summary" in r)
        completed = sum(r["summary"]["completed_todos"] for r in results if "summary" in r)
        pending = total - completed
        
        output = {
            "target": args.target,
            "category": args.category if args.category != "all" else "all",
            "lessons_checked": len(results),
            "global_summary": {
                "total_todos": total,
                "completed_todos": completed,
                "pending_todos": pending,
            },
            "lessons": results,
        }
        print(format_output("ok", data=output))


if __name__ == "__main__":
    main()
