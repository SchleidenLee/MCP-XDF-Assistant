#!/usr/bin/env python3
"""XDFManagerMCP - MCP Server for 新东方雅思教学档案管理"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from fastmcp import FastMCP

mcp = FastMCP("XDFManagerMCP")

# ===== Helper =====

def _run_script(script_rel_path: str, **kwargs) -> dict:
    """Call atomic script and return parsed JSON result."""
    cmd = [sys.executable, str(SCRIPTS_DIR / script_rel_path)]
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
        cmd, capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        encoding="utf-8", errors="replace"
    )

    # Try to parse JSON output
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

    if output_json:
        return output_json

    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        return {"status": "error", "error": stderr or stdout}

    return {"status": "ok", "data": result.stdout.strip()}


# ===== Queries (list_data) =====

@mcp.tool()
def list_classes(vault: str = None) -> str:
    """
    列出所有进行中的班课档案（含 #班课档案 标签）。
    返回每个班级的名称、课型（如初级讲义/中级教材）、排课类型（weekend/weekday）、学员数量等。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
    """
    return json.dumps(_run_script("queries/list_students.py", vault=vault), ensure_ascii=False)


@mcp.tool()
def list_one_on_one(vault: str = None) -> str:
    """
    列出所有进行中一对一学员档案（含 #一对一 标签）。
    返回学员名称、课型、教师等信息。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
    """
    return json.dumps(_run_script("queries/list_one_on_one.py", vault=vault), ensure_ascii=False)


@mcp.tool()
def list_all_students(vault: str = None) -> str:
    """
    列出所有学员（班课 + 一对一混排）。
    返回格式：[{name, type(班课/一对一), parent(班级名), course_type}]
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
    """
    return json.dumps(_run_script("queries/list_all_students.py", vault=vault), ensure_ascii=False)


@mcp.tool()
def list_lessons(vault: str = None, target: str = None) -> str:
    """
    列出指定班级或一对一的所有课次。
    返回每个课次的课次号、日期、是否需要发送反馈（need_send_feedback）。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        target: 班级名或一对一学员名（如 "3164" 或 "许宸睿"），必填
    """
    return json.dumps(_run_script("queries/list_lessons.py", vault=vault, target=target), ensure_ascii=False)


@mcp.tool()
def list_student_lessons(vault: str = None, student: str = None) -> str:
    """
    列出指定学员参加的所有课次（跨班级）。
    返回格式：[{class_name, lesson_num, date, feedback_path, need_send_feedback}]
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        student: 学员姓名，必填
    """
    return json.dumps(_run_script("queries/list_student_lessons.py", vault=vault, student=student), ensure_ascii=False)


# ===== Search =====

@mcp.tool()
def find_lessons(vault: str = None, target: str = None, lesson: int = None, date: str = None) -> str:
    """
    定位课次文件夹。通过班级/学员 + 课次号 或 日期 搜索。
    返回课次文件夹的完整路径。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        target: 班级名或一对一学员名（如 "3164"）
        lesson: 课次号（如 2 表示第2课）
        date: 课次日期（YYYY-MM-DD 格式）
    """
    return json.dumps(_run_script("search/find_lesson_files.py", vault=vault, target=target, lesson=lesson, date=date), ensure_ascii=False)


@mcp.tool()
def get_lesson_detail(vault: str = None, lesson_dir: str = None) -> str:
    """
    获取课次详情：出勤、原始记录、反馈状态、授课内容、作业等。
    同时返回该课次所有学员的反馈文件路径及反馈状态。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        lesson_dir: 课次文件夹路径（如 "Current Class/3164/3164 Lesson 2"），必填
    """
    return json.dumps(_run_script("search/get_lesson_detail.py", vault=vault, lesson_dir=lesson_dir), ensure_ascii=False)


# ===== Extract =====

@mcp.tool()
def extract_raw(vault: str = None, lesson_dir: str = None, student: str = None) -> str:
    """
    从 Feedback 文件中提取学员原始记录（出勤、课堂表现、作业情况等）。
    返回格式：{student_name: {field: value}}
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        lesson_dir: 课次文件夹路径，必填
        student: 学员姓名（可选，不传则提取所有学员）
    """
    return json.dumps(_run_script("extract/extract_raw_records.py", vault=vault, lesson_dir=lesson_dir, student=student), ensure_ascii=False)


@mcp.tool()
def extract_feedback(vault: str = None, lesson_dir: str = None, student: str = None) -> str:
    """
    从 Feedback 文件中提取 AI 生成的学员反馈总结（AI_GENERATED 块内容）。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        lesson_dir: 课次文件夹路径，必填
        student: 学员姓名（可选，不传则提取所有学员）
    """
    return json.dumps(_run_script("extract/extract_feedback.py", vault=vault, lesson_dir=lesson_dir, student=student), ensure_ascii=False)


@mcp.tool()
def extract_content(vault: str = None, lesson_dir: str = None, type: str = "teaching_content") -> str:
    """
    从课次 Lesson 文件中提取授课内容或作业。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        lesson_dir: 课次文件夹路径，必填
        type: 提取类型，"teaching_content"=授课内容，"homework"=作业记录，默认 teaching_content
    """
    return json.dumps(_run_script("extract/extract_content.py", vault=vault, lesson_dir=lesson_dir, type=type), ensure_ascii=False)


# ===== Check Status =====

@mcp.tool()
def check_feedback(vault: str = None, target: str = None) -> str:
    """
    检查指定班级/一对一的反馈提交状态。
    返回每个课次的反馈发送状态（已发送/未发送/未到期）。
    need_send_feedback 判定规则：周末班每节都需反馈，全日制班仅偶数课反馈。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        target: 班级名或一对一学员名，必填
    """
    return json.dumps(_run_script("check/check_feedback_status.py", vault=vault, target=target), ensure_ascii=False)


@mcp.tool()
def check_todo(vault: str = None, target: str = None) -> str:
    """
    检查指定班级/一对一的待办事项（如未提交作业、未完成的原始记录等）。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        target: 班级名或一对一学员名，必填
    """
    return json.dumps(_run_script("check/check_todo_status.py", vault=vault, target=target), ensure_ascii=False)


@mcp.tool()
def list_pending(vault: str = None) -> str:
    """
    列出所有班级中待发送反馈的课次（全局待办）。
    返回格式：[{class, lesson, date, status}]
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
    """
    return json.dumps(_run_script("check/list_pending_feedback.py", vault=vault), ensure_ascii=False)


# ===== Write =====

@mcp.tool()
def write_feedback(vault: str = None, lesson_dir: str = None, student: str = None, content: str = None) -> str:
    """
    写入 AI 生成的学员反馈到 Feedback 文件的 AI_GENERATED 块中。
    如果块已存在则覆盖，不存在则创建。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        lesson_dir: 课次文件夹路径，必填
        student: 学员姓名，必填
        content: 反馈内容，必填
    """
    return json.dumps(_run_script("write/write_feedback.py", vault=vault, lesson_dir=lesson_dir, student=student, content=content), ensure_ascii=False)


@mcp.tool()
def write_raw(vault: str = None, lesson_dir: str = None, student: str = None, field: str = None, content: str = None) -> str:
    """
    写入学员原始记录到 Feedback 文件。
    支持按字段（出勤、课堂表现、作业情况等）写入，字段不存在则自动创建。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        lesson_dir: 课次文件夹路径，必填
        student: 学员姓名，必填
        field: 字段名（如 "课堂表现"、"作业情况"），不传则创建新字段
        content: 字段内容，必填
    """
    return json.dumps(_run_script("write/write_raw_records.py", vault=vault, lesson_dir=lesson_dir, student=student, field=field, content=content), ensure_ascii=False)


@mcp.tool()
def write_teaching_content(vault: str = None, lesson_dir: str = None, content: str = None) -> str:
    """
    写入授课内容到课次 Lesson 文件的"授课内容"区块。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        lesson_dir: 课次文件夹路径，必填
        content: 授课内容，必填
    """
    return json.dumps(_run_script("write/write_teaching_content.py", vault=vault, lesson_dir=lesson_dir, content=content), ensure_ascii=False)


@mcp.tool()
def update_archive_index(vault: str = None, target: str = None) -> str:
    """
    更新班级档案的索引（自动添加缺失的课次链接到"课程记录索引"区块）。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        target: 班级名或一对一学员名，必填
    """
    return json.dumps(_run_script("write/update_archive_index.py", vault=vault, target=target), ensure_ascii=False)


# ===== Create =====

@mcp.tool()
def create_class(vault: str = None, class_name: str = None, course_type: str = None, schedule_type: str = None) -> str:
    """
    创建新的班课档案。
    生成班级主文件（含 Frontmatter、学员名单表格、课程记录索引区块）。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        class_name: 班级名称/班号（如 "3164"），必填
        course_type: 课型（如 "初级讲义"、"中级教材"），必填
        schedule_type: 排课类型（"weekend"=周末班，"weekday"=全日制），必填
    """
    return json.dumps(_run_script("create/create_class.py", vault=vault, class_name=class_name, course_type=course_type, schedule_type=schedule_type), ensure_ascii=False)


@mcp.tool()
def create_one_on_one(vault: str = None, student_name: str = None, course_type: str = None) -> str:
    """
    创建新的一对一学员档案。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        student_name: 学员姓名，必填
        course_type: 课型（如 "初级讲义"、"中级教材"），必填
    """
    return json.dumps(_run_script("create/create_one_on_one.py", vault=vault, student_name=student_name, course_type=course_type), ensure_ascii=False)


@mcp.tool()
def create_class_lesson(vault: str = None, target: str = None, lesson_num: int = None, date: str = None, need_feedback: bool = None) -> str:
    """
    为班课创建新课次文件。
    自动创建 Lesson 文件和空的 Feedback 文件。
    need_send_feedback 默认规则：周末班全需要，全日制班仅偶数课需要。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        target: 班级名，必填
        lesson_num: 课次号（如 2 表示第2课），必填
        date: 课次日期（YYYY-MM-DD），必填
        need_feedback: 是否需要发送反馈（可选，不传则自动计算）
    """
    return json.dumps(_run_script("create/create_class_lesson.py", vault=vault, target=target, lesson_num=lesson_num, date=date, need_feedback=need_feedback), ensure_ascii=False)


@mcp.tool()
def create_one_on_one_lesson(vault: str = None, target: str = None, date: str = None) -> str:
    """
    为一对一学员创建新课次文件。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        target: 一对一学员名，必填
        date: 课次日期（YYYY-MM-DD），必填
    """
    return json.dumps(_run_script("create/create_one_on_one_lesson.py", vault=vault, target=target, date=date), ensure_ascii=False)


@mcp.tool()
def create_test_feedback(vault: str = None, lesson_dir: str = None, student: str = None, content: str = None) -> str:
    """
    为学员创建测试反馈（如入门测、阶段测）。
    在课次的 Feedback 文件中创建测试反馈区块。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        lesson_dir: 课次文件夹路径，必填
        student: 学员姓名，必填
        content: 测试反馈内容，必填
    """
    return json.dumps(_run_script("create/create_test_feedback.py", vault=vault, lesson_dir=lesson_dir, student=student, content=content), ensure_ascii=False)


# ===== Generate Student Summary =====

@mcp.tool()
def generate_student_summary(vault: str = None, student: str = None) -> str:
    """
    生成学员综合汇总（跨所有班级和课次）。
    汇总学员的历史反馈、出勤情况、测试成绩等。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        student: 学员姓名，必填
    """
    return json.dumps(_run_script("extract/generate_student_summary.py", vault=vault, student=student), ensure_ascii=False)


# ===== Workflows =====

@mcp.tool()
def generate_daily_feedback(vault: str = None, target: str = None, lesson: int = None, date: str = None) -> str:
    """
    【工作流】日常反馈自动生成。
    
    流程：
    1. 定位课次（通过 target + lesson 或 target + date）
    2. 检查原始记录是否完整
    3. 如原始记录不足：提取授课内容 + 近2课学员个人反馈 → LLM 杜撰原始记录 → 写回 Feedback 文件
    4. 提取完整原始记录 → LLM 生成学员反馈 → 写入 AI_GENERATED 块
    
    返回 task_id，可通过 query_task_progress 查询进度。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        target: 班级名或一对一学员名（如 "3164"），必填
        lesson: 课次号（如 2），与 date 二选一
        date: 课次日期（YYYY-MM-DD），与 lesson 二选一
    """
    cmd = [sys.executable, str(SCRIPTS_DIR / "workflows/daily_feedback_generator.py")]
    if vault:
        cmd.extend(["--vault", vault])
    if target:
        cmd.extend(["--target", target])
    if lesson:
        cmd.extend(["--lesson", str(lesson)])
    if date:
        cmd.extend(["--date", date])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS_DIR), encoding="utf-8", errors="replace")
    try:
        return json.dumps(json.loads(result.stdout), ensure_ascii=False)
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "error": result.stderr or result.stdout}, ensure_ascii=False)


@mcp.tool()
def generate_end_of_class_feedback(vault: str = None, answer_sheet_folder: str = None, config_file: str = None, course_type: str = None) -> str:
    """
    【工作流】结班反馈自动生成。
    
    流程：
    1. 初始化结班缓存（读取学员名单、答题卡路径、课程配置、历史反馈）
    2. OCR 识别答题卡图片
    3. 批改答题卡 + 计算 IELTS 分数
    4. 结合批改结果 + 历史反馈 → LLM 生成结班反馈（含学生优势、提升项、复习建议）
    
    自动根据 course_type 从 configs/ 目录匹配题型配置文件。
    返回 task_id，可通过 query_task_progress 查询进度。
    
    Args:
        vault: Obsidian Vault 根目录路径，不传则读取环境变量 XDF_VAULT_PATH
        answer_sheet_folder: 答题卡图片文件夹路径（必填），脚本会自动从中解析班号和课型
        config_file: 题型配置文件路径（可选），不传则根据 course_type 自动匹配
        course_type: 课型（如 "初级讲义"、"中级教材"），用于自动匹配 configs/ 下的 JSON
    """
    cmd = [sys.executable, str(SCRIPTS_DIR / "workflows/end_of_class_feedback_generator.py")]
    if vault:
        cmd.extend(["--vault", vault])
    if answer_sheet_folder:
        cmd.extend(["--answer-sheet-folder", answer_sheet_folder])
    if config_file:
        cmd.extend(["--config-file", config_file])
    if course_type:
        cmd.extend(["--course-type", course_type])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS_DIR), encoding="utf-8", errors="replace")
    try:
        return json.dumps(json.loads(result.stdout), ensure_ascii=False)
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "error": result.stderr or result.stdout}, ensure_ascii=False)


@mcp.tool()
def query_task_progress(task_id: str) -> str:
    """
    查询工作流任务的执行进度。
    返回当前步骤、总步骤数、各步骤状态（running/completed/failed）及详情。
    
    Args:
        task_id: 任务 ID（由工作流工具返回），必填
    """
    return json.dumps(_run_script("queries/query_task_progress.py", task_id=task_id), ensure_ascii=False)


# ===== Run =====

if __name__ == "__main__":
    mcp.run()
