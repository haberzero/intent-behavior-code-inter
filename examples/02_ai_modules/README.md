# 02 - AI 模块使用介绍

本章节介绍 IBCI 的 AI 相关功能模块，包括 AI 调用和交互式调试。

## 目录结构

```
02_ai_modules/
├── README.md              # 本文件
├── 01_ai_basics.ibci     # AI 基础使用
├── 02_intent_annotation.ibci  # 单行意图注释
└── 03_idbg.ibci          # 交互式调试
```

## 核心概念

### AI 模块

IBCI 提供 `ai` 内置模块，用于与大语言模型交互：

```ibci
import ai

str response = ai.chat("你好，请介绍一下你自己")
print(response)
```

### 单行意图注释

使用 `#@` 语法添加意图注释，用于 AI 理解代码意图：

```ibci
#@ 分析用户情绪，返回积极或消极
str sentiment = ai.analyze("我今天很开心")
```

### idbg 交互式调试

`idbg` 模块提供交互式调试能力：

```ibci
import idbg

idbg.set_trace()
int x = 10
str name = "test"
# 程序会在此处暂停，等待调试命令
```

## 学习路径

### 第一步：了解 AI 基础

```bash
python main.py run examples/02_ai_modules/01_ai_basics.ibci
```

### 第二步：掌握意图注释

```bash
python main.py run examples/02_ai_modules/02_intent_annotation.ibci
```

### 第三步：学习交互调试

```bash
python main.py run examples/02_ai_modules/03_idbg.ibci
```

## 前提条件

使用 AI 模块需要：
1. 配置 LLM API 密钥（通过环境变量或配置文件）
2. 稳定的网络连接
3. 适当的 API 配额

## 下一步

- 学习 [03_basic_modules](../03_basic_modules/README.md) 了解基础模块
- 学习 [04_advanced_features](../04_advanced_features/README.md) 了解特殊功能
