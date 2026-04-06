# IBCI 示例集

IBCI (Intent-Behavior Code Interoperation) 编程语言的示例集合。

## 目录结构

```
examples/
├── 01_getting_started/     # 快速开始
├── 02_ai_modules/          # AI 模块
├── 03_basic_modules/       # 基础模块
├── 04_advanced_features/   # 高级功能
├── path_management_report.md # 路径管理报告
└── README.md               # 本文件
```

## 学习路径

### 第一步：快速开始

从基础开始，学习 IBCI 的原生语法。

📖 [进入 01_getting_started](01_getting_started/README.md)

### 第二步：掌握基础模块

学习使用文件操作、系统能力等基础模块。

📖 [进入 03_basic_modules](03_basic_modules/README.md)

### 第三步：了解 AI 功能

学习 AI 模块、意图注释和交互调试。

📖 [进入 02_ai_modules](02_ai_modules/README.md)

### 第四步：探索高级功能

深入了解插件系统和动态宿主。

📖 [进入 04_advanced_features](04_advanced_features/README.md)

## 按需学习

### 想学习基础语法？

从 `01_getting_started/01_hello_world.ibci` 开始，逐步学习：
- 变量与类型
- 运算符与表达式
- 控制流
- 函数定义
- 列表与字符串
- 切片语法
- 路径管理

### 想学习文件操作？

查看 `03_basic_modules/01_file_operations.ibci`，学习：
- 文件读写
- 文件搜索
- 路径操作

### 想学习 AI 功能？

查看 `02_ai_modules/`，学习：
- AI 基础调用
- 意图注释
- 交互调试

### 想扩展功能？

查看 `04_advanced_features/plugins_demo/`，学习：
- 插件开发
- 插件注册
- 本地插件

## 运行示例

```bash
# 运行第一个示例
python main.py run examples/01_getting_started/01_hello_world.ibci

# 运行文件操作示例
python main.py run examples/03_basic_modules/01_file_operations.ibci

# 运行插件演示
python main.py run examples/04_advanced_features/plugins_demo/main.ibci
```

## 文档

- [路径管理健康报告](path_management_report.md) - IBCI 路径管理体系详解

## 前提条件

1. 安装 Python 3.8+
2. 克隆 IBCI 仓库
3. 确保 `main.py` 可执行

```bash
python main.py --help
```

## 贡献

欢迎提交新的示例！请确保：
1. 代码清晰，有适当的注释
2. 包含 README 说明
3. 按主题分类到对应目录
