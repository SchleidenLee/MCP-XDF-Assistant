#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取学员课堂反馈总结
"""

import os
import re
from pathlib import Path


def extract_student_summary(feedback_file, student_name):
    """
    从 Feedback 文件中提取单个学员的反馈总结
    
    定位逻辑：
    1. 找到 ## 👤 沃伦 或 ## 沃伦
    2. 提取 ### 反馈总结 下的内容（移除 AI_GENERATED 标记）
    """
    with open(feedback_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 定位学员块（支持有/无 emoji）
    student_pattern = rf'^##\s*[👤\s]*{re.escape(student_name)}\s*$'
    match = re.search(student_pattern, content, re.MULTILINE)
    if not match:
        return None
    
    # 提取该块内容（到下一个 ## 开头）
    start = match.start()
    next_section = re.search(r'^##\s', content[start+1:], re.MULTILINE)
    if next_section:
        block = content[start:start+1+next_section.start()]
    else:
        block = content[start:]
    
    # 定位 ### 反馈总结
    summary_header = block.find('### 反馈总结')
    if summary_header == -1:
        return None
    
    # 提取反馈总结内容（到下一个 ### 或 ## 或块结束）
    summary_start = summary_header + len('### 反馈总结')
    
    # 找结束位置
    next_h3 = block.find('###', summary_start)
    next_h2 = block.find('##', summary_start)
    
    end_positions = [len(block)]
    if next_h3 != -1:
        end_positions.append(next_h3)
    if next_h2 != -1:
        end_positions.append(next_h2)
    
    end = min(end_positions)
    summary = block[summary_start:end].strip()
    
    # 清理：移除 AI_GENERATED 标记和分隔符
    summary = re.sub(r'<!--\s*AI_GENERATED_START\s*-->', '', summary)
    summary = re.sub(r'<!--\s*AI_GENERATED_END\s*-->', '', summary)
    lines = [line for line in summary.split('\n') if line.strip() and line.strip() != '---']
    summary = '\n'.join(lines).strip()
    
    return summary if summary else None


def get_lesson_summaries(class_id, student_name, base_path=None):
    """
    获取学员所有课堂反馈总结
    
    搜索：{base_path}/{class_id}/3376 Lesson N/Feedback N.md
    返回：[{lesson: 1, content: "..."}, {lesson: 2, content: "..."}, ...]
    
    Args:
        class_id: 班级号（如 "3376"）
        student_name: 学员姓名
        base_path: Obsidian XDF 基础路径（默认：D:\Schleiden\Obsidian\XDF\Current Class）
    
    Returns:
        list: [{lesson: 1, file: "...", content: "..."}, ...]
    """
    summaries = []
    
    # 默认路径（Linux 风格，WSL）
    if base_path is None:
        base_path = '/mnt/d/Schleiden/Obsidian/XDF/Current Class'
    
    class_dir = Path(base_path) / class_id
    
    if not class_dir.exists():
        print(f"⚠️  班级目录不存在：{class_dir}")
        return summaries
    
    # 搜索所有 Lesson 目录（按数字排序，支持任意班级号）
    lesson_pattern = f"{class_id} Lesson */"
    lesson_dirs = sorted(
        [d for d in class_dir.glob(lesson_pattern) if d.is_dir()],
        key=lambda x: int(re.search(r'(\d+)', x.name).group(1))
    )
    
    for lesson_dir in lesson_dirs:
        lesson_num = int(lesson_dir.name.split()[-1])
        feedback_file = lesson_dir / f"Feedback {lesson_num}.md"
        
        if feedback_file.exists():
            summary = extract_student_summary(feedback_file, student_name)
            if summary:
                summaries.append({
                    "lesson": lesson_num,
                    "file": str(feedback_file),
                    "content": summary
                })
    
    return summaries


# =========================
# CLI 入口
# =========================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='读取学员课堂反馈总结')
    parser.add_argument("--class-id", required=True, help="班级号 (如 3376)")
    parser.add_argument("--student-name", required=True, help="学员姓名")
    parser.add_argument("--base-path", default=None,
                        help="Obsidian XDF 基础路径 (默认: D:\\Schleiden\\Obsidian\\XDF\\Current Class)")
    
    args = parser.parse_args()
    
    summaries = get_lesson_summaries(args.class_id, args.student_name, args.base_path)
    
    if not summaries:
        print(f"未找到 {args.student_name} 的课堂反馈")
    else:
        print(f"找到 {len(summaries)} 条课堂反馈:\n")
        for item in summaries:
            print(f"=== Lesson {item['lesson']} ===")
            print(f"文件：{item['file']}")
            print(f"内容：{item['content'][:150]}...")
            print()
