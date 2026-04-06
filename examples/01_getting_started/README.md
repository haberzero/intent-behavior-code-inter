# 01 - 快速开始

本章节展示 IBCI 的核心特性：**行为描述语句** + **AI 交互**。

## 目录结构

```
01_getting_started/
├── README.md              # 本文件
├── SYNTAX_REFERENCE.md   # 语法参考手册（含切片、字符串方法等）
├── api_config.json       # AI API 配置
├── 01_hello_ai.ibci     # ⭐ 第一个程序：AI 交互
└── 03_path_management.ibci # 路径管理规则
```

## 学习路径

### 第一步：体验 IBCI 的 AI 能力

```bash
python main.py run examples/01_getting_started/01_hello_ai.ibci
```

这将运行一个展示 IBCI 核心特性的程序：
- **行为描述语句** - 描述"做什么"而非"怎么做"
- **LLM 函数调用** - 与 AI 模型实时交互
- **意图注释** - 让 AI 理解代码意图

### 第二步：理解路径管理

```bash
python main.py run examples/01_getting_started/03_path_management.ibci
```

### 第三步：查阅语法参考

打开 [SYNTAX_REFERENCE.md](SYNTAX_REFERENCE.md) 查看完整语法说明，包括：
- 列表和字符串切片
- 字符串查找方法 (`find`, `find_last`)
- 所有基础语法

## 核心概念

### 行为描述语句

IBCI 的核心是**行为描述语句**：

```ibci
# 行为描述：打印问候语
print("你好，世界！")

# 行为描述：计算两个数的和
int sum = 10 + 20
print("10 + 20 = " + (str)sum)
```

### LLM 函数

与 AI 模型交互：

```ibci
import ai

# 向 AI 提问
str response = ai.chat("请用一句话介绍 IBCI")
print(response)
```

### 意图注释

使用 `#@` 语法让代码意图更清晰：

```ibci
#@ 计算购物车总价
float total = 0.0
int i = 0
while i < prices.len():
    total = total + (float)prices[i]
    i = i + 1
```

## 配置 AI

确保 `api_config.json` 中配置了正确的 API：

```json
{
    "default_model": {
        "base_url": "http://127.0.0.1:12234",
        "api_key": "LOCAL",
        "model": "qwen3-30b-a3b-instruct-2507"
    }
}
```

## 下一步

- 学习 [SYNTAX_REFERENCE.md](SYNTAX_REFERENCE.md) 掌握完整语法
- 继续学习 [02_ai_modules](../02_ai_modules/README.md) 深入 AI 功能
