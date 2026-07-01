#!/usr/bin/env python3
"""结班反馈生成工作流。

通过 subprocess 调用原子脚本串联完成：
  1. init_end_of_class_cache  — 建档（读取学员名单、答题卡、配置、历史反馈）
  2. ocr_answer_sheet         — 批量 OCR 识别答题卡
  3. grade_answer_sheet       — 批量批改 + 估分
  4. generate_feedback        — LLM 生成结班反馈

返回 task_id，供 query_task_progress 查询进度。
"""

import argparse
import json
import os
import sys
import uuid
import subprocess
import re
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加父目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xdf_utils import resolve_vault, format_output, read_md_file, resolve_target
from llm_utils import call_llm

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 确保 SCRIPTS_DIR 指向 scripts/ 目录（包含 xdf_utils.py 的目录）
if not os.path.exists(os.path.join(SCRIPTS_DIR, "xdf_utils.py")):
    SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# 配置文件目录（项目根目录下的 configs/）
CONFIGS_DIR = os.path.join(os.path.dirname(SCRIPTS_DIR), "configs")


def _resolve_config_file(course_type: str) -> str | None:
    """根据课型自动匹配 configs/ 目录下的 JSON 配置文件"""
    if not course_type:
        return None
    configs_path = Path(CONFIGS_DIR)
    if not configs_path.exists():
        return None
    # 匹配规则：文件名包含课型（如 初级讲义.json 匹配 "初级讲义"）
    for f in configs_path.glob("*.json"):
        if course_type in f.stem:
            return str(f)
    return None

# ===== 进度管理 =====

PROGRESS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress")


def _progress_file(task_id):
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    return os.path.join(PROGRESS_DIR, f"{task_id}.json")


def _init_progress(task_id, workflow, input_args):
    data = {
        "task_id": task_id,
        "workflow": workflow,
        "input": input_args,
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "current_step": 0,
        "total_steps": 4,
        "steps": []
    }
    with open(_progress_file(task_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def _update_step(progress, step_num, name, status, detail=None):
    for s in progress["steps"]:
        if s["step"] == step_num:
            s["status"] = status
            if status == "running":
                s["started_at"] = datetime.now().isoformat()
            elif status in ("completed", "failed"):
                s["completed_at"] = datetime.now().isoformat()
            if detail:
                s["detail"] = detail
            break
    else:
        step = {
            "step": step_num,
            "name": name,
            "status": status,
            "started_at": datetime.now().isoformat() if status == "running" else None,
            "completed_at": datetime.now().isoformat() if status in ("completed", "failed") else None,
        }
        if detail:
            step["detail"] = detail
        progress["steps"].append(step)

    progress["current_step"] = step_num
    progress["updated_at"] = datetime.now().isoformat()
    if status == "failed":
        progress["status"] = "failed"
    _save_progress(progress)
    return progress


def _save_progress(progress):
    with open(_progress_file(progress["task_id"]), "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def _complete_progress(progress):
    progress["status"] = "completed"
    progress["updated_at"] = datetime.now().isoformat()
    _save_progress(progress)


# ===== 原子脚本调用封装 =====

def _run_script(script_rel_path, **kwargs):
    """调用原子脚本并返回解析后的 JSON 结果。"""
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, script_rel_path)]
    for k, v in kwargs.items():
        if v is not None:
            cmd_key = k.replace("_", "-")
            if isinstance(v, bool):
                if v:
                    cmd.append(f"--{cmd_key}")
            else:
                cmd.append(f"--{cmd_key}")
                cmd.append(str(v))

    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=SCRIPTS_DIR,
        encoding="utf-8", errors="replace"
    )

    # 尝试解析 JSON 输出（即使 exit code 非零）
    output_json = None
    try:
        output_json = json.loads(result.stdout)
    except json.JSONDecodeError:
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    output_json = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

    # 如果有 JSON 输出且是 error 状态，抛出异常
    if output_json and output_json.get("status") == "error":
        raise RuntimeError(f"脚本 {script_rel_path} 返回错误: {output_json.get('error', '未知错误')}")

    if output_json:
        return output_json

    # 无 JSON 输出且 exit code 非零
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        raise RuntimeError(f"脚本 {script_rel_path} 失败: {stderr or stdout}")

    raise RuntimeError(f"脚本 {script_rel_path} 无有效 JSON 输出")


