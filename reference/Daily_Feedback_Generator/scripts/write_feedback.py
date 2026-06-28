#!/usr/bin/env python3
"""
XDF Feedback Writer - 固定脚本

根据生成的反馈 JSON，批量替换 Obsidian 笔记中的 AI_GENERATED 块。

用法:
    # 班课（有班级反馈 + 学员反馈）
    python3 write_feedback.py "$class_file" "$feedback_file" "$json_file"
    
    # 一对一（只有学员反馈）
    python3 write_feedback.py "$feedback_file" "$json_file"
"""

import sys
import json


def norm(s: str) -> str:
    """归一化学员名字：去 emoji、去空格"""
    return s.replace('👤', '').strip()


def replace_single_block(filepath: str, content: str) -> None:
    """替换文件中唯一的 AI_GENERATED 块（用于班级反馈）"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    out = []
    in_block = False
    
    for line in lines:
        if '<!-- AI_GENERATED_START -->' in line:
            out.append(line)
            out.append(content + '\n')
            in_block = True
            continue
        
        if '<!-- AI_GENERATED_END -->' in line:
            in_block = False
            out.append(line)
            continue
        
        if in_block:
            continue
        
        out.append(line)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(out)


def replace_student_blocks(filepath: str, students: list) -> None:
    """按学员名批量替换 AI_GENERATED 块（用于学员反馈）"""
    feedback_map = {norm(s['name']): s['feedback'] for s in students}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    out = []
    current_student = None
    in_block = False
    
    for line in lines:
        stripped = line.strip()
        
        # 检测学员块开始（## 开头，不是 ###）
        if stripped.startswith('## ') and not stripped.startswith('### '):
            current_student = norm(stripped.lstrip('# ').strip())
        
        # 遇到 AI_GENERATED_START 时，用当前学员的 feedback 替换
        if '<!-- AI_GENERATED_START -->' in line and current_student in feedback_map:
            out.append(line)
            out.append(feedback_map[current_student] + '\n')
            in_block = True
            continue
        
        if '<!-- AI_GENERATED_END -->' in line and in_block:
            in_block = False
            out.append(line)
            continue
        
        if in_block:
            continue
        
        out.append(line)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(out)


def main():
    # 参数解析
    if len(sys.argv) == 4:
        # 班课：class_file, feedback_file, json_file
        class_file = sys.argv[1]
        feedback_file = sys.argv[2]
        json_file = sys.argv[3]
    elif len(sys.argv) == 3:
        # 一对一：feedback_file, json_file
        class_file = None
        feedback_file = sys.argv[1]
        json_file = sys.argv[2]
    else:
        print(json.dumps({
            "status": "error",
            "error": f"参数错误，需要 2-3 个参数，当前 {len(sys.argv) - 1} 个"
        }, ensure_ascii=False))
        sys.exit(1)
    
    # 读取 JSON（带错误处理）
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": f"JSON 解析失败：{str(e)}"
        }, ensure_ascii=False))
        sys.exit(1)
    
    # 验证 JSON 结构
    if "students" not in data or not isinstance(data["students"], list):
        print(json.dumps({
            "status": "error",
            "error": "JSON 结构错误：缺少 students 字段或不是列表"
        }, ensure_ascii=False))
        sys.exit(1)
    
    # 验证每个学生数据
    for i, student in enumerate(data["students"]):
        if "name" not in student or "feedback" not in student:
            print(json.dumps({
                "status": "error",
                "error": f"学生 {i+1} 数据不完整：缺少 name 或 feedback 字段"
            }, ensure_ascii=False))
            sys.exit(1)
    
    # 写班级反馈（有班级文件且反馈非空时才写）
    if class_file and data.get('class_feedback'):
        replace_single_block(class_file, data['class_feedback'])
    
    # 写学员反馈
    replace_student_blocks(feedback_file, data['students'])
    
    # 输出结果
    print(json.dumps({
        "status": "ok",
        "class_written": bool(class_file and data.get('class_feedback')),
        "students_written": [s['name'] for s in data['students']]
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
