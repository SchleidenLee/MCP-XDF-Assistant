#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IELTS 答题卡 OCR 识别脚本
使用多模态 LLM API 识别答题卡图像，提取 40 道题答案

输入：
  --vault     Vault 根目录
  --image     图像文件路径（单张）
  --images    图像文件路径列表（批量）
  --model     LLM 模型名（默认 qwen-vl-plus）

输出（JSON）：
  status: ok | error
  data:
    answers: ["A", "B", ...]  # 40 个答案
    confidence: 0.95
    image_count: N
"""

import argparse
import sys
import os
import json
import base64
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from xdf_utils import resolve_vault, format_output

try:
    import requests
    from PIL import Image
except ImportError:
    print(format_output("error", error="请安装 requests 和 Pillow: pip install requests Pillow"))
    sys.exit(1)


# 图像最大大小（字节），超过此大小需要压缩
MAX_IMAGE_SIZE = 4 * 1024 * 1024  # 4MB


def compress_image_if_needed(image_path: str, max_size: int = MAX_IMAGE_SIZE) -> str:
    """如果图像过大则压缩，返回压缩后的路径"""
    path = Path(image_path)
    if path.stat().st_size <= max_size:
        return image_path

    img = Image.open(image_path)
    width, height = img.size

    # 逐步缩小直到小于 max_size
    ratio = 0.8
    compressed_path = path.parent / f"{path.stem}_ocr_temp.jpg"
    while True:
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        resized = img.resize((new_width, new_height), Image.LANCZOS)
        if img.mode in ("RGBA", "P"):
            resized = resized.convert("RGB")
        resized.save(str(compressed_path), quality=85, optimize=True)
        if compressed_path.stat().st_size <= max_size or ratio < 0.2:
            break
        ratio *= 0.8

    return str(compressed_path)


def encode_image_to_base64(image_path: str) -> str:
    """将图像编码为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_mime_type(image_path: str) -> str:
    """根据文件扩展名返回 MIME 类型"""
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    return mime_map.get(ext, "image/jpeg")


def call_vision_api(image_paths: list[str], model: str) -> str:
    """调用多模态 LLM API 识别答题卡"""
    api_key = os.environ.get("OCR_API_KEY") or os.environ.get("QWEN_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("未设置 OCR_API_KEY、QWEN_API_KEY 或 OPENAI_API_KEY 环境变量")

    base_url = os.environ.get("OCR_API_URL") or os.environ.get("QWEN_BASE_URL") or os.environ.get("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # 构建消息内容
    content = []
    for img_path in image_paths:
        processed_path = compress_image_if_needed(img_path)
        mime_type = get_mime_type(processed_path)
        base64_image = encode_image_to_base64(processed_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"},
        })

    # 添加文本提示（支持所有 IELTS 阅读题型）
    content.append({
        "type": "text",
        "text": (
            "这是一张 IELTS 阅读答题卡。请识别所有 40 道题的答案。\n\n"
            "要求：\n"
            "1. 按题号顺序提取答案（Q1-Q40）\n"
            "2. 填空题直接提取单词\n"
            "3. 判断题识别 T/F/TRUE/FALSE/NG/N.G 等\n"
            "4. 选择题识别 A/B/C/D\n"
            "5. 配标题题识别罗马数字（I, II, III, IV, V, VI, VII, VIII）\n\n"
            "请以 JSON 格式返回，格式为：{\"answers\": [\"答案1\", \"答案2\", ...]}，\n"
            "其中 answers 数组包含 40 个元素，对应第 1 到第 40 题的答案。\n"
            "如果某题无法识别，请填 \"X\"。\n"
            "只返回 JSON，不要其他文字。"
        ),
    })

    messages = [
        {"role": "user", "content": content},
    ]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    # Reference 脚本没有传 temperature 和 max_tokens，避免不兼容参数导致 400
    payload = {
        "model": model,
        "messages": messages,
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    response = requests.post(
        url, headers=headers, json=payload, timeout=(10, 300)
    )
    response.raise_for_status()

    result = response.json()
    return result["choices"][0]["message"]["content"]


def parse_answers(raw_text: str) -> tuple[list[str], float]:
    """从 LLM 返回的文本中解析答案列表和置信度"""
    # 尝试提取 JSON
    clean_text = raw_text.strip()
    match = __import__("re").search(r'```(?:json)?\s*(.*?)\s*```', clean_text, __import__("re").DOTALL)
    if match:
        clean_text = match.group(1)

    start_idx = clean_text.find("{")
    end_idx = clean_text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        clean_text = clean_text[start_idx : end_idx + 1]

    data = json.loads(clean_text)
    answers = data.get("answers", [])

    # 确保答案是 40 个
    if len(answers) < 40:
        answers = answers + ["X"] * (40 - len(answers))
    elif len(answers) > 40:
        answers = answers[:40]

    # 规范化答案
    answers = [a.strip().upper() for a in answers]
    valid_answers = {"A", "B", "C", "D"}
    recognized_count = sum(1 for a in answers if a in valid_answers)
    confidence = recognized_count / len(answers) if answers else 0.0

    return answers, confidence


def ocr_answer_sheet(
    vault_path: str | None,
    image_path: str | None,
    images: list[str] | None,
    model: str,
) -> str:
    """执行答题卡 OCR 识别"""
    try:
        vault = resolve_vault(vault_path)
    except FileNotFoundError as e:
        return format_output("error", error=str(e))

    # 确定要处理的图像列表
    image_list = []
    if image_path:
        p = Path(image_path)
        if not p.is_absolute():
            p = vault / p
        image_list.append(str(p))
    if images:
        for img in images:
            p = Path(img)
            if not p.is_absolute():
                p = vault / p
            image_list.append(str(p))

    if not image_list:
        return format_output("error", error="请提供 --image 或 --images 参数")

    try:
        raw_response = call_vision_api(image_list, model)
        answers, confidence = parse_answers(raw_response)

        return format_output("ok", data={
            "answers": answers,
            "confidence": round(confidence, 2),
            "image_count": len(image_list),
        })
    except Exception as e:
        return format_output("error", error=str(e))


def main():
    parser = argparse.ArgumentParser(description="IELTS 答题卡 OCR 识别")
    parser.add_argument("--vault", type=str, default=None, help="Vault 根目录路径")
    parser.add_argument("--image", type=str, help="图像文件路径（单张）")
    parser.add_argument("--images", nargs="+", help="图像文件路径列表（批量）")
    parser.add_argument("--model", type=str, default="qwen3.6-plus", help="LLM 模型名（默认 qwen3.6-plus）")
    args = parser.parse_args()

    result = ocr_answer_sheet(
        vault_path=args.vault,
        image_path=args.image,
        images=args.images,
        model=args.model,
    )
    print(result)


if __name__ == "__main__":
    main()
