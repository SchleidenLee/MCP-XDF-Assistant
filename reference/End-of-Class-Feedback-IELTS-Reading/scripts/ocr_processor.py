#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR Processor for IELTS Reading Feedback Skill
Uses Qwen3.5-Plus (DashScope) for answer sheet recognition
"""

import os
import sys
import json
import base64
import subprocess
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

logger = logging.getLogger("ielts_feedback_ocr")
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
logger.info(f" OCR Pipeline Started. Log file: {log_file}")

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


def load_dashscope_api_key():
    """Load DashScope API key from environment variable"""
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if api_key:
        return api_key
    return None


# =========================
# 图片预处理 (自动压缩)
# =========================

def preprocess_image(image_path, output_base_dir):
    """
    Preprocess image: ALWAYS compress to standard size to ensure API stability.
    Returns the path to the image to be used (compressed).
    """
    image_path = Path(image_path)
    try:
        original_size_mb = image_path.stat().st_size / (1024 * 1024)
    except Exception as e:
        logger.error(f"Failed to read image size for {image_path}: {e}")
        return str(image_path)

    # Create compressed directory
    compressed_dir = Path(output_base_dir) / "compressed"
    compressed_dir.mkdir(parents=True, exist_ok=True)
    output_path = compressed_dir / f"{image_path.stem}_compressed.jpg"
    
    # Run ffmpeg (No size check anymore, always process)
    cmd = [
        'ffmpeg',
        '-i', str(image_path),
        '-vf', "scale='if(gt(iw,ih),min(2048,iw),-1)':'if(gt(iw,ih),-1,min(2048,ih))'",
        '-q:v', '2',
        '-y',
        str(output_path)
    ]
    
    try:
        logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            new_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Image processed: {image_path.name} ({original_size_mb:.2f}MB -> {new_size_mb:.2f}MB)")
            return str(output_path)
        else:
            logger.error(f"FFmpeg failed for {image_path.name}: {result.stderr}")
            return str(image_path)
    except FileNotFoundError:
        logger.error("FFmpeg executable not found.")
        return str(image_path)
    except Exception as e:
        logger.exception(f"Unexpected error during compression: {e}")
        return str(image_path)


def recognize_with_qwen36(image_path):
    """
    Use Qwen3.5-Plus (DashScope) to recognize answer sheet
    Returns extracted answers as a list
    """
    import urllib.request
    import urllib.error
    
    api_key = load_dashscope_api_key()
    if not api_key:
        logger.error("DASHSCOPE_API_KEY not found.")
        return None
    
    # Read image and convert to base64
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
    except Exception as e:
        logger.error(f"Failed to read image {image_path}: {e}")
        return None
    
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    logger.debug(f"Image {image_path} encoded to Base64 (Length: {len(image_base64)})")
    
    # DashScope API - Qwen3.5-Plus (使用 coding.dashscope.aliyuncs.com)
    url = "https://coding.dashscope.aliyuncs.com/v1/chat/completions"
    
    body = {
        "model": "qwen3.6-plus",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": """这是一张 IELTS 阅读答题卡。请识别所有 40 道题的答案。

要求：
1. 按题号顺序提取答案（Q1-Q40）
2. 填空题直接提取单词
3. 判断题识别 T/F/TRUE/FALSE/NG/N.G 等
4. 选择题识别 A/B/C/D
5. 配标题题识别罗马数字（I, II, III, IV, V, VI, VII, VIII）

请只输出答案列表，格式为：
Q1: answer1
Q2: answer2
...
Q40: answer40

