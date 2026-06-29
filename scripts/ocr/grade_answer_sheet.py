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
IELTS_A_LOOKUP = {
    40: 9.0, 39: 8.5, 38: 8.5, 37: 8.0, 36: 8.0, 35: 7.5, 34: 7.5, 33: 7.0,
    32: 7.0, 31: 6.5, 30: 6.5, 29: 6.0, 28: 6.0, 27: 5.5, 26: 5.5, 25: 5.0,
    24: 5.0, 23: 4.5, 22: 4.5, 21: 4.0, 20: 4.0, 19: 3.5, 18: 3.5, 17: 3.0,
    16: 3.0, 15: 2.5, 14: 2.5, 13: 2.0, 12: 2.0, 11: 1.5, 10: 1.5, 9: 1.0,
    8: 1.0, 7: 0.5, 6: 0.5, 5: 0.5, 4: 0.5, 3: 0.5, 2: 0.5, 1: 0.5, 0: 0.0,
}

# OCR 无法识别的答案标记
UNRECOGNIZED_MARKERS = {"X", "", "?", "N/A", "NULL", "NONE"}

# 有效答案
VALID_ANSWERS = {"A", "B", "C", "D"}


def convert_to_band(raw_score: int, test_type: str) -> float:
    """将原始分数转换为 IELTS Band Score"""
    if test_type.upper() == "A":
        return IELTS_A_LOOKUP.get(raw_score, 0.0)
    else:
        # G-class 使用公式: (raw * 1.48) - 6
        band = (raw_score * 1.48) - 6
        # 限制在 0-9 范围内，并四舍五入到 0.5
        band = max(0.0, min(9.0, band))
        # 四舍五入到最近的 0.5
        band = round(band * 2) / 2
        return band


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
        elif answer.upper() not in VALID_ANSWERS:
            errors.append({
                "question": i + 1,
                "answer": answer,
                "error_type": "invalid_format",
            })
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

        # 规范化答案
        correct_normalized = [a.strip().upper() for a in correct_answers]
        student_normalized = [a.strip().upper() for a in student_answers]

        # 对比答案
        correct_count = 0
        wrong_count = 0
        for c, s in zip(correct_normalized, student_normalized):
            if s in UNRECOGNIZED_MARKERS or s == "":
                wrong_count += 1
            elif c == s:
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
