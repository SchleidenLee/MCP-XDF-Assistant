#!/usr/bin/env python3
"""XDFManagerMCP - MCP Server for 新东方雅思教学档案管理"""

import json
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Use virtual environment's Python interpreter
VENV_PYTHON = Path(__file__).parent / "venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)

from fastmcp import FastMCP

mcp = FastMCP("XDFManagerMCP")

# ===== Helper =====

# 活跃工作流任务映射：task_id -> subprocess.Popen
active_tasks: dict[str, subprocess.Popen] = {}


def _get_vault_path() -> str | None:
    """获取 Vault 路径（从环境变量）"""
    return os.environ.get("XDF_VAULT_PATH")

def _run_script(script_rel_path: str, **kwargs) -> dict:
    """Call atomic script and return parsed JSON result."""
    cmd = [str(VENV_PYTHON), str(SCRIPTS_DIR / script_rel_path)]
    vault = _get_vault_path()
    if vault:
        cmd.extend(["--vault", vault])
    for k, v in kwargs.items():
        if v is not None:
            cmd_key = k.replace("_", "-")
            if isinstance(v, bool):
                if v:
                    cmd.append(f"--{cmd_key}")
            else:
                cmd.append(f"--{cmd_key}")
                cmd.append(str(v))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS_DIR)
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(SCRIPTS_DIR),
        encoding="utf-8", errors="replace", timeout=60, env=env,
        stdin=subprocess.DEVNULL
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
def list_classes() -> str:
    """
    列出所有进行中的班课档案（含 #班课档案 标签）。
    返回每个班级的名称、课型（如初级讲义/中级教材）、排课类型（weekend/weekday）、学员数量等。
    """
    return json.dumps(_run_script("queries/list_classes.py"), ensure_ascii=False)


@mcp.tool()
def list_one_on_one() -> str:
    """
    列出所有进行中一对一学员档案（含 #一对一 标签）。
    返回学员名称、课型、教师等信息。
    """
    return json.dumps(_run_script("queries/list_one_on_one.py"), ensure_ascii=False)


@mcp.tool()
def list_all_students() -> str:
    """
    列出所有学员（班课 + 一对一混排）。
    返回格式：[{name, type(班课/一对一), parent(班级名), course_type}]
    """
    return json.dumps(_run_script("queries/list_all_students.py"), ensure_ascii=False)


@mcp.tool()
def list_lessons(target: str) -> str:
    """
    列出指定班级或一对一的所有课次。
    返回每个课次的课次号、日期、是否需要发送反馈（need_send_feedback）。
    
    Args:
        target: 班级名或一对一学员名（如 "3164" 或 "许宸睿"），必填
    """
    return json.dumps(_run_script("queries/list_lessons.py", target=target), ensure_ascii=False)


@mcp.tool()
def list_student_lessons(student: str) -> str:
    """
    列出指定学员参加的所有课次（跨班级）。
    返回格式：[{class_name, lesson_num, date, feedback_path, need_send_feedback}]
    
    Args:
        student: 学员姓名，必填
    """
    return json.dumps(_run_script("queries/list_student_lessons.py", student=student), ensure_ascii=False)


# ===== Search =====

@mcp.tool()
def find_lessons(target: str, lesson: int = None, date: str = None) -> str:
    """
    定位课次文件夹。通过班级/学员 + 课次号 或 日期 搜索。
    返回课次文件夹的完整路径。
    
    Args:
        target: 班级名或一对一学员名（如 "3164"）
        lesson: 课次号（如 2 表示第2课）
        date: 课次日期（YYYY-MM-DD 格式）
    """
    return json.dumps(_run_script("search/find_lesson_files.py", target=target, lesson=lesson, date=date), ensure_ascii=False)


@mcp.tool()
def get_lesson_detail(target: str, lesson: int) -> str:
    """
    获取课次详情：出勤、原始记录、反馈状态、授课内容、作业等。
    同时返回该课次所有学员的反馈文件路径及反馈状态。
    
    Args:
        target: 班级名或一对一学员名（如 "3164"），必填
        lesson: 课次号（如 2 表示第2课），必填
    """
    return json.dumps(_run_script("search/get_lesson_detail.py", target=target, lesson=lesson), ensure_ascii=False)


# ===== Extract =====

