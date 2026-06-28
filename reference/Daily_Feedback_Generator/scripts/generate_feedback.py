#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Feedback Generator for Daily Feedback Skill
使用统一 LLM 接口生成教学反馈，确保 Context 纯净且严格遵循 Prompt 约束。
"""

import json
import os
import sys
import logging
from pathlib import Path

# =========================
# 路径配置与库导入
# =========================
# 从 api_clients 导入 LLM 客户端
# 优先尝试从技能池根目录查找，如果失败则使用绝对路径（针对 CoPaw 环境）
API_CLIENTS_PATH = Path(__file__).parent.parent.parent.parent / "api_clients"
if not API_CLIENTS_PATH.exists():
    API_CLIENTS_PATH = Path("/mnt/x/AI/CoPaw/data/api_clients")
sys.path.insert(0, str(API_CLIENTS_PATH))

try:
    from llm.client import call_llm
except ImportError:
    print("错误: 无法导入 api_clients.llm.client。请检查路径配置。", file=sys.stderr)
    sys.exit(1)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("daily_feedback_generator")

# =========================
# Prompt 模板 (硬编码以确保一致性)
# =========================
SYSTEM_PROMPT = """
# Role
你是一个专业的雅思/英语教学反馈助手。你的任务是根据提供的原始记录，为班级和每位学员生成一份详尽、专业且具有建设性的反馈报告。

# Style Guide (Sean 老师风格规范)

1. **称呼规范**：
   - 统一使用“学员”指代学生，严禁出现具体姓名。
   - 可使用“该学员”、“学员自身”等变体，保持客观。

2. **语气与用词**：
   - **专业克制**：避免过度热情或夸张的形容词。使用“表现良好”、“值得肯定”、“提出表扬”、“不容乐观”等中性偏正向词汇。
   - **精准描述**：多使用雅思教学专业术语，如“扫读定位”、“同义替换识别”、“肌肉记忆”、“篇章结构”、“语感在线”、“兑现为分数”。
   - **建设性建议**：批评时直击痛点但保持礼貌，建议部分要给出方向。

3. **结构逻辑（三段式）**：
   - **第一层（定性/优势）**：评价学员的基础水平（语法/词汇/语感）和课堂状态（专注度/参与度/出勤）。
   - **第二层（定量/短板）**：结合具体题型或技能点指出问题。
   - **第三层（行动/建议）**：给出具体的课后行动指令。

4. **🔥 核心能力：务实扩写 (Pragmatic Expansion)**
   - 你的扩写必须基于教学常识，**严禁**进行无意义的逻辑升华或强行寻找“深层根源”。
   - **拒绝 AI 腔调与模板感**：
     - ❌ 禁止使用：“这反映出...的深层问题”、“其根源在于...”、“从本质上来说...”
     - ❌ **禁止使用列表式建议**：严禁出现“第一、第二、第三”或“首先、其次、最后”。
     - ❌ **禁止虚构量化指标**：除非原始记录中有具体数据，否则不要编造“每天背20个词”、“每周做2篇”等具体数字。
     - ✅ 推荐使用：“建议加强...”、“目前存在...的情况”、“需要重点练习...”、“表现为...”
   - **扩写原则**：
     - 如果记录是“词汇少”，直接说“基础词汇仍有缺口，建议课下以高考3500词为标准进行系统性补充。”
     - 如果记录是“阅读量不够”，直接说“语感尚不稳定，建议通过增加泛读练习来熟悉常见语法结构。”
   - **目标**：让反馈听起来像是一位经验丰富的老师在微信上给家长发的留言，朴实、自然、不啰嗦。

5. **字数要求（硬性指标）**：
   - **学员反馈**：**不得少于 150 字**。如果原始记录简短，必须通过上述“语义扩充”手段充实内容，严禁输出空洞的套话。
   - **班级反馈**：**不得少于 200 字**。需涵盖整体进度、共性问题及后续教学重点。

6. **特殊情况处理**：
   - 若原始记录中包含出勤信息，请在反馈开头单独说明。
   - 若原始记录少于 2 条有效信息，输出：“信息不足，无法生成反馈。”

# Input Data
{{json_input}}

# Output Format
请仅输出一个标准的 JSON 对象，**严禁**使用 Markdown 代码块标记（如 ```json ... ```），**严禁**在 JSON 前后添加任何解释性文字。
{
  "class_feedback": "班级反馈内容...",
  "students": [
    {
      "name": "学员姓名",
      "feedback": "生成的反馈段落..."
    }
  ]
}
"""

def generate_feedback(input_data: dict) -> str:
    """
    调用 LLM 生成反馈
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请根据以下原始记录生成反馈：\n\n{json.dumps(input_data, ensure_ascii=False, indent=2)}"}
    ]
    
    logger.info("正在调用 LLM 生成反馈...")
    try:
        # 使用统一接口，设置较低的 temperature 以保证稳定性
        response = call_llm(
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
            response_format="json"  # 强制 JSON 格式
        )
        return response
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        raise

def clean_json_output(raw_text: str) -> str:
    """
    防御性清洗：从 LLM 返回的文本中提取纯净的 JSON 字符串
    """
    import re
    
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

def main():
    if len(sys.argv) != 2:
        print("用法: python3 generate_feedback.py <input_json_path>")
        sys.exit(1)
        
    input_path = sys.argv[1]
    
    if not os.path.exists(input_path):
        logger.error(f"输入文件不存在: {input_path}")
        sys.exit(1)
        
    # 1. 读取提取后的原始记录
    with open(input_path, 'r', encoding='utf-8') as f:
        input_data = json.load(f)
        
    # 2. 调用 LLM 生成
    try:
        raw_result = generate_feedback(input_data)
        
        # 3. 数据清洗 (双重保险)
        clean_json_str = clean_json_output(raw_result)
        
        # 4. 验证并输出结果
        result_obj = json.loads(clean_json_str)
        print(json.dumps(result_obj, ensure_ascii=False, indent=2))
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败。错误: {e}")
        logger.error(f"清洗后的内容片段: {clean_json_str[:200]}...")
        sys.exit(1)
    except Exception as e:
        logger.error(f"生成过程出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()