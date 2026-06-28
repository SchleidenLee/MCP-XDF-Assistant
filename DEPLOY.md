# XDFManagerMCP 部署说明

## 1. 克隆项目

```bash
git clone https://github.com/SchleidenLee/MCP-XDF-Assistant.git
cd MCP-XDF-Assistant
```

## 2. 创建虚拟环境

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

## 3. 安装依赖

```bash
pip install -r requirements.txt
```

## 4. 配置环境变量

复制 `.env.example` 为 `.env`，填入实际值：

```env
# Obsidian Vault 根目录
XDF_VAULT_PATH=D:\Schleiden\Obsidian\XDF\Current Class

# 通义千问 API Key（用于 LLM 调用）
QWEN_API_KEY=your-qwen-api-key

# OpenAI 兼容 API Key（可选）
OPENAI_API_KEY=your-openai-api-key
```

## 5. 配置题型（可选）

题型配置文件位于 `configs/` 目录，按课型命名：
- 初级教材.json
- 初级讲义.json
- 中级教材.json
- 中级讲义.json

结班反馈工作流会根据 `course_type` 自动匹配对应配置。

## 6. 运行 MCP Server

```bash
python mcp_server.py
```

Server 启动后会通过 stdio 与客户端通信，支持 MCP 协议。

## 7. 客户端配置

在支持 MCP 的客户端（如 Claude Desktop、Cursor 等）中添加：

```json
{
  "mcpServers": {
    "XDFManagerMCP": {
      "command": "python",
      "args": ["path/to/mcp_server.py"]
    }
  }
}
```

## 8. 部署到生产目录

将项目复制到部署目录后，在虚拟环境中安装：

```bash
cd X:\AI\MCP\XDFAssistant
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

然后配置 `.env` 并运行。