@mcp.tool()
def extract_raw(target: str, lesson: int | str, student: str = None) -> str:
    """
    从 Feedback 文件中提取学员原始记录（出勤、课堂表现、作业情况等）。
    返回格式：{student_name: {field: value}}
    
    Args:
        target: 班级名或一对一学员名（如 "3164"），必填
        lesson: 课次号（如 1）或范围（如 "1-3,5"），必填
        student: 学员姓名（可选，不传则提取所有学员）
    """
    return json.dumps(_run_script("extract/extract_raw_records.py", target=target, lesson=lesson, student=student), ensure_ascii=False)


@mcp.tool()
def extract_feedback(target: str, lesson: int | str, student: str = None) -> str:
    """
    从 Feedback 文件中提取 AI 生成的学员反馈总结（AI_GENERATED 块内容）。
    
    Args:
        target: 班级名或一对一学员名（如 "3164"），必填
        lesson: 课次号（如 1）或范围（如 "1-3,5"），必填
        student: 学员姓名（可选，不传则提取所有学员）
    """
    return json.dumps(_run_script("extract/extract_feedback.py", target=target, lesson=lesson, student=student), ensure_ascii=False)


@mcp.tool()
def extract_content(target: str, lesson: int | str, type: str = "teaching_content") -> str:
    """
    从课次 Lesson 文件中提取授课内容或作业。
    
    Args:
        target: 班级名或一对一学员名（如 "3164"），必填
        lesson: 课次号（如 1）或范围（如 "1-3,5"），必填
        type: 提取类型（"teaching_content"=授课内容，"homework"=作业），默认 "teaching_content"
    """
    return json.dumps(_run_script("extract/extract_content.py", target=target, lesson_num=lesson, type=type), ensure_ascii=False)


# ===== Check Status =====

@mcp.tool()
def check_feedback(target: str) -> str:
    """
    检查指定班级/一对一的反馈提交状态。
    返回每个课次的反馈发送状态（已发送/未发送/未到期）。
    need_send_feedback 判定规则：周末班每节都需反馈，全日制班仅偶数课反馈。
    
    Args:
        target: 班级名或一对一学员名，必填
    """
    return json.dumps(_run_script("check/check_feedback_status.py", target=target), ensure_ascii=False)


@mcp.tool()
def check_todo(target: str) -> str:
    """
    检查指定班级/一对一的待办事项（如未提交作业、未完成的原始记录等）。
    
    Args:
        target: 班级名或一对一学员名，必填
    """
    return json.dumps(_run_script("check/check_todo_status.py", target=target), ensure_ascii=False)


@mcp.tool()
def list_pending() -> str:
    """
    列出所有班级中待发送反馈的课次（全局待办）。
    返回格式：[{class, lesson, date, status}]
    """
    return json.dumps(_run_script("check/list_pending_feedback.py"), ensure_ascii=False)


# ===== Write =====

@mcp.tool()
def write_feedback(target: str, lesson: int, student: str, content: str, feedback_type: str = "student_feedback") -> str:
    """
    写入 AI 生成的学员反馈到 Feedback 文件的 AI_GENERATED 块中。
    如果块已存在则覆盖，不存在则创建。
    
    Args:
        target: 班级名或一对一学员名（如 "3164"），必填
        lesson: 课次号（如 1），必填
        student: 学员姓名，必填
        content: 反馈内容，必填
        feedback_type: 反馈类型（"student_feedback"=学员反馈，"class_feedback"=班级反馈），默认 "student_feedback"
    """
    return json.dumps(_run_script("write/write_feedback.py", target=target, lesson_num=lesson, student_name=student, content=content, feedback_type=feedback_type), ensure_ascii=False)


@mcp.tool()
def write_raw(target: str, lesson: int, student: str, content: str, field: str = None) -> str:
    """
    写入学员原始记录到 Feedback 文件。
    支持按字段（出勤、课堂表现、作业情况等）写入，字段不存在则自动创建。
    
    Args:
        target: 班级名或一对一学员名（如 "3164"），必填
        lesson: 课次号（如 1），必填
        student: 学员姓名，必填
        field: 字段名（如 "课堂表现"、"作业情况"），不传则自动识别
        content: 字段内容，必填
    """
    records = json.dumps([{"field": field or "", "content": content}]) if field else json.dumps([{"content": content}])
    return json.dumps(_run_script("write/write_raw_records.py", target=target, lesson_num=lesson, student=student, records=records), ensure_ascii=False)


@mcp.tool()
def write_teaching_content(target: str, lesson: int, content: str) -> str:
    """
    写入授课内容到课次 Lesson 文件的"授课内容"区块。
    
    Args:
        target: 班级名或一对一学员名（如 "3164"），必填
        lesson: 课次号（如 1），必填
        content: 授课内容，必填
    """
    return json.dumps(_run_script("write/write_teaching_content.py", target=target, lesson_num=lesson, content=content), ensure_ascii=False)


