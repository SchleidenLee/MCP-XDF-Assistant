#!/usr/bin/env python3
"""
查找课时文件 - 固定脚本（V2 - MCP 降级方案）

根据日期和学员姓名查找对应的课时文件。
作为 MCP search_notes 不可用时的降级方案。

通过读取 Lesson 文件内容解析 [[Feedback N]] 链接查找 Feedback 文件，
解析失败时降级到目录遍历匹配。

用法:
    # 只按日期查找
    python3 find_lesson_files.py --date 2026-03-19 --vault "/mnt/d/Schleiden/Obsidian/XDF/Current Class"
    
    # 按日期 + 学员姓名查找
    python3 find_lesson_files.py --date 2026-03-19 --student "朱家君" --vault "/mnt/d/Schleiden/Obsidian/XDF/Current Class"
    
    # 只按学员姓名查找
    python3 find_lesson_files.py --student "3376" --vault "/mnt/d/Schleiden/Obsidian/XDF/Current Class"
"""

import sys
import argparse
import re
import json
from pathlib import Path
from datetime import datetime, timedelta


def search_by_date(vault_path: str, date_str: str) -> list:
    """按日期搜索课时文件（优先搜索 frontmatter）"""
    vault = Path(vault_path)
    if not vault.exists():
        return []
    
    results = []
    # 匹配 frontmatter 中的 Date 字段（--- 和 --- 之间）
    date_pattern = f"^Date:\\s*{date_str}"
    
    # 遍历所有 markdown 文件
    for md_file in vault.rglob("*.md"):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                in_frontmatter = False
                frontmatter_lines = 0
                found = False
                
                for line in f:
                    stripped = line.strip()
                    
                    # 检测 frontmatter 开始
                    if stripped == '---':
                        if not in_frontmatter:
                            in_frontmatter = True
                            frontmatter_lines = 0
                        else:
                            # frontmatter 结束
                            break
                    
                    if in_frontmatter:
                        frontmatter_lines += 1
                        # 限制只检查前 50 行 frontmatter
                        if frontmatter_lines > 50:
                            break
                        
                        # 在 frontmatter 中搜索 Date 字段
                        if re.match(date_pattern, stripped, re.IGNORECASE):
                            results.append(str(md_file))
                            found = True
                            break
                
                if found:
                    continue
                    
        except Exception:
            continue
    
    return results


def filter_by_student(files: list, student_name: str) -> list:
    """按学员姓名过滤文件"""
    if not student_name:
        return files
    
    # 支持多种匹配方式
    patterns = [
        student_name,  # 直接匹配
        student_name.replace(' ', ''),  # 去空格匹配
        student_name.lower(),  # 小写匹配
    ]
    
    filtered = []
    for f in files:
        file_str = str(f).lower()
        for pattern in patterns:
            if pattern.lower() in file_str:
                filtered.append(f)
                break
    
    return filtered


def find_feedback_file(lesson_file: Path) -> Path | None:
    """根据课时文件查找对应的学员反馈文件（V2 - 优先解析 [[Feedback]] 链接）"""
    parent_dir = lesson_file.parent
    
    # 【优先】尝试解析文件内的 [[Feedback N|...]] 链接
    try:
        with open(lesson_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # 匹配 [[Feedback N|xxx]] 或 [[Feedback N]]
            link_match = re.search(r'\[\[Feedback\s*(\d+)(?:\|[^\]]*)?\]\]', content, re.IGNORECASE)
            if link_match:
                feedback_num = link_match.group(1)
                # 优先精确匹配 Feedback N.md
                exact_path = parent_dir / f"Feedback {feedback_num}.md"
                if exact_path.exists():
                    return exact_path
                # 降级：模糊匹配 *Feedback*N*.md
                for f in parent_dir.glob(f"*Feedback*{feedback_num}*.md"):
                    return f
    except Exception:
        pass  # 解析失败，降级到目录遍历
    
    # 【降级】目录遍历匹配
    lesson_num_match = re.search(r'Lesson\s*(\d+)', lesson_file.name, re.IGNORECASE)
    if lesson_num_match:
        lesson_num = lesson_num_match.group(1)
        feedback_pattern = f"*Feedback*{lesson_num}*.md"
        for f in parent_dir.glob(feedback_pattern):
            return f
    
    # 尝试匹配同目录下的第一个 Feedback*.md
    for f in parent_dir.glob("Feedback*.md"):
        return f
    
    return None


def main():
    parser = argparse.ArgumentParser(description='查找课时文件')
    parser.add_argument('--date', type=str, help='日期 (YYYY-MM-DD)')
    parser.add_argument('--student', type=str, help='学员姓名或班级编号')
    parser.add_argument('--vault', type=str, required=True, help='Obsidian 仓库路径')
    parser.add_argument('--max-depth', type=int, default=1, help='往前推几天（默认 1 天）')
    
    args = parser.parse_args()
    
    # 确定搜索日期
    dates_to_search = []
    if args.date:
        dates_to_search.append(args.date)
        # 如果没找到，往前推 max_depth 天
        for i in range(1, args.max_depth + 1):
            prev_date = datetime.strptime(args.date, '%Y-%m-%d') - timedelta(days=i)
            dates_to_search.append(prev_date.strftime('%Y-%m-%d'))
    else:
        # 没有指定日期，默认今天和昨天
        today = datetime.now()
        dates_to_search = [
            today.strftime('%Y-%m-%d'),
            (today - timedelta(days=1)).strftime('%Y-%m-%d')
        ]
    
    all_results = []
    
    # 按日期搜索
    for date_str in dates_to_search:
        files = search_by_date(args.vault, date_str)
        if files:
            # 如果指定了学员姓名，过滤结果
            if args.student:
                files = filter_by_student(files, args.student)
            all_results.extend(files)
            # 找到结果就不再继续搜索更早的日期
            if all_results:
                break
    
    # 如果没有按日期找到，且指定了学员姓名，直接按姓名搜索
    if not all_results and args.student:
        all_results = filter_by_student(
            [str(f) for f in Path(args.vault).rglob("*.md")],
            args.student
        )
    
    # 构建结果
    results = []
    for lesson_file in all_results:
        lesson_path = Path(lesson_file)
        feedback_path = find_feedback_file(lesson_path)
        
        result = {
            "lesson_file": str(lesson_path),
            "feedback_file": str(feedback_path) if feedback_path else None,
            "has_class_feedback": lesson_path.exists(),
            "has_student_feedback": feedback_path.exists() if feedback_path else False
        }
        results.append(result)
    
    # 输出 JSON
    output = {
        "status": "ok" if results else "no_results",
        "search_params": {
            "date": args.date,
            "student": args.student,
            "vault": args.vault
        },
        "count": len(results),
        "files": results
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
