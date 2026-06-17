# QQ Auto Reply

基于 LLBot + DeepSeek 的 QQ 自动回复机器人。支持多风格切换、AI 智能回复、好友管理。

## 功能

- **AI 智能回复** — 基于 DeepSeek 大模型，回复自然
- **风格菜单** — 进入聊天后选择回复风格（AI分身 / AI助手 / 丛雨 / 转接本人）
- **多好友支持** — 所有好友私聊自动回复
- **图形化管理** — 可视化好友选择工具
- **自定义提示词** — 可自由修改 AI 回复风格

## 环境要求

- Windows 10 / Windows Server 2012 R2+
- Python 3.10+

## 安装

### 1. 安装 Python 依赖

```bash
cd scripts
pip install -r requirements.txt
```

### 2. 下载 LLBot Desktop

从 [LuckyLilliaBot Release](https://github.com/LLOneBot/LuckyLilliaBot/releases) 下载最新版 `LLBot-Desktop-win-x64.zip`

解压到 `D:\QQ-AutoReply\llbot\`

### 3. 配置

```bash
# 复制配置文件模板
copy config.example.yaml config.yaml
# 编辑 config.yaml，填入你的 DeepSeek API Key
```

### 4. 启动

```bash
# 第一步：启动 LLBot Desktop
# 双击 llbot\llbot.exe，打开 http://127.0.0.1:3080 扫码登录QQ

# 第二步：启动自动回复服务
cd scripts
python main.py
```

## 配置文件说明

| 配置项 | 说明 |
|--------|------|
| `ai.api_key` | DeepSeek API Key [申请地址](https://platform.deepseek.com/) |
| `ai.base_url` | API 地址，兼容 OpenAI 格式的服务均可 |
| `ai.model` | 模型名称，如 `deepseek-chat` |
| `system_prompt` | 默认的 AI 人格提示词 |
| `context_length` | 上下文记忆轮数 |

## 风格菜单

首次发送消息会显示菜单，可选择：

1. **主人的AI分身** — 损友风格，简短回复
2. **AI助手** — 专业风格，回答问题
3. **丛雨（千恋万花）** — 二次元傲娇风格
4. **和本人聊天** — 转接真人

发送「菜单」可重新呼出菜单切换风格。

## 好友管理

运行 `friend_manager.bat` 或 `python friend_selector.py` 可打开图形化管理工具。

也可直接编辑 config.yaml 的 friends 字段。

## 自定义提示词

修改 `config.yaml` 的 `system_prompt` 可改变默认回复风格。

不同好友可设置不同提示词：
```yaml
friends:
  - qq: 123456789
    name: 好友A
    prompt: 用温柔的语气回复
```

## 免责声明

本项目基于第三方 QQ 协议实现，存在账号被限制的风险，请自行评估使用。
建议使用小号，遵守 QQ 使用协议。

## 许可证

MIT
