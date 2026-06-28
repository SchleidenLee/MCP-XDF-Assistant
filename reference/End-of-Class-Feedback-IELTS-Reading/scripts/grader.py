#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grader for IELTS Reading Feedback Skill
Handles grading of student answers against course configuration
"""

import json
import os
import sys
import re
import logging
from datetime import datetime

# =========================
# Logging Setup
# =========================
script_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(script_dir, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

logger = logging.getLogger("ielts_feedback_grader")
logger.setLevel(logging.DEBUG)
# File Handler (Debug level)
fh = logging.FileHandler(log_file, encoding='utf-8')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
fh.setFormatter(formatter)
logger.addHandler(fh)
# Console Handler (Info level)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.info(f" Grader Started. Log file: {log_file}")


# =========================
# 雅思分数换算 (Hardcoded & Formula)
# =========================
BAND_MAP = {
    40: "9.0", 39: "8.5", 38: "8.5", 37: "8.0", 36: "8.0",
    35: "7.5", 34: "7.5", 33: "7.0", 32: "7.0", 31: "7.0",
    30: "6.5", 29: "6.5", 28: "6.5", 27: "6.0", 26: "6.0",
    25: "6.0", 24: "5.5", 23: "5.5", 22: "5.5", 21: "5.0",
    20: "5.0", 19: "5.0", 18: "4.5", 17: "4.5", 16: "4.5",
    15: "4.5", 14: "4.0", 13: "4.0", 12: "4.0", 11: "3.5",
    10: "3.5", 9: "3.0", 8: "3.0", 7: "3.0", 6: "2.5",
    5: "2.5", 4: "2.0", 3: "2.0", 2: "2.0", 1: "2.0", 0: "2.0"
}

def calculate_band_range(raw_score, total_questions, course_type):
    """
    根据原始分和课型计算预估雅思分数区间
    - A 类/默认：直接查表
    - G 类/初级教材：公式换算 (raw_score * 1.48) - 6 后再查表
    """
    # 1. 换算有效分
    if course_type == "初级教材" and total_questions == 27:
        effective_score = (raw_score * 1.48) - 6
    else:
        effective_score = float(raw_score)
        
    # 限制边界 0-40
    effective_score = max(0.0, min(40.0, effective_score))
    lookup_score = int(round(effective_score))
    
    # 2. 查表
    band_val_str = BAND_MAP.get(lookup_score, "0.0")
    
    # 3. 生成区间：+0.5
    try:
        current_band = float(band_val_str)
        upper_band = current_band + 0.5
        if upper_band > 9.0: upper_band = 9.0
        return f"{band_val_str}-{upper_band:.1f}"
    except ValueError:
        return band_val_str


# =========================
# 工具函数
# =========================

def load_json(path):
    """Load JSON file"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    """Save JSON file"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize(text):
    """Normalize text for comparison"""
    if text is None:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s']", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_roman(num_str):
    """Normalize Roman numerals to lowercase"""
    if not num_str:
        return num_str
    roman_chars = set('ivxlcdmIVXLCDM')
    if all(c in roman_chars for c in num_str.strip()):
        return num_str.strip().lower()
    return num_str


def normalize_list(ans):
    """Normalize answer list"""
    if isinstance(ans, list):
        return [normalize(x) for x in ans]
    return [normalize(ans)]


# =========================
# 判分逻辑
# =========================

def check_single_answer(q_type, student_ans, correct_answers):
    """Check if single question answer is correct"""
    student_ans_normalized = normalize(student_ans)
    correct_answers_normalized = normalize_list(correct_answers)

    if q_type == "fill_blank":
        return student_ans_normalized in correct_answers_normalized

    if q_type == "matching_heading":
        student_roman = normalize_roman(student_ans)
        for correct in correct_answers:
            correct_normalized = normalize(correct)
            correct_roman = normalize_roman(correct)
            if student_roman == correct_normalized or student_roman == correct_roman:
                return True
        return student_ans_normalized in correct_answers_normalized

    if q_type in ["matching", "matching_list"]:
        return student_ans_normalized in correct_answers_normalized

    if q_type == "true_false_not_given":
        variants = {
            "true": {"true", "t"},
            "false": {"false", "f"},
            "not given": {"not given", "ng", "notgiven"}
        }
        for correct in correct_answers_normalized:
            if correct in variants:
                if student_ans_normalized in variants[correct]:
                    return True
        return student_ans_normalized in correct_answers_normalized

    if q_type == "yes_no_not_given":
        variants = {
            "yes": {"yes", "y"},
            "no": {"no", "n"},
            "not given": {"not given", "ng", "notgiven"}
        }
        for correct in correct_answers_normalized:
            if correct in variants:
                if student_ans_normalized in variants[correct]:
                    return True
        return student_ans_normalized in correct_answers_normalized

    if q_type == "single_choice":
        return student_ans_normalized in correct_answers_normalized

    return False


