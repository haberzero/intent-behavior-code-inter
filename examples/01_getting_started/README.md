# 01 - 快速开始

本章节介绍 IBCI 的原生语法基础，不涉及任何 AI 相关功能。

## 目录结构

```
01_getting_started/
├── README.md              # 本文件
├── 01_hello_world.ibci   # 第一个程序：你好，世界
├── 02_variables.ibci     # 变量与类型
├── 03_operators.ibci     # 运算符与表达式
├── 04_control_flow.ibci   # 控制流
├── 05_functions.ibci     # 函数定义
├── 06_lists.ibci         # 列表操作
├── 07_strings.ibci       # 字符串操作
├── 08_slicing.ibci       # 切片语法
└── 09_path_management.ibci # 路径管理规则
```

## 学习路径

### 第一步：运行你的第一个程序

```bash
python main.py run examples/01_getting_started/01_hello_world.ibci
```

### 第二步：理解变量与类型

```bash
python main.py run examples/01_getting_started/02_variables.ibci
```

### 第三步：掌握控制流

```bash
python main.py run examples/01_getting_started/04_control_flow.ibci
```

### 第四步：理解路径管理

路径管理是 IBCI 的核心特性之一，详见 `09_path_management.ibci`。

## 核心概念

### 行为描述语句

IBCI 的核心是**行为描述语句**，用于描述"做什么"而非"怎么做"：

```ibci
# 行为描述：获取用户输入并打印
str name = input("请输入你的名字：")
print("你好，" + name)
```

### 类型系统

IBCI 是强类型语言，主要类型包括：

| 类型 | 说明 | 示例 |
|------|------|------|
| `int` | 整数 | `int age = 25` |
| `float` | 浮点数 | `float pi = 3.14` |
| `str` | 字符串 | `str name = "Alice"` |
| `bool` | 布尔值 | `bool flag = true` |
| `list` | 列表 | `list items = ["a", "b"]` |
| `dict` | 字典 | `dict data = {"key": "value"}` |

### 路径管理

IBCI 有自己独立的路径管理体系，与 Python 解耦：

```ibci
import sys

str project_root = sys.project_root()    # 项目根目录
str script_dir = sys.script_dir()        # 脚本所在目录
```

详细说明请参考 `09_path_management.ibci`。

## 下一步

- 继续学习 [02_operators.ibci](01_operators.ibci) 掌握运算符
- 学习 [05_functions.ibci](05_functions.ibci) 定义自己的函数
- 学习 [06_lists.ibci](06_lists.ibci) 和 [08_slicing.ibci](08_slicing.ibci) 处理数据集合
