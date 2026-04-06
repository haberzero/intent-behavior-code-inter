# 02 - AI 模块使用介绍

本章节介绍 IBCI 的 AI 相关功能模块，包括行为描述语句和意图注释。

## 目录结构

```
02_ai_modules/
├── README.md                    # 本文件
├── 01_ai_basics.ibci          # AI 基础使用
└── 02_intent_annotation.ibci   # 单行意图注释
```

## 核心概念

### AI 模块

IBCI 提供 `ai` 内置模块，用于与大语言模型交互：

```ibci
import ai

# 行为描述语句：直接调用 AI
str response = @~请用一句话介绍 IBCI~
print(response)
```

### 单行意图注释

使用 `#@` 语法添加意图注释，用于 AI 理解代码意图：

```ibci
#@ 分析用户情绪，返回积极或消极
str sentiment = @~判断这句话的情感：今天天气真好~
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

## 关于 idbg 模块

idbg 模块提供**非侵入式**状态查询功能：

- `idbg.vars()` - 获取当前作用域变量
- `idbg.last_llm()` - 获取上次 LLM 调用信息
- `idbg.last_result()` - 获取上次 AI 执行结果

> 注意: idbg 的交互式断点调试功能暂不实现。
> 详见 [IDBG_DESIGN_PRINCIPLES.md](../../IDBG_DESIGN_PRINCIPLES.md)

## 前提条件

使用 AI 模块需要：
1. 配置 LLM API 密钥（通过 `api_config.json` 或环境变量）
2. 稳定的网络连接

## 下一步

- 学习 [03_basic_modules](../03_basic_modules/README.md) 了解基础模块
- 学习 [04_advanced_features](../04_advanced_features/README.md) 了解特殊功能