# =========================
# OCR 误差检测
# =========================

def levenshtein(a, b):
    """Calculate Levenshtein distance"""
    if len(a) < len(b):
        return levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev_row = range(len(b) + 1)
    for i, c1 in enumerate(a):
        curr_row = [i + 1]
        for j, c2 in enumerate(b):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def is_possible_ocr_error(student_ans, correct_answers):
    """Check if student answer might be OCR error"""
    student_ans = normalize(student_ans)
    for correct in correct_answers:
        correct = normalize(correct)
        if len(correct) > 3 and levenshtein(student_ans, correct) <= 1:
            return True
    return False


# =========================
# 主函数
# =========================

def grade_student(state_path, config_path):
    """Grade a single student's answers"""
    logger.info(f"Grading student: {state_path}")
    state = load_json(state_path)
    config = load_json(config_path)

    ocr_answers = state["ocr"]["answers"]
    if not isinstance(ocr_answers, list):
        logger.warning(f"Invalid OCR answers format for {state_path}, treating as empty.")
        ocr_answers = []

    total = 0
    correct = 0
    details = []
    warnings = []
    section_scores = []

    try:
        for section_idx, section in enumerate(config["sections"]):
            section_correct = 0
            section_total = 0
            
            for group in section["question_groups"]:
                q_type = group["type"]
                
                for q in group["questions"]:
                    qid = q["id"]
                    correct_ans = q["answers"]
                    
                    question_index = qid - 1
                    if question_index < len(ocr_answers):
                        student_ans = ocr_answers[question_index]
                        if not student_ans:
                            student_ans = ""
                    else:
                        student_ans = ""
                    
                    is_correct = check_single_answer(q_type, student_ans, correct_ans)
                    
                    if is_correct:
                        correct += 1
                        section_correct += 1
                    
                    if not is_correct and student_ans:
                        if is_possible_ocr_error(student_ans, correct_ans):
                            warnings.append({
                                "question_id": qid,
                                "type": "ocr_suspected",
                                "student_answer": student_ans,
                                "correct_answer": correct_ans[0] if correct_ans else ""
                            })
                    
                    total += 1
                    section_total += 1
                    
                    details.append({
                        "question_id": int(qid),
                        "student_answer": student_ans,
                        "correct_answer": correct_ans,
                        "is_correct": is_correct,
                        "question_type": q_type
                    })
            
            section_scores.append(section_correct)
    except Exception as e:
        logger.error(f"Error during grading logic: {e}")
        raise
    
    # 计算各题型统计
    question_type_stats = {}
    for detail in details:
        q_type = detail["question_type"]
        if q_type not in question_type_stats:
            question_type_stats[q_type] = {"correct": 0, "total": 0}
        question_type_stats[q_type]["total"] += 1
        if detail["is_correct"]:
            question_type_stats[q_type]["correct"] += 1
    
    # 计算各篇章总题数
    section_totals = []
    for section in config["sections"]:
        section_total = sum(len(group.get("questions", [])) for group in section.get("question_groups", []))
        section_totals.append(section_total)
    
    accuracy = round(correct / total, 3) if total > 0 else 0
    
    # 计算预估分数
    course_type = state.get("course_type", "")
    estimated_band = calculate_band_range(correct, total, course_type)

    # Update state with grading results
    state["grading"] = {
        "score": correct,
        "total": total,
        "accuracy": accuracy,
        "section_scores": section_scores,
        "section_totals": section_totals,
        "question_type_stats": question_type_stats,
        "details": details,
        "warnings": warnings,
        "estimated_band": estimated_band,  # 新增：预估分数
        "error": None
    }

    state["status"]["graded"] = True
    state["meta"]["updated_at"] = datetime.now().isoformat()

    save_json(state, state_path)

    logger.info(f"Graded: {state['student_name']} | {correct}/{total} ({accuracy*100:.1f}%) | Band: {estimated_band}")


# =========================
# CLI 入口
# =========================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Grade student answers for IELTS Reading Feedback')
    parser.add_argument("--state", required=True, help="Student state JSON path")
    parser.add_argument("--config", required=True, help="Course config JSON path")

    args = parser.parse_args()

    grade_student(args.state, args.config)
