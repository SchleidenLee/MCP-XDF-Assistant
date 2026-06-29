"""
XDFManager MCP Tools - 公共工具模块
提供档案解析、Frontmatter 读取、路径解析等原子能力
"""

import json
import re
import os
from pathlib import Path
from datetime import datetime

# Auto-load .env file from project root
try:
    from dotenv import load_dotenv
    _script_dir = Path(__file__).resolve().parent
    _env_path = _script_dir.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed, rely on system environment


LESSON_TIME_SLOTS = {
    1: "10:00",
    2: "12:20",
    3: "15:30",
    4: "17:50",
    5: "20:10",  # 仅一对一
}


def parse_schedule_datetime(date_str: str, default_time: str = "00:00") -> str:
    """
    解析排课时间。支持格式：
    - YYYY-MM-DD (默认时间)
    - YYYY-MM-DD HH:MM (显式时间)
    - YYYY-MM-DD N (节次，N=1~5)
    """
    parts = date_str.strip().rsplit(" ", 1)
    date_part = parts[0]
    
    if len(parts) > 1:
        suffix = parts[1]
        if suffix.isdigit() and int(suffix) in LESSON_TIME_SLOTS:
            # 节次模式
            return f"{date_part}T{LESSON_TIME_SLOTS[int(suffix)]}:00+08:00"
        elif ":" in suffix:
            # 显式时间模式
            return f"{date_part}T{suffix}:00+08:00"
    
    return f"{date_part}T{default_time}:00+08:00"


def resolve_vault(vault_path: str | None) -> Path:
    """解析并返回 Vault 绝对路径，支持 Windows 和 WSL 风格路径"""
    if not vault_path:
        vault_path = os.environ.get("XDF_VAULT_PATH")
    if vault_path:
        p = Path(vault_path)
        if not p.exists():
            raise FileNotFoundError(f"Vault 路径不存在: {vault_path}")
        return p.resolve()
    # 默认指向项目下的 current class
    default = Path(__file__).parent.parent / "current class"
    if default.exists():
        return default.resolve()
    raise FileNotFoundError("未找到默认 Vault 路径，请通过 --vault 或 XDF_VAULT_PATH 指定")


def parse_frontmatter(content: str) -> dict:
    """解析 Markdown 文件的 YAML Frontmatter，返回字典"""
    fm = {}
    if not content.startswith("---"):
        return fm
    end = content.find("\n---", 3)
    if end == -1:
        return fm
    fm_text = content[3:end].strip()

    # 简单 YAML 解析：支持 key: value 和 key:\n  - value 格式
    current_key = None
    for line in fm_text.split("\n"):
        stripped = line.rstrip()
        if not stripped:
            continue
        # 列表项
        if stripped.lstrip().startswith("- "):
            if current_key:
                val = stripped.lstrip()[2:].strip().strip('"').strip("'")
                if current_key not in fm:
                    fm[current_key] = []
                if isinstance(fm[current_key], list):
                    fm[current_key].append(val)
            continue
        # key: value
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            # 检测是否是数组开头行（如 tags: 或 tags: []）
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1]
                fm[key] = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
            elif val == "":
                fm[key] = []
                current_key = key
            else:
                fm[key] = val
                current_key = key
    return fm


def read_md_file(path: Path | str) -> tuple[str, dict]:
    """读取 Markdown 文件，返回 (正文, frontmatter)"""
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        return "", {}
    content = p.read_text(encoding="utf-8")
    return content, parse_frontmatter(content)


def extract_table_rows(content: str, header_keyword: str = "姓名") -> list[dict]:
    """从 Markdown 表格中提取数据行，返回字典列表"""
    rows = []
    lines = content.split("\n")
    in_table = False
    headers = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        parts = [p.strip() for p in stripped.split("|")]
        parts = [p for p in parts if p != ""]
        if not parts:
            continue
        if header_keyword in parts[0] or header_keyword in stripped:
            headers = parts
            in_table = True
            continue
        if in_table and ("---" in stripped or "===" in stripped):
            continue
        if in_table and headers:
            row = {}
            for i, h in enumerate(headers):
                row[h] = parts[i] if i < len(parts) else ""
            rows.append(row)
    return rows


