#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IELTS 答题卡评分脚本
对比学生答案与正确答案，计算原始分数并转换为 IELTS  band score

输入：
  --correct-answers  正确答案 JSON 数组（40 个）
  --student-answers  学生答案 JSON 数组（40 个）
  --test-type        测试类型：A（Academic）或 G（General Training）
  --config-file      可选的 JSON 配置文件路径（包含正确答案和 test-type）

输出（JSON）：
  status: ok | error
  data:
    raw_score: N
    ielts_band: X.X
    correct_count: N
    wrong_count: N
    errors: [...]
    error_rate: 0.XX
"""

import argparse
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from xdf_utils import format_output


# IELTS Academic 听力和阅读原始分数转 Band Score 对照表
# 对齐参考项目逻辑：基础分 2.0 起，低分段分数更高
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

# OCR 无法识别的答案标记
UNRECOGNIZED_MARKERS = {"X", "", "?", "N/A", "NULL", "NONE"}

# 判断题变体映射
TFNG_VARIANTS = {
    "true": {"true", "t"},
    "false": {"false", "f"},
    "not given": {"not given", "ng", "notgiven"}
}

import re


def normalize(text):
    """Normalize text for comparison (lowercase, remove punctuation)"""
    if text is None:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s']", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def check_answer_match(student_ans, correct_answers):
    """智能判断学生答案是否正确，支持变体匹配"""
    s_ans = normalize(student_ans)
    if not s_ans or s_ans in {x.lower() for x in UNRECOGNIZED_MARKERS}:
        return False

    c_answers = [normalize(c) for c in correct_answers]

    # 1. 精确匹配或简单包含
    if s_ans in c_answers:
        return True

    # 2. 判断题变体处理 (T/F/NG)
    for canonical, variants in TFNG_VARIANTS.items():
        # 如果标准答案里包含 canonical 或其变体
        is_tfng_question = any(c in c_answers for c in variants)
        # 如果学生的回答也在变体中
        is_tfng_student = s_ans in variants

        if is_tfng_question and is_tfng_student:
            return True

    return False


def convert_to_band(raw_score: int, test_type: str) -> str:
    """将原始分数转换为 IELTS Band Score (返回区间字符串)"""
    if test_type.upper() == "A":
        band_val_str = BAND_MAP.get(raw_score, "0.0")
    else:
        # G-class / 初级教材 使用公式: (raw * 1.48) - 6
        # 参考项目中针对初级教材有特定逻辑，此处使用通用公式
        if raw_score <= 27: # 简单推断，如果是 27 题制
             band = (raw_score * 1.48) - 6
        else:
             # 如果是 40 题，但使用 G 类换算（通常不常见，但作为 fallback）
             # 假设总分 40 对应 9.0
             band = BAND_MAP.get(raw_score, "0.0")
             try:
                 return f"{band}-{min(9.0, float(band) + 0.5):.1f}"
             except ValueError:
                 return band
             
        band = max(0.0, min(40.0, band)) # 换算后的分数可能直接是 Band 对应分
        # 注意：参考项目中公式算出的是 raw score 然后再查表
        # 这里简化：如果 band 是 raw score 换算结果
        lookup_score = int(round(band))
        band_val_str = BAND_MAP.get(lookup_score, "0.0")

    # 生成区间
    try:
        current_band = float(band_val_str)
        upper_band = current_band + 0.5
        if upper_band > 9.0: upper_band = 9.0
        return f"{band_val_str}-{upper_band:.1f}"
    except ValueError:
        return band_val_str


def detect_ocr_errors(student_answers: list[str]) -> list[dict]:
    """检测 OCR 识别错误"""
    errors = []
    for i, answer in enumerate(student_answers):
        if answer.upper() in UNRECOGNIZED_MARKERS or answer.strip() == "":
            errors.append({
                "question": i + 1,
                "answer": answer,
                "error_type": "unrecognized",
            })
        # 移除无效格式检查，因为包含大量填空题，字母不是唯一标准
    return errors


def grade_answer_sheet(
    correct_answers: list[str],
    student_answers: list[str],
    test_type: str,
    config_file: str | None = None,
) -> str:
    """执行答题卡评分"""
    try:
        # 如果提供了配置文件，从中读取正确答案和测试类型
        if config_file:
            config_path = Path(config_file)
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if "correct_answers" in config:
                    correct_answers = config["correct_answers"]
                if "test_type" in config:
                    test_type = config["test_type"]

        # 验证输入
        if len(correct_answers) != 40:
            return format_output("error", error=f"正确答案数量应为 40，实际为 {len(correct_answers)}")
        if len(student_answers) != 40:
            return format_output("error", error=f"学生答案数量应为 40，实际为 {len(student_answers)}")

        # 对比答案 (使用智能匹配)
        correct_count = 0
        wrong_count = 0
        for c, s in zip(correct_answers, student_answers):
            if check_answer_match(s, [c]):
                correct_count += 1
            else:
                wrong_count += 1

        raw_score = correct_count
        ielts_band = convert_to_band(raw_score, test_type)

        # 检测 OCR 错误
        errors = detect_ocr_errors(student_answers)
        error_rate = len(errors) / len(student_answers) if student_answers else 0.0

        return format_output("ok", data={
            "raw_score": raw_score,
            "ielts_band": ielts_band,
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "errors": errors,
            "error_rate": round(error_rate, 2),
        })
    except Exception as e:
        return format_output("error", error=str(e))


def main():
    # 修复 Windows 终端编码问题 (UnicodeEncodeError)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="IELTS 答题卡评分")
    parser.add_argument("--correct-answers", type=str, help="正确答案 JSON 数组（40 个）")
    parser.add_argument("--student-answers", type=str, help="学生答案 JSON 数组（40 个）")
    parser.add_argument("--test-type", type=str, default="A", choices=["A", "G"], help="测试类型：A（Academic）或 G（General Training）")
    parser.add_argument("--config-file", type=str, help="JSON 配置文件路径（包含正确答案和 test-type）")
    args = parser.parse_args()

    # 从参数解析 JSON
    try:
        correct_answers = json.loads(args.correct_answers) if args.correct_answers else []
    except json.JSONDecodeError as e:
        print(format_output("error", error=f"正确答案 JSON 解析失败: {e}"))
        sys.exit(1)

    try:
        student_answers = json.loads(args.student_answers) if args.student_answers else []
    except json.JSONDecodeError as e:
        print(format_output("error", error=f"学生答案 JSON 解析失败: {e}"))
        sys.exit(1)

    result = grade_answer_sheet(
        correct_answers=correct_answers,
        student_answers=student_answers,
        test_type=args.test_type,
        config_file=args.config_file,
    )
    print(result)


if __name__ == "__main__":
    main()
