#!/usr/bin/env python3
"""日常反馈生成工作流。

通过 subprocess 调用原子脚本串联完成：
  1. find_lesson_files     — 定位课次
  2. extract_raw_records   — 检查 Feedback 文件中的原始记录
  3. extract_content       — 提取授课内容（如需补充）
  4. extract_feedback      — 提取近课反馈（如需补充）
  5. call_llm              — 为每个学员杜撰原始记录
  6. （直接写 Feedback 文件）— 补充原始记录
  7. extract_raw_records   — 完整原始记录
  8. call_llm              — 生成学员反馈
  9. write_feedback        — 写入 AI_GENERATED 块

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

# 添加父目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xdf_utils import resolve_vault, format_output, read_md_file
from llm_utils import call_llm, call_llm_json

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 确保 SCRIPTS_DIR 指向 scripts/ 目录（包含 xdf_utils.py 的目录）
if not os.path.exists(os.path.join(SCRIPTS_DIR, "xdf_utils.py")):
    SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

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
        "total_steps": 5,
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
    # 先尝试解析整个 stdout
    try:
        output_json = json.loads(result.stdout)
    except json.JSONDecodeError:
        # 如果整个解析失败，逐行查找
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


def _find_lesson(vault, target, lesson_num=None, date=None):
    """Step 1: 定位课次"""
    kwargs = {"vault": vault, "target": target}
    if lesson_num:
        kwargs["lesson"] = lesson_num
    if date:
        kwargs["date"] = date
    return _run_script("search/find_lesson_files.py", **kwargs)


def _extract_raw(vault, target, lesson, student=None):
    """Step 2: 提取原始记录"""
    return _run_script("extract/extract_raw_records.py",
                       vault=vault, target=target, lesson=lesson, student=student)


def _extract_content(vault, target, lesson_num, extract_type="all"):
    """Step 3: 提取授课内容等"""
    return _run_script("extract/extract_content.py",
                       vault=vault, target=target, lesson_num=lesson_num, type=extract_type)


def _extract_feedback(vault, target, lesson, student=None):
    """Step 4: 提取反馈内容"""
    return _run_script("extract/extract_feedback.py",
                       vault=vault, target=target, lesson=lesson, student=student)


def _write_feedback(vault, target, lesson_num, json_file):
    """Step 9: 批量写入反馈"""
    return _run_script("write/write_feedback.py",
                       vault=vault, target=target, lesson_num=lesson_num,
                       json_file=json_file)


# ===== Feedback 文件操作 =====

def _extract_students_from_feedback(fb_path):
    """从 Feedback 文件提取学员名（二级标题）"""
    content = fb_path.read_text(encoding="utf-8")
    students = []
    for match in re.finditer(r"^##(?!\s*#)\s*[👤\s]*(.+)$", content, re.MULTILINE):
        name = match.group(1).strip()
        students.append(name)
    return students


def _extract_student_raw_from_feedback(fb_path, student_name):
    """从 Feedback 文件提取指定学员的原始记录"""
    content = fb_path.read_text(encoding="utf-8")
    # 找到学员区块
    pattern = rf"^##(?!\s*#)\s*[👤\s]*{re.escape(student_name)}\s*$"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return []

    start = match.start()
    next_section = re.search(r"^##(?!\s*#)", content[start + 1:], re.MULTILINE)
    if next_section:
        block = content[start: start + 1 + next_section.start()]
    else:
        block = content[start:]

    # 提取 ### 原始记录 下的内容
    raw_match = re.search(r"### 原始记录\s*\n(.*?)(?=###|$)", block, re.DOTALL)
    if not raw_match:
        return []

    raw_content = raw_match.group(1).strip()
    if not raw_content:
        return []

    # 按行提取，跳过空行和 #### 标题
    lines = []
    for line in raw_content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            # 去掉列表标记
            lines.append(line.lstrip("- *"))
    return lines


def _write_student_raw_to_feedback(fb_path, student_name, raw_records):
    """将原始记录写入 Feedback 文件的指定学员区块，按字段分类写入 #### 子区块"""
    content = fb_path.read_text(encoding="utf-8")
    pattern = rf"^##(?!\s*#)\s*[👤\s]*{re.escape(student_name)}\s*$"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return False

    start = match.start()
    next_section = re.search(r"^##(?!\s*#)", content[start + 1:], re.MULTILINE)
    if next_section:
        block = content[start: start + 1 + next_section.start()]
    else:
        block = content[start:]

    # 解析记录，按字段分类
    # 格式如："作业情况：按时提交" → 写入 #### 作业情况
    fields_map = {}
    for record in raw_records:
        # 尝试提取字段名（如 "作业情况：" 或 "作业情况"）
        field_match = re.match(r"^([^：:：]+?)[：:：]\s*(.*)", record)
        if field_match:
            field_name = field_match.group(1).strip()
            field_value = field_match.group(2).strip()
            fields_map.setdefault(field_name, []).append(field_value)
        else:
            # 没有字段名的记录，默认放到"课堂表现"
            fields_map.setdefault("课堂表现", []).append(record)

    # 对每个字段，写入对应的 #### 子区块
    for field_name, values in fields_map.items():
        header = f"#### {field_name}"
        value_text = "\n".join(f"- {v}" for v in values)

        if header in block:
            # 已有该字段，在字段下追加
            # 找到该 #### 的位置
            header_match = re.search(rf"^{re.escape(header)}\s*$", block, re.MULTILINE)
            if header_match:
                # 找到下一个 #### 或 ### 的位置
                next_header = re.search(r"^#{3,4}\s", block[header_match.end():], re.MULTILINE)
                if next_header:
                    insert_pos = header_match.end() + next_header.start()
                    block = block[:insert_pos] + value_text + "\n\n" + block[insert_pos:]
                else:
                    # 没有下一个标题，追加到字段末尾
                    block = block[:header_match.end()] + "\n" + value_text + "\n" + block[header_match.end():]
        else:
            # 没有该字段，找到 ### 原始记录 的位置，在最后添加
            raw_marker = "### 原始记录"
            raw_match = re.search(rf"^{re.escape(raw_marker)}\s*$", block, re.MULTILINE)
            if raw_match:
                # 找到原始记录区域的末尾（下一个 ### 之前）
                next_h3 = re.search(rf"^{re.escape(raw_marker)}\s*\n.*?^(?=###)", block[raw_match.start():], re.MULTILINE | re.DOTALL)
                if next_h3:
                    # 有后续内容，在最后添加
                    insert_pos = raw_match.start() + next_h3.end()
                    block = block[:insert_pos] + f"\n{header}\n{value_text}\n\n" + block[insert_pos:]
                else:
                    # 原始记录区域没有内容，直接在标题后添加
                    block = block[:raw_match.end()] + f"\n{header}\n{value_text}\n" + block[raw_match.end():]

    # 替换原内容
    if next_section:
        content = content[:start] + block + content[start + 1 + next_section.start():]
    else:
        content = content[:start] + block

    fb_path.write_text(content, encoding="utf-8")
    return True