def is_class_folder(path: Path) -> bool:
    """判断目录是否为班课档案：包含 {dirname}.md 且 tags 含 #班课档案"""
    control = path / f"{path.name}.md"
    if not control.exists():
        return False
    _, fm = read_md_file(control)
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    return any("班课档案" in t for t in tags)


def is_one_on_one_folder(path: Path) -> bool:
    """判断目录是否为一对一档案：包含 {dirname}.md 且 tags 含 #一对一"""
    control = path / f"{path.name}.md"
    if not control.exists():
        return False
    _, fm = read_md_file(control)
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    return any("一对一" in t for t in tags)


def resolve_target(vault: Path, target_name: str) -> Path:
    """解析目标路径：依次查找 vault/{target}、vault/Current Class/{target}、vault/Archived/{target}"""
    candidates = [
        vault / target_name,
        vault / "Current Class" / target_name,
        vault / "Archived" / target_name,
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    raise FileNotFoundError(f"目标 '{target_name}' 不存在")


def list_lesson_dirs(target_path: Path, target_name: str) -> list[Path]:
    """列出目标目录下的所有 Lesson 子目录，按课次排序"""
    if not target_path.exists():
        return []
    pattern = re.compile(re.escape(target_name) + r"\s+Lesson\s+(\d+)", re.IGNORECASE)
    lessons = []
    for sub in target_path.iterdir():
        if sub.is_dir():
            m = pattern.match(sub.name)
            if m:
                lessons.append((int(m.group(1)), sub))
    lessons.sort(key=lambda x: x[0])
    return [p for _, p in lessons]


def get_lesson_meta(lesson_dir: Path, target_name: str, lesson_num: int) -> dict:
    """读取单次课的主文件，提取元数据"""
    lesson_file = lesson_dir / f"{target_name} Lesson {lesson_num}.md"
    if not lesson_file.exists():
        return {"lesson_num": lesson_num, "date": None, "has_files": {}}

    content, fm = read_md_file(lesson_file)
    date_raw = fm.get("Date", "")
    date_str = None
    if date_raw:
        # 处理 ISO 格式，提取日期部分
        m = re.match(r"(\d{4}-\d{2}-\d{2})", str(date_raw))
        if m:
            date_str = m.group(1)

    # 检查子文件存在性
    has_files = {}
    for name, fname in [
        ("note", f"Note {lesson_num}.md"),
        ("wordlist", f"Wordlist {lesson_num}.md"),
        ("grammar", f"Grammar Note {lesson_num}.md"),
        ("homework", f"Homework {lesson_num}.md"),
        ("quiz", f"Quiz {lesson_num + 1}.md"),
        ("feedback", f"Feedback {lesson_num}.md"),
    ]:
        has_files[name] = (lesson_dir / fname).exists()

    # 反馈状态：检查主文件中的班级反馈和 Feedback 文件
    feedback_status = check_feedback_in_content(content)

    return {
        "lesson_num": lesson_num,
        "date": date_str,
        "has_files": has_files,
        "feedback_status": feedback_status,
        "need_send_feedback": fm.get("need_send_feedback", False) if isinstance(fm.get("need_send_feedback"), bool) else False,
    }


def check_feedback_in_content(content: str) -> dict:
    """检查课程主文件和反馈文件的提交状态"""
    result = {
        "class_feedback_submitted": False,
        "class_feedback_has_content": False,
        "student_feedback_count": 0,
        "students_with_feedback": 0,
    }
    # 检查班级反馈是否已提交（- [x] 提交反馈）
    if re.search(r"-\s*\[x\]\s*提交反馈", content, re.IGNORECASE):
        result["class_feedback_submitted"] = True

    # 检查班级反馈总结是否有 AI 生成内容
    class_fb_match = re.search(
        r"###\s*反馈总结\s*\n<!--\s*AI_GENERATED_START\s*-->(.*?)<!--\s*AI_GENERATED_END\s*-->",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if class_fb_match:
        inner = class_fb_match.group(1).strip()
        if inner and inner not in ("待生成", ""):
            result["class_feedback_has_content"] = True

    return result


def check_feedback_file_status(feedback_path: Path) -> dict:
    """读取 Feedback N.md，统计每位学员的反馈生成状态"""
    if not feedback_path.exists():
        return {"exists": False, "students": 0, "generated": 0, "pending": 0}

    content = feedback_path.read_text(encoding="utf-8")
    # 按二级标题（## 但不是 ###）分割学员块
    blocks = re.split(r"(?=^##(?!\s*#))", content, flags=re.MULTILINE)
    students = 0
    generated = 0
    pending = 0

    for block in blocks:
        name_match = re.search(r"^##(?!\s*#)\s*[👤\s]*(.+)$", block, re.MULTILINE)
        if not name_match:
            continue
        students += 1
        fb_match = re.search(
            r"<!--\s*AI_GENERATED_START\s*-->(.*?)<!--\s*AI_GENERATED_END\s*-->",
            block,
            re.DOTALL | re.IGNORECASE,
        )
        if fb_match:
            inner = fb_match.group(1).strip()
            if inner and inner not in ("待生成", ""):
                generated += 1
            else:
                pending += 1
        else:
            pending += 1

    return {
        "exists": True,
        "students": students,
        "generated": generated,
        "pending": pending,
    }


def extract_raw_from_content(content: str, section_marker: str = "### 原始记录") -> list[str]:
    """从内容中提取原始记录行（通用逻辑，参考 extract_raw.py）"""
    lines = content.split("\n")
    raw_lines = []
    in_raw = False
    current_header = None
    for line in lines:
        stripped = line.strip()
        if stripped == section_marker:
            in_raw = True
            current_header = None
            continue
        if in_raw and re.match(r"^###\s", stripped):
            break
        if in_raw:
            if re.match(r"^####\s", stripped):
                current_header = stripped.replace("####", "").strip()
            elif stripped and stripped != "-":
                item = stripped.lstrip("- ").strip()
                if current_header:
                    raw_lines.append(f"{current_header}: {item}")
                else:
                    raw_lines.append(item)
    return raw_lines


def extract_feedback_from_content(content: str) -> str:
    """提取反馈总结内容"""
    match = re.search(
        r"<!--\s*AI_GENERATED_START\s*-->(.*?)<!--\s*AI_GENERATED_END\s*-->",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return ""


def format_output(status: str, data=None, error: str = "") -> str:
    """统一输出 JSON 格式"""
    return json.dumps(
        {"status": status, "data": data if data is not None else {}, "error": error},
        ensure_ascii=False,
        indent=2,
    )


# =========================
# LLM 调用模块
# =========================

def call_llm(
    messages: list[dict],
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: str = None,
) -> str:
    """
    通用 LLM 调用函数，支持 OpenAI 兼容接口。
    
    环境变量：
        LLM_API_KEY: API 密钥（必填）
        LLM_BASE_URL: API 基础 URL（可选，默认使用 openai 官方）
        LLM_MODEL: 默认模型名（可选，默认 gpt-4o-mini）
    
    Args:
        messages: OpenAI 格式的 messages 列表
        model: 模型名（覆盖环境变量）
        temperature: 温度参数
        max_tokens: 最大 token 数
        response_format: "json" 时强制 JSON 输出
    
    Returns:
        LLM 返回的文本内容
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("请安装 openai 库: pip install openai")

    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        raise ValueError("未设置环境变量 LLM_API_KEY")

    base_url = os.environ.get("LLM_BASE_URL", None)
    model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")

    client = OpenAI(api_key=api_key, base_url=base_url)

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def clean_json_output(raw_text: str) -> str:
    """
    从 LLM 返回的文本中提取纯净的 JSON 字符串。
    处理 Markdown 代码块包裹、前后多余文字等情况。
    """
    # 1. 尝试匹配 Markdown 代码块 (```json ... ``` 或 ``` ... ```)
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_text, re.DOTALL)
    if match:
        clean_text = match.group(1)
    else:
        clean_text = raw_text.strip()

    # 2. 进一步提取：找到第一个 { 和最后一个 } 之间的内容
    start_idx = clean_text.find('{')
    end_idx = clean_text.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        clean_text = clean_text[start_idx : end_idx + 1]

    return clean_text
