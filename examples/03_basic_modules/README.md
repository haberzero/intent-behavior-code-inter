# 03 - 基础模块使用介绍

本章节介绍 IBCI 基础模块的使用，包括文件操作、系统能力等。

## 目录结构

```
03_basic_modules/
├── README.md              # 本文件
├── 01_file_operations.ibci # 文件操作
├── 02_sys_module.ibci     # 系统模块
└── 03_config_mock.ibci   # 配置与模拟
```

## 可用模块

### file 模块

文件操作模块，提供读写、搜索等功能：

```ibci
import file

str content = file.read("./data.txt")
file.write("./output.txt", content)
bool exists = file.exists("./data.txt")
```

### sys 模块

系统能力模块，提供路径信息和沙箱控制：

```ibci
import sys

str project_root = sys.project_root()
str script_dir = sys.script_dir()
bool sandboxed = sys.is_sandboxed()
```

### config 模块（可选）

配置管理模块，用于加载配置文件：

```ibci
import config

dict settings = config.load("settings.json")
str api_key = (str)settings["api_key"]
```

## 学习路径

### 第一步：掌握文件操作

```bash
python main.py run examples/03_basic_modules/01_file_operations.ibci
```

### 第二步：了解系统模块

```bash
python main.py run examples/03_basic_modules/02_sys_module.ibci
```

### 第三步：配置管理

```bash
python main.py run examples/03_basic_modules/03_config_mock.ibci
```

## 模块列表

| 模块 | 功能 | 状态 |
|------|------|------|
| `file` | 文件读写、搜索、列表 | ✅ 可用 |
| `sys` | 路径信息、沙箱控制 | ✅ 可用 |
| `config` | 配置加载 | ⏳ 开发中 |

## 下一步

- 学习 [04_advanced_features](../04_advanced_features/README.md) 了解特殊功能
- 学习 [02_ai_modules](../02_ai_modules/README.md) 了解 AI 模块