# ===== 工作流主逻辑 =====

def run_workflow(target, vault=None, lesson_num=None, date=None):
    task_id = str(uuid.uuid4())[:8]
    progress = _init_progress(task_id, "daily_feedback", {
        "target": target,
        "lesson": lesson_num,
        "date": date
    })

    # 打印 task_id 供 Agent 轮询
    print(json.dumps({"task_id": task_id}, ensure_ascii=False))

    try:
        vault_path = str(resolve_vault(vault))

        # Step 1: 定位课次
        _update_step(progress, 1, "定位课次", "running")
        lesson_result = _find_lesson(vault_path, target, lesson_num, date)
        if lesson_result["status"] != "ok" or not lesson_result["data"].get("lessons"):
            _update_step(progress, 1, "定位课次", "failed", f"未找到目标 {target} 的课次")
            return
        lesson_info = lesson_result["data"]["lessons"][0]
        actual_lesson = lesson_info["lesson_num"]
        lesson_date = lesson_info.get("date", "")
        _update_step(progress, 1, "定位课次", "completed", {
            "lesson": actual_lesson,
            "date": lesson_date
        })

        # 定位 Feedback 文件
        lesson_dir = Path(vault_path) / target / f"{target} Lesson {actual_lesson}"
        fb_file = lesson_dir / f"Feedback {actual_lesson}.md"
        if not fb_file.exists():
            _update_step(progress, 1, "定位课次", "failed", f"Feedback 文件不存在")
            return

        # Step 2: 检查原始记录（从 Feedback 文件提取学员和他们的原始记录）
        _update_step(progress, 2, "检查原始记录", "running")
        students = _extract_students_from_feedback(fb_file)
        if not students:
            _update_step(progress, 2, "检查原始记录", "failed", "Feedback 文件中未找到学员")
            return

        student_raw_status = {}
        for student in students:
            raw_records = _extract_student_raw_from_feedback(fb_file, student)
            student_raw_status[student] = raw_records

        # 判断哪些学员需要补充原始记录
        students_need_raw = [s for s, records in student_raw_status.items() if len(records) < 3]

        _update_step(progress, 2, "检查原始记录", "completed", {
            "students": students,
            "students_need_raw": students_need_raw
        })

        # Step 3: 补充原始记录（对不足的学员）
        if students_need_raw:
            _update_step(progress, 3, "补充原始记录", "running")

            # 提取授课内容
            content_result = _extract_content(vault_path, target, actual_lesson, "teaching_content")
            teaching_content = content_result["data"]["content"].get("teaching_content", "")

            # 提取近 2 课反馈（只取学员个人的）
            prev_lessons_fb = []
            for prev_lesson in range(max(1, actual_lesson - 2), actual_lesson):
                try:
                    fb_result = _extract_feedback(vault_path, target, str(prev_lesson))
                    if fb_result["status"] == "ok" and fb_result["data"]["lessons"]:
                        prev_lessons_fb.append(fb_result["data"]["lessons"][0])
                except Exception:
                    pass

            # 为每个需要补充的学员调用 LLM 生成原始记录
            generated_raw = {}
            for student in students_need_raw:
                # 提取该学员的历史反馈
                student_prev_fb = []
                for lesson in prev_lessons_fb:
                    for s_fb in lesson.get("students", []):
                        if s_fb.get("name") == student:
                            student_prev_fb.append({
                                "lesson": lesson["lesson_num"],
                                "feedback": s_fb.get("feedback", "")
                            })

                prompt = f"""你是一位雅思老师，需要为学员 {student} 补充课堂原始记录。

授课内容：
{teaching_content}

该学员近2节课的反馈记录：
{json.dumps(student_prev_fb, ensure_ascii=False, indent=2)}

请生成 3-5 条原始记录，格式为：
- 作业情况：...
- 课堂表现：...
- 掌握情况：...

只输出记录行，不要其他内容。"""

                raw_text = call_llm(
                    system_prompt="你是一位雅思教师，负责记录学员课堂情况。",
                    user_prompt=prompt
                )

                # 解析为记录列表
                records = []
                for line in raw_text.split("\n"):
                    line = line.strip().lstrip("- *")
                    if line:
                        records.append(line)

                generated_raw[student] = records

                # 写入 Feedback 文件
                _write_student_raw_to_feedback(fb_file, student, records)

            _update_step(progress, 3, "补充原始记录", "completed", {
                "generated_for": list(generated_raw.keys())
            })

        # Step 4: 生成反馈
        _update_step(progress, 4, "生成反馈", "running")

        # 重新提取完整原始记录
        all_raw = {}
        for student in students:
            raw_records = _extract_student_raw_from_feedback(fb_file, student)
            all_raw[student] = raw_records

        # 构造 prompt 生成每个学员的反馈
        raw_summary = "\n\n".join(
            f"### {student}\n" + "\n".join(all_raw[student])
            for student in students if all_raw[student]
        )

        prompt = f"""你是 Sean 老师，一位资深雅思教师。请根据以下学员的课堂原始记录，为每位学员生成课堂反馈。

原始记录：
{raw_summary}

要求：
1. 语气亲切专业，称呼学员名字
2. 每个学员 100-150 字
3. 包含表现肯定 + 改进建议
4. 输出 JSON 格式：{{"学员名": "反馈内容", ...}}"""

        feedback_json = call_llm_json(
            system_prompt="你是一位资深雅思教师，负责给学员写反馈。",
            user_prompt=prompt
        )

        _update_step(progress, 4, "生成反馈", "completed", {
            "student_count": len(feedback_json)
        })

        # Step 5: 写入反馈
        _update_step(progress, 5, "写入反馈", "running")

        # 构造 JSON 文件用于批量写入
        json_file = os.path.join(PROGRESS_DIR, f"feedback_{task_id}.json")
        write_data = {"students": []}
        for student_name, fb_text in feedback_json.items():
            write_data["students"].append({"name": student_name, "feedback": fb_text})

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(write_data, f, ensure_ascii=False, indent=2)

        _write_feedback(vault_path, target, actual_lesson, json_file)

        # 清理临时文件
        try:
            os.remove(json_file)
        except OSError:
            pass

        _update_step(progress, 5, "写入反馈", "completed")
        _complete_progress(progress)

    except Exception as e:
        _update_step(progress, progress.get("current_step", 0) + 1, "错误", "failed", str(e))
        raise


def main():
    parser = argparse.ArgumentParser(description="日常反馈生成工作流")
    parser.add_argument("--vault", type=str, default=None)
    parser.add_argument("--target", type=str, required=True, help="班级号或学员名")
    parser.add_argument("--lesson", type=int, default=None, help="课次号")
    parser.add_argument("--date", type=str, default=None, help="日期 YYYY-MM-DD")

    args = parser.parse_args()

    if not args.lesson and not args.date:
        print(format_output("error", "需要指定 --lesson 或 --date"))
        sys.exit(1)

    vault = resolve_vault(args.vault)
    run_workflow(args.target, vault, args.lesson, args.date)


if __name__ == "__main__":
    main()
