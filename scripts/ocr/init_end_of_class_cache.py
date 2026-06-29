#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化结课反馈缓存脚本
扫描班级档案、答题卡图像和测试配置，创建结课反馈缓存 JSON

输入：
  --vault               Vault 根目录
  --target              班级名称（必填）
  --answer-sheet-folder 答题卡图像文件夹路径
  --config-file         测试结构 JSON 配置文件路径

输出（JSON）：
  status: ok | error
  data:
    cache_path: "..."
    student_count: N
    image_count: N
"""

import argparse
import sys
import os
import json
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from xdf_utils import resolve_vault, resolve_target, read_md_file, parse_frontmatter, format_output


def extract_students_from_archive(archive_path: Path) -> list[str]:
    """从班级档案 Markdown 文件中提取学生名单"""
    if not archive_path.exists():
        return []

    content, fm = read_md_file(archive_path)

    # 优先从 frontmatter 中读取
    if "students" in fm:
        students = fm["students"]
        if isinstance(students, str):
            students = [s.strip() for s in students.split(",")]
        return [s for s in students if s]

    # 从表格中提取
    students = []
    lines = content.split("\n")
    in_table = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        parts = [p.strip() for p in stripped.split("|")]
        parts = [p for p in parts if p != ""]
        if not parts:
            continue
        # 检测表头
        if "姓名" in parts[0] or "---" in stripped:
            in_table = True
            if "---" in stripped:
                continue
            continue
        if in_table and parts:
            name = parts[0].strip()
            if name and name not in ("姓名", "---"):
                students.append(name)

    return students


def scan_answer_sheets(folder_path: Path) -> dict[str, str]:
    """扫描答题卡文件夹，按学生姓名匹配图像"""
    if not folder_path.exists():
        return {}

    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    answer_sheets = {}

    for file_path in folder_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in image_extensions:
            # 从文件名提取学生姓名（假设文件名包含学生姓名）
            name = file_path.stem
            # 移除常见的后缀模式
            name = re.sub(r"[_\-](answer|sheet|ocr|scan|img|image|photo)[_\-]?\d*", "", name, flags=re.IGNORECASE)
            name = re.sub(r"[\s_\-]+$", "", name).strip()
            if name:
                answer_sheets[name] = str(file_path)

    return answer_sheets


def read_test_config(config_path: Path) -> dict:
    """读取测试配置 JSON"""
    if not config_path.exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_historical_feedback(class_path: Path, student_names: list[str]) -> dict[str, list[str]]:
    """读取所有课次的历史反馈"""
    feedback = {name: [] for name in student_names}

    # 查找所有 Lesson 目录
    lesson_pattern = re.compile(r"Lesson\s+(\d+)", re.IGNORECASE)
    for sub in class_path.iterdir():
        if not sub.is_dir():
            continue
        m = lesson_pattern.search(sub.name)
        if not m:
            continue

        # 查找 Feedback 文件
        for fb_file in sub.glob("Feedback*.md"):
            if not fb_file.exists():
                continue
            content = fb_file.read_text(encoding="utf-8")
            # 按学生分割反馈块
            blocks = re.split(r"(?=^##\s)", content, flags=re.MULTILINE)
            for block in blocks:
                name_match = re.search(r"^##\s*[👤\s]*(.+)$", block, re.MULTILINE)
                if not name_match:
                    continue
                student_name = name_match.group(1).strip()
                # 匹配学生姓名
                for name in student_names:
                    if name in student_name or student_name in name:
                        # 提取反馈内容
                        fb_match = re.search(
                            r"<!--\s*AI_GENERATED_START\s*-->(.*?)<!--\s*AI_GENERATED_END\s*-->",
                            block,
                            re.DOTALL | re.IGNORECASE,
                        )
                        if fb_match:
                            fb_text = fb_match.group(1).strip()
                            if fb_text and fb_text not in ("待生成", ""):
                                feedback[name].append(fb_text)
                        break

    return feedback


def init_end_of_class_cache(
    vault_path: str | None,
    target: str | None,
    answer_sheet_folder: str | None,
    config_file: str | None,
) -> str:
    """初始化结课反馈缓存"""
    try:
        vault = resolve_vault(vault_path)
    except FileNotFoundError as e:
        return format_output("error", error=str(e))

    # 从答题卡文件夹名解析班号和课型（如果未指定 target）
    class_id = target
    course_type = ""
    if not class_id and answer_sheet_folder:
        folder_name = Path(answer_sheet_folder).name
        match = re.match(r'(\d+)[_\s]*(.+)', folder_name)
        if match:
            class_id = match.group(1)
            course_type = match.group(2).strip('_- ')
        else:
            class_id = folder_name

    if not class_id:
        return format_output("error", error="请指定 --target 或 --answer-sheet-folder")

    # 1. 找到班级文件夹
    try:
        class_path = resolve_target(vault, class_id)
    except FileNotFoundError as e:
        return format_output("error", error=str(e))

    # 2. 提取学生名单
    archive_file = class_path / f"{class_id}.md"
    students = extract_students_from_archive(archive_file)
    if not students:
        return format_output("error", error="未能从班级档案中提取学生名单")

    # 3. 扫描答题卡文件夹
    answer_sheets = {}
    if answer_sheet_folder:
        sheet_path = Path(answer_sheet_folder)
        if not sheet_path.is_absolute():
            sheet_path = vault / sheet_path
        answer_sheets = scan_answer_sheets(sheet_path)

    # 4. 读取测试配置
    config = {}
    if config_file:
        config_path = Path(config_file)
        if not config_path.is_absolute():
            config_path = vault / config_path
        config = read_test_config(config_path)

    # 5. 读取历史反馈
    historical_feedback = read_historical_feedback(class_path, students)

    # 6. 构建缓存结构
    cache_data = {
        "class_name": class_id,
        "course_type": course_type,
        "students": students,
        "answer_sheets": answer_sheets,
        "config": config,
        "historical_feedback": historical_feedback,
        "ocr_results": {},
        "grade_results": {},
    }

    # 7. 保存缓存
    cache_dir = class_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{class_id}_end_of_class.json"
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

    return format_output("ok", data={
        "cache_path": str(cache_path),
        "student_count": len(students),
        "image_count": len(answer_sheets),
    })


def main():
    parser = argparse.ArgumentParser(description="初始化结课反馈缓存")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--target", type=str, default=None, help="班级名称（不传则从答题卡文件夹名解析）")
    parser.add_argument("--answer-sheet-folder", type=str, help="答题卡图像文件夹路径")
    parser.add_argument("--config-file", type=str, help="测试结构 JSON 配置文件路径")
    args = parser.parse_args()

    result = init_end_of_class_cache(
        vault_path=args.vault,
        target=args.target,
        answer_sheet_folder=args.answer_sheet_folder,
        config_file=args.config_file,
    )
    print(result)


if __name__ == "__main__":
    main()