def _init_cache(vault, target, answer_sheet_folder, config_file):
    """Step 1: 初始化结班缓存"""
    return _run_script("ocr/init_end_of_class_cache.py",
                       vault=vault, target=target,
                       answer_sheet_folder=answer_sheet_folder,
                       config_file=config_file)


def _ocr_image(vault, image_path, model="qwen3.6-plus"):
    """OCR 单张答题卡"""
    return _run_script("ocr/ocr_answer_sheet.py",
                       vault=vault, image=image_path, model=model)


def _grade_answers(correct_answers, student_answers, test_type="A"):
    """批改单个学员答案"""
    return _run_script("ocr/grade_answer_sheet.py",
                       correct_answers=json.dumps(correct_answers),
                       student_answers=json.dumps(student_answers),
                       test_type=test_type)


# ===== 缓存操作 =====

def _load_cache(vault_path, target):
    """加载结班缓存"""
    try:
        class_path = resolve_target(Path(vault_path), target)
    except FileNotFoundError:
        return None, None
    cache_path = class_path / "cache" / f"{target}_end_of_class.json"
    if not cache_path.exists():
        return None, None
    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f), cache_path


def _update_cache(cache, cache_path):
    """保存结班缓存"""
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ===== 历史反馈读取 =====

def _read_student_history(cache, student_name):
    """从缓存中获取学员的历史反馈"""
    return cache.get("historical_feedback", {}).get(student_name, [])


# ===== 反馈生成 =====

# IELTS Academic 原始分数转 Band Score 对照表
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


def _calculate_band(raw_score, total, course_type=""):
    """计算预估分数（与 grader.py 保持一致）"""
    if course_type == "初级教材" and total == 27:
        effective = (raw_score * 1.48) - 6
    else:
        effective = float(raw_score)
    effective = max(0.0, min(40.0, effective))
    lookup_score = int(round(effective))
    band_str = BAND_MAP.get(lookup_score, "0.0")
    try:
        current = float(band_str)
        upper = min(9.0, current + 0.5)
        return f"{band_str}-{upper:.1f}"
    except ValueError:
        return band_str


def _analyze_question_types(config, student_answers):
    """从 config 中分析学员各题型的正确率"""
    if not config or not student_answers:
        return []
    
    type_stats = []
    for section in config.get("sections", []):
        passage_title = section.get("title", "")
        for group in section.get("question_groups", []):
            type_name = group.get("type_name", "")
            questions = group.get("questions", [])
            if not questions:
                continue
            
            correct = 0
            total = len(questions)
            wrong_questions = []
            for q in questions:
                q_id = q.get("id", 0)
                correct_answers = [a.strip().upper() for a in q.get("answers", [])]
                student_answer = student_answers[q_id - 1].strip().upper() if q_id <= len(student_answers) else ""
                if student_answer in correct_answers:
                    correct += 1
                else:
                    wrong_questions.append(q_id)
            
            type_stats.append({
                "passage": passage_title,
                "type": type_name,
                "correct": correct,
                "total": total,
                "wrong": wrong_questions
            })
    
    return type_stats


def _format_type_analysis(type_stats):
    """格式化题型分析结果为文本"""
    if not type_stats:
        return "无题型分析数据"
    
    lines = []
    for stat in type_stats:
        pct = f"{stat['correct']}/{stat['total']}"
        wrong_info = f"（错题：{','.join(map(str, stat['wrong']))}）" if stat['wrong'] else ""
        lines.append(f"- {stat['passage']} - {stat['type']}: 正确{pct}{wrong_info}")
    return "\n".join(lines)


