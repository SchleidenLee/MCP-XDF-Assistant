#!/usr/bin/env python3
"""查询工作流任务进度。

读取 workflows/progress/{task_id}.json 文件，返回当前进度状态。
供 Agent 在调用多步工作流后轮询检查任务状态。
"""

import argparse
import json
import os
import sys
import uuid

from xdf_utils import format_output


def resolve_progress_dir(vault: str = None) -> str:
    """解析进度文件存储目录。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    progress_dir = os.path.join(project_root, "scripts", "workflows", "progress")
    os.makedirs(progress_dir, exist_ok=True)
    return progress_dir


def get_progress(task_id: str, progress_dir: str) -> dict:
    """读取指定 task_id 的进度文件。"""
    progress_file = os.path.join(progress_dir, f"{task_id}.json")
    
    if not os.path.exists(progress_file):
        return {
            "task_id": task_id,
            "status": "not_found",
            "message": f"Task {task_id} not found"
        }
    
    with open(progress_file, "r", encoding="utf-8") as f:
        return json.load(f)


def list_all_progress(progress_dir: str, status: str = None, limit: int = 10) -> list:
    """列出所有任务进度（支持按状态过滤）。"""
    results = []
    
    if not os.path.exists(progress_dir):
        return results
    
    for filename in os.listdir(progress_dir):
        if not filename.endswith(".json"):
            continue
        
        filepath = os.path.join(progress_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if status and data.get("status") != status:
                    continue
                results.append(data)
            except json.JSONDecodeError:
                continue
    
    # 按 updated_at 倒序排序，取最新 limit 条
    results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return results[:limit]


def main():
    parser = argparse.ArgumentParser(description="查询工作流任务进度")
    parser.add_argument("--vault", type=str, default=None,
                        help="Vault 路径（可选，用于定位项目根目录）")
    parser.add_argument("--task-id", type=str, default=None,
                        help="任务 ID（uuid），不传则列出所有任务")
    parser.add_argument("--status", type=str, default=None,
                        help="过滤状态：running/completed/failed（仅列出时使用）")
    parser.add_argument("--limit", type=int, default=10,
                        help="列出任务时的数量限制（默认 10）")
    
    args = parser.parse_args()
    
    try:
        progress_dir = resolve_progress_dir(args.vault)
        
        if args.task_id:
            # 查询单个任务
            data = get_progress(args.task_id, progress_dir)
            print(format_output(data))
        else:
            # 列出所有任务
            tasks = list_all_progress(progress_dir, args.status, args.limit)
            print(format_output({
                "tasks": tasks,
                "total_count": len(tasks)
            }))
            
    except Exception as e:
        print(format_output(None, str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
