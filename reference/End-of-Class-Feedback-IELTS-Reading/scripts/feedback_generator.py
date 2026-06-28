#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Feedback Generator for IELTS Reading Feedback Skill
Uses Qwen3.5-Plus (DashScope) for analysis generation
"""

import json
import os
import sys
import re
import logging
from datetime import datetime
from pathlib import Path

import time

# =========================
# 路径配置与库导入
# =========================
# 从 api_clients 导入 LLM 客户端
API_CLIENTS_PATH = Path(__file__).parent.parent.parent.parent / "api_clients"
if not API_CLIENTS_PATH.exists():
    API_CLIENTS_PATH = Path("/mnt/x/AI/CoPaw/data/api_clients")
sys.path.insert(0, str(API_CLIENTS_PATH))

try:
    from llm.client import call_llm
except ImportError:
    # 如果导入失败，使用内嵌的备用实现
    call_llm = None

# =========================
# Logging Setup
# =========================
script_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(script_dir, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

logger = logging.getLogger("ielts_feedback_generator")
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
logger.info(f" Feedback Generator Started. Log file: {log_file}")

# =========================
# 自动加载环境变量
# =========================
_env_file = os.path.join(os.path.expanduser("~"), ".openclaw", ".env")
if os.path.exists(_env_file):
    with open(_env_file, "r") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())
                logger.debug(f"Loaded env var: {_key}")
# =========================

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from feedback_reader import get_lesson_summaries



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
    # 1. 换算有效分
    # 只有当“初级教材”且刚好考“27题”时，才用公式
    if course_type == "初级教材" and total_questions == 27:
        effective_score = (raw_score * 1.48) - 6
    else:
        effective_score = float(raw_score)
        
    # 限制边界 0-40
    effective_score = max(0.0, min(40.0, effective_score))
    lookup_score = int(round(effective_score))
    
    # 2. 查表
    band_val_str = BAND_MAP.get(lookup_score, "0.0")
    
    # 3. 生成区间：一律在当前分基础上 +0.5 (e.g. 6.0 -> 6.0-6.5)
    try:
        current_band = float(band_val_str)
        upper_band = current_band + 0.5
        # 封顶 9.0
        if upper_band > 9.0: upper_band = 9.0
        return f"{band_val_str}-{upper_band:.1f}"
    except ValueError:
        return band_val_str

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_template(template_path):
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def save_feedback(content, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


# =========================
# LLM 调用 - 使用 api_clients
# =========================

def call_llm_for_analysis(prompt):
    """Call LLM via api_clients.llm.client"""
    
    # 如果 api_clients 导入成功，使用统一接口
    if call_llm is not None:
        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是 IELTS 阅读教学反馈生成助手。根据数据生成专业反馈。要求：1.用具体数据 2.结合课堂表现 3.建议可执行 4.输出纯文本，每条一行，数字编号开头"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            t0 = time.time()
            logger.info(f"  🚀 [API Start] {datetime.now().strftime('%H:%M:%S')}")
            
            content = call_llm(messages, model="qwen3.6-plus", temperature=0.7)
            
            # 清理格式
            content = re.sub(r'^[-*]\s*', '', content, flags=re.MULTILINE)
            
            elapsed = time.time() - t0
            logger.info(f"  ✅ [API Done]  Received response in {elapsed:.2f}s")
            
            return content.strip()
        except Exception as e:
            logger.exception(f"LLM API error via api_clients: {e}")
            # 失败时回退到内嵌实现
    
    # 备用：内嵌实现（当 api_clients 不可用时）
    import urllib.request
    import urllib.error
    
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    
    if not api_key:
        logger.warning("DASHSCOPE_API_KEY not found, using fallback")
        return None
    
    url = "https://coding.dashscope.aliyuncs.com/v1/chat/completions"
    
    body = {
        "model": "qwen3.6-plus",
        "messages": [
            {
                "role": "system",
                "content": "你是 IELTS 阅读教学反馈生成助手。根据数据生成专业反馈。要求：1.用具体数据 2.结合课堂表现 3.建议可执行 4.输出纯文本，每条一行，数字编号开头"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "parameters": {"temperature": 0.7}
    }
    
    data = json.dumps(body).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }
    
    t0 = time.time()
    logger.info(f"  🚀 [API Start - Fallback] {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=480) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('choices'):
                content = result['choices'][0]['message']['content']
                content = re.sub(r'^[-*]\s*', '', content, flags=re.MULTILINE)
                
                elapsed = time.time() - t0
                logger.info(f"  ✅ [API Done - Fallback]  Received response in {elapsed:.2f}s")
                
                return content.strip()
        return None
    except Exception as e:
        logger.exception(f"LLM API error: {e}")
        return None


# =========================
# 分析生成 (One-Shot)
# =========================

def parse_feedback_response(response):
    """Parse single API response into 3 parts based on markers."""
    strengths = ""
    improvements = ""
    recommendations = ""
    
    # Split by markers
    parts = re.split(r'### 【学生优势】|### 【提升项】|### 【复习建议】', response)
    
    # parts[0] is usually empty or intro text
    # parts[1] -> Strengths
    # parts[2] -> Improvements
    # parts[3] -> Recommendations
    
    if len(parts) > 1: strengths = parts[1].strip()
    if len(parts) > 2: improvements = parts[2].strip()
    if len(parts) > 3: recommendations = parts[3].strip()
    
    # Fallback if parsing fails (just dump into one or return raw)
    if not strengths and not improvements:
        # If markers weren't followed, try to guess or return raw
        strengths = response 
    
    return strengths, improvements, recommendations

def fill_template(template_content, state, config, lesson_summaries=None):
    # 1. 动态生成【完成情况】块
    completion_block = ""
    if state["status"].get("ocr_done", False) and state.get("grading"):
        grading = state["grading"]
        total_correct = grading.get("score", 0)
        total_questions = grading.get("total", 40)
        estimated_band = grading.get("estimated_band", "N/A")
        section_scores = grading.get("section_scores", [])
        section_totals = grading.get("section_totals", [])
        
        # 动态拼接篇目成绩
        section_details = []
        for i in range(len(section_scores)):
            section_details.append(f"第{i+1}篇 {section_scores[i]}/{section_totals[i]}道")
        sections_str = "，".join(section_details)
        
        completion_block = f"准确率：共{total_questions}题，正确{total_correct}个（{sections_str}）\n\n预估雅思对应分数：{estimated_band}"
    else:
        completion_block = "学员未参加结班测"

    # 2. 构建 Prompt
    prompt_parts = []
    prompt_parts.append("你是雅思阅读教学专家。请根据以下数据生成反馈。")
    prompt_parts.append("")
    prompt_parts.append("【数据】")
    prompt_parts.append(completion_block)
    prompt_parts.append("")
    prompt_parts.append("【课堂历史反馈】")
    
    if lesson_summaries:
        for item in sorted(lesson_summaries, key=lambda x: x['lesson']):
            prompt_parts.append("L{}: {}".format(item['lesson'], item['content']))
    else:
        prompt_parts.append("无历史记录")
    
    prompt_parts.append("")
    prompt_parts.append("【任务】")
    prompt_parts.append("请生成以下三个部分，并严格遵守输出格式标记：")
    prompt_parts.append("")
    prompt_parts.append("1. ### 【学生优势】")
    prompt_parts.append("根据数据和历史表现，分析学员优势。要求：2-4 点，每条数据详实。格式严格遵循\"数字。 **核心结论**：具体展开\"")
    prompt_parts.append("")
    prompt_parts.append("2. ### 【提升项】")
    prompt_parts.append("根据错题分布和历史反馈中的问题，分析待提升点。要求：2-4 点，直击痛点。格式严格遵循\"数字。 **核心结论**：具体展开\"")
    prompt_parts.append("")
    prompt_parts.append("3. ### 【复习建议】")
    prompt_parts.append("针对上述提升项，给出可执行的复习计划。要求：2-4 点，具体可量化。格式严格遵循\"数字。 **核心结论**：具体展开\"")
    prompt_parts.append("")
    prompt_parts.append("请直接输出内容，不要有多余的问候语。")

    prompt = "\n".join(prompt_parts)

    # 3. Call API ONCE
    response = call_llm_for_analysis(prompt)
    
    if not response:
        response = "（生成失败，请检查 API 或数据）"
    
    # 4. Parse
    strengths, improvements, recommendations = parse_feedback_response(response)
    
    # 5. Fill Template
    filled = template_content
    filled = filled.replace("{completion_block}", completion_block)
    
    # Remove number prefix if model added it
    filled = filled.replace("{strengths}", strengths.strip())
    filled = filled.replace("{improvements}", improvements.strip())
    filled = filled.replace("{recommendations}", recommendations.strip())
    
    return filled

def generate_feedback_for_student(state_path, config_path, template_path, output_dir, 
                                   task_id, course_type, class_id, student_name):
    logger.info(f"Processing feedback for: {student_name}")
    state = load_json(state_path)
    config = load_json(config_path)
    template_content = load_template(template_path)
    
    lesson_summaries = get_lesson_summaries(class_id, student_name)
    if lesson_summaries:
        logger.info(f"  Loaded {len(lesson_summaries)} lesson summaries")
    
    if state.get("status", {}).get("feedback_generated", False):
        logger.info(f"  Already generated, skipping")
        return state
    
    logger.info(f"  Calling LLM for analysis...")
    filled_content = fill_template(template_content, state, config, lesson_summaries)
    
    feedback_folder_name = f"{task_id}结班反馈"
    output_path = os.path.join(output_dir, feedback_folder_name, f"{student_name}.md")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(filled_content)
    
    state["output"]["feedback_path"] = output_path
    state["status"]["feedback_generated"] = True
    state["meta"]["updated_at"] = datetime.now().isoformat()
    
    save_json(state, state_path)
    logger.info(f"  Generated: {feedback_folder_name}/{student_name}.md")
    return state


if __name__ == "__main__":
    import argparse
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from pathlib import Path
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--class-id", required=True)
    parser.add_argument("--student", required=False, help="单个学员名（可选，不指定则批量处理所有学员）")
    parser.add_argument("--workers", type=int, default=5, help="并行工作线程数（默认：5）")
    args = parser.parse_args()
    
    config = load_json(args.config)
    
    # 如果指定了单个学员，执行单个处理
    if args.student:
        state_path = os.path.join(args.cache_dir, args.task_id, f"{args.student}.json")
        try:
            generate_feedback_for_student(
                state_path, args.config, args.template, args.output_dir,
                args.task_id, config.get("course_type", ""), args.class_id, args.student
            )
        except Exception as e:
            logger.exception(f"Failed to process student {args.student}: {e}")
    else:
        # 批量处理所有学员
        cache_dir = Path(args.cache_dir) / args.task_id
        if not cache_dir.exists():
            logger.error(f"缓存目录不存在: {cache_dir}")
            sys.exit(1)
        
        # 查找所有学员 Cache
        state_files = list(cache_dir.glob("*.json"))
        if not state_files:
            logger.warning(f"缓存目录中没有 JSON 文件: {cache_dir}")
            sys.exit(0)
        
        # 所有学员都处理（不再过滤 ocr_done）
        students_to_process = []
        for state_file in state_files:
            try:
                state = load_json(state_file)
                students_to_process.append(state_file.stem)
            except Exception as e:
                logger.error(f"Failed to read {state_file.stem}: {e}")
        
        if not students_to_process:
            logger.error("没有找到学员 Cache 文件")
            sys.exit(0)
        
        logger.info(f"Found {len(students_to_process)} students to process")
        logger.info(f"Workers: {args.workers}")
        
        # 批量处理
        success_count = 0
        fail_count = 0
        
        def process_student(student_name):
            state_path = os.path.join(args.cache_dir, args.task_id, f"{student_name}.json")
            try:
                generate_feedback_for_student(
                    state_path, args.config, args.template, args.output_dir,
                    args.task_id, config.get("course_type", ""), args.class_id, student_name
                )
                return student_name, True, None
            except Exception as e:
                return student_name, False, e
        
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(process_student, student): student for student in students_to_process}
            
            for future in as_completed(futures):
                student_name, success, error = future.result()
                
                if error:
                    logger.error(f"Failed: {student_name}: {error}")
                    fail_count += 1
                else:
                    success_count += 1
        
        logger.info(f"Finished. Success: {success_count}, Failed: {fail_count}")
        
        # 清理 Cache
        import shutil
        if cache_dir.exists():
            logger.info(f"Cleaning up cache: {cache_dir}")
            shutil.rmtree(cache_dir)
            logger.info("Cache cleared.")

        if fail_count > 0:
            sys.exit(1)