def _generate_student_feedback(student_name, grade_result, history_feedback, course_info="", config=None, student_answers=None):
    """调用 LLM 为单个学员生成结班反馈"""
    completion_block = ""
    if grade_result:
        total_correct = grade_result.get("raw_score", 0)
        total_questions = grade_result.get("total_questions", 40)
        band = grade_result.get("ielts_band", "N/A")
        completion_block = f"准确率：共{total_questions}题，正确{total_correct}个\n\n预估雅思对应分数：{band}"
    else:
        completion_block = "学员未参加结班测"

    history_text = ""
    if history_feedback:
        for i, fb in enumerate(history_feedback, 1):
            history_text += f"L{i}: {fb}\n"
    else:
        history_text = "无历史记录"

    # 题型分析
    type_analysis = _analyze_question_types(config, student_answers)
    type_analysis_text = _format_type_analysis(type_analysis)

    prompt = f"""你是雅思阅读教学专家。请根据以下数据为学员 {student_name} 生成结班反馈。

【完成情况】
{completion_block}

【课程信息】
{course_info}

【课堂历史反馈】
{history_text}

【结班测题型分析】
{type_analysis_text}

【任务】
请生成以下三个部分，并严格遵守输出格式标记：

1. ### 【学生优势】
根据数据和历史表现，分析学员优势。要求：2-4 点，每条数据详实。格式严格遵循"数字。 **核心结论**：具体展开"

2. ### 【提升项】
根据错题分布和历史反馈中的问题，分析待提升点。要求：2-4 点，直击痛点。格式严格遵循"数字。 **核心结论**：具体展开"

3. ### 【复习建议】
针对上述提升项，给出可执行的复习计划。要求：2-4 点，具体可量化。格式严格遵循"数字。 **核心结论**：具体展开"

请直接输出内容，不要有多余的问候语。"""

    response = call_llm(
        system_prompt="你是 IELTS 阅读教学反馈生成助手。根据数据生成专业反馈。要求：1.用具体数据 2.结合课堂表现 3.建议可执行 4.输出纯文本，每条一行，数字编号开头",
        user_prompt=prompt
    )

    # 解析响应
    strengths = ""
    improvements = ""
    recommendations = ""

    parts = re.split(r'### 【学生优势】|### 【提升项】|### 【复习建议】', response)
    if len(parts) > 1:
        strengths = parts[1].strip()
    if len(parts) > 2:
        improvements = parts[2].strip()
    if len(parts) > 3:
        recommendations = parts[3].strip()

    if not strengths and not improvements:
        strengths = response

    return {
        "strengths": strengths,
        "improvements": improvements,
        "recommendations": recommendations
    }


def _build_feedback_content(student_name, grade_result, feedback_result):
    """构建完整的 Markdown 反馈内容"""
    if grade_result:
        total_correct = grade_result.get("raw_score", 0)
        total_questions = 40
        band = grade_result.get("ielts_band", "N/A")
        completion_block = f"准确率：共{total_questions}题，正确{total_correct}个\n\n预估雅思对应分数：{band}"
    else:
        completion_block = "学员未参加结班测"

    content = f"#### **【完成情况】**\n\n{completion_block}\n\n"
    content += f"#### **【本阶段学习分析】**\n\n"
    content += f"**学生优势：**\n\n{feedback_result['strengths']}\n\n"
    content += f"**提升项：**\n\n{feedback_result['improvements']}\n\n"
    content += f"#### **【复习建议】**\n\n{feedback_result['recommendations']}\n"

    return content


# ===== 工作流主逻辑 =====

