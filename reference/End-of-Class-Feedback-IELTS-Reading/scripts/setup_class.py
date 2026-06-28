#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup Class - 建档脚本
从答题卡文件夹名解析班号和课型，抓取学员名单，建立 Cache
"""

import json
import os
import re
import sys
import logging
from datetime import datetime
from pathlib import Path

# =========================
# Logging Setup
# =========================
script_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(script_dir, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

logger = logging.getLogger("ielts_setup_class")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(log_file, encoding='utf-8')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
fh.setFormatter(formatter)
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.info(f" Setup Class Started. Log file: {log_file}")

# =========================
# 工具函数
# =========================
def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_folder_name(folder_path):
    """
    从文件夹名解析班号和课型
    示例：
    - "3376 初级讲义" → class_id="3376", course_type="初级讲义"
    - "3320_初级讲义" → class_id="3320", course_type="初级讲义"
    - "凯丽 L1 教材" → class_id="凯丽", course_type="L1 教材"
    """
    folder_name = Path(folder_path).name
    # 正则：数字 + 分隔符(可选) + 文字（班课）或 纯文字（一对一）
    match = re.match(r'(\d+)[_\s]*(.+)', folder_name)
    if match:
        # 班课：数字班号 + 课型（自动去除首尾空白和特殊符号）
        return match.group(1), match.group(2).strip('_- ')
    else:
        # 一对一：文件夹名即学员名
        return folder_name, ""

def is_valid_name(name):
    """校验是否为有效学员姓名"""
    if not name or len(name) < 2:
        return False
    # 排除纯符号、分隔符或表头关键词
    if re.match(r'^[-_=|]+$', name):
        return False
    if name in ['姓名', 'Name', '学生', '序号', 'No.']:
        return False
    # 必须包含中文或常见英文字母
    if re.search(r'[\u4e00-\u9fff]', name):
        return True
    if re.match(r'^[a-zA-Z\u00C0-\u00FF\s\.]{2,}$', name):
        return True
    return False

def get_student_list(class_id, base_path=None):
    r"""
    从班级档案总控页抓取学员名单
    
    Args:
        class_id: 班级号（如 "3376"）
        base_path: Obsidian 基础路径（默认：/mnt/d/Schleiden/Obsidian/XDF/Current Class）
    
    Returns:
        list: 学员姓名列表
    """
    if base_path is None:
        base_path = '/mnt/d/Schleiden/Obsidian/XDF/Current Class'
    
    control_file = Path(base_path) / class_id / f"{class_id}.md"
    
    if not control_file.exists():
        logger.warning(f"总控页不存在：{control_file}")
        return []
    
    with open(control_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    students = []
    lines = content.split('\n')
    name_idx = -1
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped.startswith('|'):
            continue
        
        parts = [p.strip() for p in line.split('|')]
        
        # 1. 识别表头，确定姓名列的位置
        if '姓名' in line_stripped and name_idx == -1:
            if '姓名' in parts:
                name_idx = parts.index('姓名')
            continue
            
        if name_idx == -1: 
            continue # 还没找到表头，跳过
        
        # 2. 物理过滤：跳过分隔行
        if '---' in line_stripped or '===' in line_stripped:
            continue
        
        # 3. 提取并校验
        if len(parts) > name_idx:
            candidate = parts[name_idx]
            if is_valid_name(candidate):
                students.append(candidate)
    
    logger.info(f"Found {len(students)} students from {class_id}.md: {students}")
    return students

def create_cache(student_name, course_type, class_id, cache_base):
    """
    创建学员 Cache 文件
    
    Args:
        student_name: 学员姓名
        course_type: 课型（如 "初级讲义"）
        class_id: 班级号
        cache_base: Cache 基础路径（默认：./cache）
    
    Returns:
        str: Cache 文件路径
    """
    cache_file = Path(cache_base) / class_id / f"{student_name}.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    state = {
        "student_name": student_name,
        "course_type": course_type,
        "input": {
            "image_path": None
        },
        "status": {
            "ocr_done": False,
            "graded": False,
            "feedback_generated": False
        },
        "ocr": {
            "answers": None,
            "raw_text": None,
            "error": None
        },
        "grading": None,
        "output": {
            "feedback_path": None
        },
        "history_feedback": [],
        "meta": {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "task_id": class_id
        }
    }
    
    save_json(state, cache_file)
    return str(cache_file)

def get_lesson_summaries(class_id, student_name, base_path=None):
    """
    调用 feedback_reader.py 获取学员课堂反馈总结
    """
    try:
        from feedback_reader import get_lesson_summaries as fetch_summaries
        return fetch_summaries(class_id, student_name, base_path)
    except Exception as e:
        logger.error(f"Failed to load feedback_reader: {e}")
        return []

# =========================
# 主流程
# =========================
def setup_class(answer_sheet_folder, cache_base="./cache", obsidian_base=None):
    r"""
    建档主流程
    
    Args:
        answer_sheet_folder: 答题卡文件夹路径（如：/Desktop/3376 初级讲义）
        cache_base: Cache 基础路径（默认：./cache）
        obsidian_base: Obsidian XDF 基础路径（默认：/mnt/d/Schleiden/Obsidian/XDF/Current Class）
    """
    logger.info(f"Starting setup for: {answer_sheet_folder}")
    
    # Step 1: 从文件夹名解析班号和课型
    class_id, course_type = parse_folder_name(answer_sheet_folder)
    logger.info(f"Parsed: class_id={class_id}, course_type={course_type}")
    
    if not class_id:
        logger.error("无法解析班号")
        return False
    
    # Step 2: 获取学员名单
    students = get_student_list(class_id, obsidian_base)
    if not students:
        logger.error(f"未找到学员名单：{class_id}")
        return False
    
    logger.info(f"Found {len(students)} students: {', '.join(students)}")
    
    # Step 3: 为每个学员建立 Cache
    cache_files = []
    for student_name in students:
        cache_file = create_cache(student_name, course_type, class_id, cache_base)
        cache_files.append(cache_file)
        logger.info(f"Created cache for {student_name}: {cache_file}")
    
    # Step 4: 抓取历史反馈
    logger.info("Fetching historical feedback...")
    for student_name in students:
        summaries = get_lesson_summaries(class_id, student_name, obsidian_base)
        if summaries:
            cache_file = Path(cache_base) / class_id / f"{student_name}.json"
            state = load_json(cache_file)
            state["history_feedback"] = summaries
            state["meta"]["updated_at"] = datetime.now().isoformat()
            save_json(state, cache_file)
            logger.info(f"Loaded {len(summaries)} feedback summaries for {student_name}")
        else:
            logger.info(f"No historical feedback for {student_name}")
    
    logger.info(f"Setup completed! Created {len(cache_files)} cache files.")
    return True

# =========================
# CLI 入口
# =========================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup Class - 建档脚本')
    parser.add_argument("--answer-sheet-folder", required=True,
                        help="答题卡文件夹路径（如：/Desktop/3376 初级讲义）")
    parser.add_argument("--cache-base", default="./cache",
                        help="Cache 基础路径（默认：./cache）")
    parser.add_argument("--obsidian-base", default=None,
                        help="Obsidian XDF 基础路径（默认：/mnt/d/Schleiden/Obsidian/XDF/Current Class）")
    
    args = parser.parse_args()
    
    success = setup_class(args.answer_sheet_folder, args.cache_base, args.obsidian_base)
    sys.exit(0 if success else 1)