@mcp.tool()
def update_archive_index(target: str) -> str:
    """
    更新班级档案的索引（自动添加缺失的课次链接到"课程记录索引"区块）。
    
    Args:
        target: 班级名或一对一学员名，必填
    """
    return json.dumps(_run_script("write/update_archive_index.py", target=target), ensure_ascii=False)


# ===== Create =====

@mcp.tool()
def create_class(class_name: str, course_type: str, schedule_type: str) -> str:
    """
    创建新的班课档案。
    生成班级主文件（含 Frontmatter、学员名单表格、课程记录索引区块）。
    
    Args:
        class_name: 班级名称/班号（如 "3164"），必填
        course_type: 课型（如 "初级讲义"、"中级教材"），必填
        schedule_type: 排课类型（"weekend"=周末班，"weekday"=全日制），必填
    """
    return json.dumps(_run_script("create/create_class.py", class_name=class_name, course_type=course_type, schedule_type=schedule_type), ensure_ascii=False)


@mcp.tool()
def create_one_on_one(student_name: str, course_type: str) -> str:
    """
    创建新的一对一学员档案。
    
    Args:
        student_name: 学员姓名，必填
        course_type: 课型（如 "初级讲义"、"中级教材"），必填
    """
    return json.dumps(_run_script("create/create_one_on_one.py", student_name=student_name, course_type=course_type), ensure_ascii=False)


@mcp.tool()
def create_class_lesson(target: str, lesson_num: int, date: str, need_feedback: bool = None) -> str:
    """
    为班课创建新课次文件。
    自动创建 Lesson 文件和空的 Feedback 文件。
    need_send_feedback 默认规则：周末班全需要，全日制班仅偶数课需要。
    
    Args:
        target: 班级名，必填
        lesson_num: 课次号（如 2 表示第2课），必填
        date: 课次日期（YYYY-MM-DD），必填
        need_feedback: 是否需要发送反馈（可选，不传则自动计算）
    """
    return json.dumps(_run_script("create/create_class_lesson.py", target=target, lesson_num=lesson_num, date=date, need_feedback=need_feedback), ensure_ascii=False)


@mcp.tool()
def create_one_on_one_lesson(target: str, date: str) -> str:
    """
    为一对一学员创建新课次文件。
    
    Args:
        target: 一对一学员名，必填
        date: 课次日期（YYYY-MM-DD），必填
    """
    return json.dumps(_run_script("create/create_one_on_one_lesson.py", target=target, date=date), ensure_ascii=False)


@mcp.tool()
def create_test_feedback(target: str, test_name: str, date: str, student: str = None, content: str = "") -> str:
    """
    为学员创建测试反馈（如入门测、阶段测、结班测）。
    
    Args:
        target: 班级名或一对一学员名（如 "3164"），必填
        test_name: 测试名称（如 "结班测试"），必填
        date: 测试日期（YYYY-MM-DD），必填
        student: 学员姓名（一对一时不需要，班课时必填）
        content: 测试反馈内容
    """
    return json.dumps(_run_script("create/create_test_feedback.py", target=target, test_name=test_name, date=date, student=student, content=content), ensure_ascii=False)


# ===== Generate Student Summary =====

@mcp.tool()
def generate_student_summary(student: str) -> str:
    """
    生成学员综合汇总（跨所有班级和课次）。
    汇总学员的历史反馈、出勤情况、测试成绩等。
    
    Args:
        student: 学员姓名，必填
    """
    return json.dumps(_run_script("extract/generate_student_summary.py", student=student), ensure_ascii=False)


# ===== Workflows =====