def run_workflow(vault=None, answer_sheet_folder=None, config_file=None, course_type=None):
    """
    结班反馈生成工作流。
    
    Args:
        vault: Vault 根目录（可选，优先使用 .env 中的 XDF_VAULT_PATH）
        answer_sheet_folder: 答题卡文件夹路径（必填），脚本会从中解析班号和课型
        config_file: 测试配置文件路径（可选）
        course_type: 测试类型 A/G（可选，默认从配置或答题卡文件夹名推断）
    """
    if not answer_sheet_folder:
        raise ValueError("请提供 --answer-sheet-folder 参数")

    # 从答题卡文件夹名解析班号和课型
    folder_name = Path(answer_sheet_folder).name
    match = re.match(r'(\d+)[_\s]*(.+)', folder_name)
    if match:
        target = match.group(1)
        parsed_course_type = match.group(2).strip('_- ')
    else:
        target = folder_name
        parsed_course_type = ""

    if course_type is None:
        course_type = parsed_course_type if parsed_course_type else "A"

    # 自动匹配配置文件（如果未手动指定）
    if config_file is None:
        config_file = _resolve_config_file(course_type)

    task_id = str(uuid.uuid4())[:8]
    progress = _init_progress(task_id, "end_of_class_feedback", {
        "target": target,
        "answer_sheet_folder": answer_sheet_folder,
        "config_file": config_file,
        "course_type": course_type
    })

    # 打印 task_id 供 Agent 轮询
    print(json.dumps({"task_id": task_id}, ensure_ascii=False), flush=True)

    try:
        vault_path = str(resolve_vault(vault))

        # Step 1: 初始化结班缓存
        _update_step(progress, 1, "初始化结班缓存", "running")
        cache_result = _init_cache(vault_path, target, answer_sheet_folder, config_file)
        student_count = cache_result["data"]["student_count"]
        image_count = cache_result["data"]["image_count"]
        _update_step(progress, 1, "初始化结班缓存", "completed", {
            "student_count": student_count,
            "image_count": image_count
        })

        # 加载缓存
        cache, cache_path = _load_cache(vault_path, target)
        if cache is None:
            _update_step(progress, 1, "初始化结班缓存", "failed", "缓存加载失败")
            return

        students = cache["students"]
        answer_sheets = cache.get("answer_sheets", {})
        config = cache.get("config", {})

        # 从配置中提取正确答案
        correct_answers = []
        test_type = course_type
        if config:
            test_type = config.get("test_type", "A")
            # 从 sections 中提取正确答案
            for section in config.get("sections", []):
                for group in section.get("question_groups", []):
                    for q in group.get("questions", []):
                        answers = q.get("answers", [])
                        correct_answers.append(answers[0] if answers else "")

        # 获取课程信息
        course_info = ""
        if config:
            info = config.get("course_info", {})
            if info:
                course_info = json.dumps(info, ensure_ascii=False, indent=2)

        # Step 2: OCR 识别答题卡（如果有答题卡则执行）
        if answer_sheets:
            _update_step(progress, 2, "OCR 识别答题卡", "running")
            ocr_results = cache.get("ocr_results", {})
            ocr_errors = []

            def _ocr_student(student_name, image_path):
                try:
                    ocr_result = _ocr_image(vault_path, image_path)
                    return student_name, {
                        "answers": ocr_result["data"]["answers"],
                        "confidence": ocr_result["data"]["confidence"]
                    }, None
                except Exception as e:
                    return student_name, None, f"{student_name}: {str(e)}"

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(_ocr_student, student, answer_sheets[student]): student
                    for student in students if student in answer_sheets
                }
                for future in as_completed(futures):
                    student, result, error = future.result()
                    if result:
                        ocr_results[student] = result
                    else:
                        ocr_errors.append(error)

            if ocr_errors:
                _update_step(progress, 2, "OCR 识别答题卡", "failed",
                             f"部分学员识别失败: {'; '.join(ocr_errors[:3])}")
                raise RuntimeError(f"OCR 识别失败: {'; '.join(ocr_errors[:3])}")

            cache["ocr_results"] = ocr_results
            _update_cache(cache, cache_path)

            ocr_done = sum(1 for s in students if s in ocr_results and "answers" in ocr_results[s])
            _update_step(progress, 2, "OCR 识别答题卡", "completed", {
                "ocr_done": ocr_done,
                "total": len(students)
            })

            # Step 3: 批改 + 估分
            _update_step(progress, 3, "批改 + 估分", "running")
            grade_results = cache.get("grade_results", {})

            for student in students:
                if student in ocr_results and "answers" in ocr_results[student]:
                    student_answers = ocr_results[student]["answers"]
                    if correct_answers and len(correct_answers) == 40:
                        try:
                            grade_result = _grade_answers(correct_answers, student_answers, test_type)
                            grade_results[student] = grade_result["data"]
                        except Exception as e:
                            grade_results[student] = {"error": str(e)}

            cache["grade_results"] = grade_results
            _update_cache(cache, cache_path)

            graded_done = sum(1 for s in students if s in grade_results and "raw_score" in grade_results[s])
            _update_step(progress, 3, "批改 + 估分", "completed", {
                "graded_done": graded_done,
                "total": len(students)
            })
        else:
            # 没有答题卡，跳过 OCR 和批改
            _update_step(progress, 2, "OCR 识别答题卡", "completed", {"skipped": True, "reason": "无答题卡"})
            _update_step(progress, 3, "批改 + 估分", "completed", {"skipped": True, "reason": "无答题卡"})

        # Step 4: 生成结班反馈（从缓存中读取历史反馈）
        _update_step(progress, 4, "生成结班反馈", "running")

        # 创建输出目录
        try:
            class_path = resolve_target(Path(vault_path), target)
        except FileNotFoundError:
            _update_step(progress, 4, "生成结班反馈", "failed", f"班级目录不存在: {target}")
            raise
        output_dir = class_path / f"{target}结班反馈"
        output_dir.mkdir(parents=True, exist_ok=True)

        feedback_files = []

        def _generate_for_student(student):
            grade_result = grade_results.get(student)
            history = cache.get("historical_feedback", {}).get(student, [])
            student_answers = None
            if student in cache.get("ocr_results", {}):
                student_answers = cache["ocr_results"][student].get("answers")

            try:
                fb_result = _generate_student_feedback(
                    student, grade_result, history, course_info, config, student_answers
                )
                content = _build_feedback_content(student, grade_result, fb_result)
                output_path = output_dir / f"{student}.md"
                output_path.write_text(content, encoding="utf-8")
                return str(output_path)
            except Exception as e:
                return f"{student}: {str(e)}"

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(_generate_for_student, student): student for student in students}
            for future in as_completed(futures):
                result = future.result()
                feedback_files.append(result)

        _update_step(progress, 4, "生成结班反馈", "completed", {
            "feedback_files": feedback_files
        })

        _complete_progress(progress)

    except Exception as e:
        _update_step(progress, progress.get("current_step", 0) + 1, "错误", "failed", str(e))
        raise


def main():
    parser = argparse.ArgumentParser(description="结班反馈生成工作流")
    parser.add_argument("--vault", type=str, default=None)
    parser.add_argument("--answer-sheet-folder", type=str, required=True, help="答题卡图像文件夹路径（脚本会从中解析班号和课型）")
    parser.add_argument("--config-file", type=str, help="测试结构 JSON 配置文件路径")
    parser.add_argument("--course-type", type=str, default=None, help="测试类型：A（Academic）或 G（General Training），不传则从文件夹名推断")

    args = parser.parse_args()

    run_workflow(
        vault=args.vault,
        answer_sheet_folder=args.answer_sheet_folder,
        config_file=args.config_file,
        course_type=args.course_type
    )


if __name__ == "__main__":
    main()