如果某个答案无法识别，写"空"。"""
                    }
                ]
            }
        ]
    }

    data = json.dumps(body).encode('utf-8')
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }
    
    try:
        logger.info(f"Calling DashScope API for {Path(image_path).stem}...")
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=480) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if result.get('choices'):
                content = result['choices'][0]['message']['content']
                
                # Parse answers from Q1: xxx format
                answers = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('Q') and ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            answer = parts[1].strip()
                            if answer == '空' or not answer:
                                answers.append('')
                            else:
                                answers.append(answer)
                
                logger.info(f"Successfully extracted {len(answers)} answers.")
                return answers if answers else None
            else:
                logger.warning(f"API returned unexpected response: {result}")
                return None
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"API request failed: {e.code} {e.reason} - {error_body}")
        return None
    except Exception as e:
        logger.exception(f"API call failed unexpectedly: {e}")
        return None


def load_student_state(cache_file_path):
    """Load student state from cache file"""
    cache_file = Path(cache_file_path)
    
    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        state = {
            "student_name": cache_file.stem,
            "course_type": None,
            "input": {"image_path": None},
            "status": {"ocr_done": False, "graded": False, "feedback_generated": False},
            "ocr": {"answers": None, "raw_text": None, "error": None},
            "grading": None,
            "output": {"feedback_path": None},
            "meta": {"created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(), "task_id": None}
        }
        return state


def save_student_state(cache_file_path, state):
    """Save student state to cache file"""
    cache_file = Path(cache_file_path)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    state["meta"]["updated_at"] = datetime.now().isoformat()
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def process_single_student(image_path, cache_file_path, course_type, task_id):
    """Process a single student's answer sheet"""
    student_name = Path(image_path).stem
    logger.info(f"Processing OCR for: {student_name}")
    
    state = load_student_state(cache_file_path)
    state["input"]["image_path"] = str(image_path)
    state["course_type"] = course_type
    state["meta"]["task_id"] = task_id
    
    if state["status"]["ocr_done"]:
        logger.info(f"  OCR already completed, skipping...")
        return state
    
    try:
        # Preprocess image to avoid timeout
        processed_image_path = preprocess_image(str(image_path), Path(cache_file_path).parent)
        
        answers = recognize_with_qwen36(processed_image_path)
        
        if answers is None:
            raise Exception("Qwen3.5-Plus returned no answers")
        
        state["ocr"]["answers"] = answers
        state["ocr"]["raw_text"] = f"识别到 {len(answers)} 个答案"
        state["ocr"]["error"] = None
        state["status"]["ocr_done"] = True
        
        logger.info(f"  OCR completed! Found {len(answers)} answers for {student_name}")
        
    except Exception as e:
        logger.error(f"  OCR failed for {student_name}: {str(e)}")
        state["ocr"]["error"] = str(e)
    
    save_student_state(cache_file_path, state)
    return state


def main():
    import argparse
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    parser = argparse.ArgumentParser(description='OCR using Qwen3.5-Plus')
    parser.add_argument('--input-dir', required=True)
    parser.add_argument('--cache-base', required=True)
    parser.add_argument('--course-type', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--workers', type=int, default=10, help='并行工作线程数（默认：4）')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    cache_base = Path(args.cache_base)
    
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)
    
    image_files = [f for f in input_dir.iterdir() if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png'}]
    
    if not image_files:
        logger.warning(f"No images found in {input_dir}")
        sys.exit(0)
    
    logger.info(f"Found {len(image_files)} answer sheets")
    logger.info(f"Parallel workers: {args.workers}")
    
    # 准备任务列表
    tasks = []
    for image_file in sorted(image_files):
        cache_file_path = cache_base / args.task_id / f"{image_file.stem}.json"
        tasks.append((image_file, cache_file_path, args.course_type, args.task_id))
    
    # 统计已处理和待处理
    already_done = 0
    to_process = 0
    for _, cache_file_path, _, _ in tasks:
        if cache_file_path.exists():
            try:
                with open(cache_file_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    if state.get("status", {}).get("ocr_done", False):
                        already_done += 1
                    else:
                        to_process += 1
            except Exception as e:
                logger.error(f"Failed to read cache {cache_file_path}: {e}")
                to_process += 1
        else:
            to_process += 1
    
    logger.info(f"Already completed: {already_done}")
    logger.info(f"To process: {to_process}")
    
    # 并行处理
    success_count = 0
    fail_count = 0
    
    def process_wrapper(args):
        image_file, cache_file_path, course_type, task_id = args
        try:
            state = process_single_student(image_file, cache_file_path, course_type, task_id)
            return image_file, state, None
        except Exception as e:
            return image_file, None, e
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_wrapper, task): task for task in tasks}
        
        for future in as_completed(futures):
            image_file, state, error = future.result()
            
            if error:
                logger.error(f"Failed: {image_file.stem}: {error}")
                fail_count += 1
            elif state and state.get("status", {}).get("ocr_done", False):
                logger.info(f"Success: {image_file.stem}")
                success_count += 1
            else:
                logger.warning(f"Failed (No State): {image_file.stem}")
                fail_count += 1
    
    logger.info(f"Pipeline Finished. Success: {success_count}, Failed: {fail_count}")
    
    if fail_count > 0:
        logger.error(f"There are {fail_count} failures. Please check the log file.")
        sys.exit(1)
    else:
        logger.info("All students OCR completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