@mcp.tool()
def generate_daily_feedback(target: str, lesson: int = None, date: str = None) -> str:
    """
    【工作流】日常反馈自动生成。
    
    流程：
    1. 定位课次（通过 target + lesson 或 target + date）
    2. 检查原始记录是否完整
    3. 如原始记录不足：提取授课内容 + 近2课学员个人反馈 → LLM 杜撰原始记录 → 写回 Feedback 文件
    4. 提取完整原始记录 → LLM 生成学员反馈 → 写入 AI_GENERATED 块
    
    返回 task_id，可通过 query_task_progress 查询进度。
    
    Args:
        target: 班级名或一对一学员名（如 "3164"），必填
        lesson: 课次号（如 2），与 date 二选一
        date: 课次日期（YYYY-MM-DD），与 lesson 二选一
    """
    cmd = [str(VENV_PYTHON), str(SCRIPTS_DIR / "workflows/daily_feedback_generator.py")]
    vault = _get_vault_path()
    if vault:
        cmd.extend(["--vault", vault])
    if target:
        cmd.extend(["--target", target])
    if lesson:
        cmd.extend(["--lesson", str(lesson)])
    if date:
        cmd.extend(["--date", date])

    # 启动后台进程，立即返回 task_id
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(SCRIPTS_DIR),
        encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
    )
    # 等待第一行输出（task_id）
    import time
    task_id_line = None
    for _ in range(30):
        line = proc.stdout.readline()
        if line:
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    if "task_id" in data:
                        task_id_line = data
                        break
                except json.JSONDecodeError:
                    pass
        time.sleep(0.5)

    if task_id_line:
        active_tasks[task_id_line["task_id"]] = proc
        return json.dumps(task_id_line, ensure_ascii=False)
    else:
        # 如果没拿到 task_id，读取 stderr 看看报了什么错
        proc.terminate()
        _, stderr = proc.communicate()
        return json.dumps({"status": "error", "error": f"未能获取 task_id. 脚本错误输出: {stderr.strip()[:500]}"}, ensure_ascii=False)


@mcp.tool()
def generate_end_of_class_feedback(answer_sheet_folder: str, config_file: str = None, course_type: str = None) -> str:
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
        answer_sheet_folder: 答题卡图片文件夹路径（必填），脚本会自动从中解析班号和课型
        config_file: 题型配置文件路径（可选），不传则根据 course_type 自动匹配
        course_type: 课型（如 "初级讲义"、"中级教材"），用于自动匹配 configs/ 下的 JSON
    """
    cmd = [str(VENV_PYTHON), str(SCRIPTS_DIR / "workflows/end_of_class_feedback_generator.py")]
    vault = _get_vault_path()
    if vault:
        cmd.extend(["--vault", vault])
    if answer_sheet_folder:
        cmd.extend(["--answer-sheet-folder", answer_sheet_folder])
    if config_file:
        cmd.extend(["--config-file", config_file])
    if course_type:
        cmd.extend(["--course-type", course_type])

    # 启动后台进程，立即返回 task_id
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(SCRIPTS_DIR),
        encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
    )
    # 等待第一行输出（task_id）
    import time
    task_id_line = None
    for _ in range(30):
        line = proc.stdout.readline()
        if line:
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    if "task_id" in data:
                        task_id_line = data
                        break
                except json.JSONDecodeError:
                    pass
        time.sleep(0.5)

    if task_id_line:
        active_tasks[task_id_line["task_id"]] = proc
        return json.dumps(task_id_line, ensure_ascii=False)
    else:
        proc.terminate()
        _, stderr = proc.communicate()
        return json.dumps({"status": "error", "error": f"未能获取 task_id. 脚本错误输出: {stderr.strip()[:500]}"}, ensure_ascii=False)


@mcp.tool()
def cancel_task(task_id: str) -> str:
    """
    取消/终止正在运行的工作流任务。
    
    会终止对应的子进程，并将任务进度标记为 cancelled。
    
    Args:
        task_id: 任务 ID（由工作流工具返回），必填
    """
    proc = active_tasks.get(task_id)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        
        # 更新进度文件状态为 cancelled
        progress_dir = SCRIPTS_DIR / "workflows" / "progress"
        progress_file = progress_dir / f"{task_id}.json"
        if progress_file.exists():
            try:
                with open(progress_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["status"] = "cancelled"
                data["steps"] = [
                    {**step, "status": "cancelled"} if step["status"] == "running" else step
                    for step in data.get("steps", [])
                ]
                data["updated_at"] = datetime.now().isoformat()
                with open(progress_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        return json.dumps({"status": "cancelled", "task_id": task_id}, ensure_ascii=False)
    else:
        # 任务不在活跃状态或已结束，直接更新进度文件
        progress_dir = SCRIPTS_DIR / "workflows" / "progress"
        progress_file = progress_dir / f"{task_id}.json"
        if progress_file.exists():
            try:
                with open(progress_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["status"] = "cancelled"
                data["updated_at"] = datetime.now().isoformat()
                with open(progress_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return json.dumps({"status": "cancelled", "task_id": task_id}, ensure_ascii=False)
            except Exception:
                pass
        return json.dumps({"status": "error", "error": f"Task {task_id} not found or already finished"}, ensure_ascii=False)


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
