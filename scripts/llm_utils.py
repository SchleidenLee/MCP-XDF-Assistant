"""
LLM 调用公共工具模块
提供 LLM API 调用和 JSON 响应解析功能
支持 LLM（纯文本）和 OCR（多模态）两种模型
"""

import json
import os
import re
from pathlib import Path
from openai import OpenAI

# Auto-load .env file from project root
try:
    from dotenv import load_dotenv
    _script_dir = Path(__file__).resolve().parent
    _env_path = _script_dir.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=True)
except ImportError:
    pass  # python-dotenv not installed, rely on system environment


def _get_client(api_url: str = None, api_key: str = None) -> OpenAI:
    """获取 OpenAI 客户端实例。"""
    url = api_url or os.environ.get("LLM_API_URL")
    key = api_key or os.environ.get("LLM_API_KEY")
    if not url or not key:
        raise ValueError("未配置 LLM_API_URL 或 LLM_API_KEY，请设置环境变量或在 MCP 启动配置中指定。")
    return OpenAI(base_url=url, api_key=key)


def _get_ocr_client(api_url: str = None, api_key: str = None) -> OpenAI:
    """获取 OCR 多模态客户端实例。"""
    url = api_url or os.environ.get("OCR_API_URL") or os.environ.get("LLM_API_URL")
    key = api_key or os.environ.get("OCR_API_KEY") or os.environ.get("LLM_API_KEY")
    if not url or not key:
        raise ValueError("未配置 OCR_API_URL 或 OCR_API_KEY。")
    return OpenAI(base_url=url, api_key=key)


def call_llm(system_prompt: str, user_prompt: str, model: str = None, **kwargs) -> str:
    """
    调用 LLM API（纯文本）。
    
    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        model: 模型名（默认使用 LLM_MODEL 环境变量）
        **kwargs: 额外参数（temperature, max_tokens 等）
    
    Returns:
        LLM 返回的文本内容
    """
    client = _get_client()
    model_name = model or os.environ.get("LLM_MODEL", "qwen-plus")
    
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=kwargs.get("temperature", 0.7),
        max_tokens=kwargs.get("max_tokens", 4096),
    )
    
    return response.choices[0].message.content or ""


def call_llm_json(system_prompt: str, user_prompt: str, model: str = None, **kwargs) -> dict:
    """
    调用 LLM 并解析 JSON 响应。
    """
    raw_response = call_llm(system_prompt, user_prompt, model=model, **kwargs)
    
    # 清理 Markdown 代码块
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_response, re.DOTALL)
    if match:
        clean_text = match.group(1)
    else:
        clean_text = raw_response.strip()
    
    start_idx = clean_text.find('{')
    end_idx = clean_text.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        clean_text = clean_text[start_idx : end_idx + 1]
    
    return json.loads(clean_text)


def call_ocr(image_paths: list[str], user_prompt: str, model: str = None, **kwargs) -> str:
    """
    调用 OCR 多模态 API。
    
    Args:
        image_paths: 图片文件路径列表
        user_prompt: 用户提示词
        model: 模型名（默认使用 OCR_MODEL 环境变量）
        **kwargs: 额外参数
    
    Returns:
        OCR 返回的文本内容
    """
    client = _get_ocr_client()
    model_name = model or os.environ.get("OCR_MODEL", "qwen-vl-max")
    
    messages = [{"role": "user", "content": []}]
    
    for img_path in image_paths:
        import base64
        with open(img_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        ext = os.path.splitext(img_path)[1].lstrip(".").lower()
        mime = f"image/{ext}" if ext in ("jpg", "jpeg", "png", "webp") else "image/jpeg"
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{encoded}"},
        })
    
    messages[0]["content"].append({"type": "text", "text": user_prompt})
    
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=kwargs.get("temperature", 0.3),
        max_tokens=kwargs.get("max_tokens", 4096),
    )
    
    return response.choices[0].message.content or ""
