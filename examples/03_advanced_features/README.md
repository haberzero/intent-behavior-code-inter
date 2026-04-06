# 04 - 特殊功能

本章节介绍 IBCI 的特殊功能，包括动态宿主和插件系统。

## 目录结构

```
04_advanced_features/
├── README.md              # 本文件
├── plugins_demo/          # 插件系统演示
│   ├── main.ibci
│   └── plugins/           # 本地插件
│       ├── calc/
│       └── plugin_info/
└── isolation_demo/       # 隔离机制演示
    ├── parent.ibci
    └── sub_project/      # 子项目（独立沙箱）
        ├── child.ibci
        └── plugins/
```

## 核心概念

### 动态宿主

IBCI 支持**动态宿主**概念，每个脚本可以有自己的项目根目录：

```
parent.ibci
  └── 子项目/
      ├── child.ibci
      └── plugins/
```

子项目的 `child.ibci` 运行时，会使用 `子项目/` 作为项目根目录。

### 插件系统

IBCI 支持通过 `plugins/` 目录扩展功能：

```
my_project/
├── main.ibci
└── plugins/
    ├── my_plugin/
    │   ├── __init__.py
    │   └── _spec.py
    └── another_plugin/
        ├── __init__.py
        └── _spec.py
```

## 学习路径

### 第一步：理解插件系统

```bash
python main.py run examples/04_advanced_features/plugins_demo/main.ibci
```

### 第二步：理解隔离机制

```bash
python main.py run examples/04_advanced_features/isolation_demo/parent.ibci
```

## 插件开发

### 创建插件

1. 在 `plugins/` 下创建插件目录
2. 创建 `__init__.py` 定义插件类
3. 创建 `_spec.py` 定义插件元数据

### 插件示例

```python
# plugins/my_plugin/__init__.py

class MyPlugin:
    def setup(self, capabilities):
        self.capabilities = capabilities

    def my_method(self, arg):
        return f"处理: {arg}"

def create_implementation():
    return MyPlugin()
```

```python
# plugins/my_plugin/_spec.py

def __ibcext_metadata__():
    return {
        "name": "my_plugin",
        "version": "1.0.0",
        "description": "我的插件",
    }

def __ibcext_vtable__():
    return {
        "functions": {
            "my_method": {
                "param_types": ["str"],
                "return_type": "str"
            }
        }
    }
```

## 下一步

- 回到 [01_getting_started](../01_getting_started/README.md) 复习基础
- 学习 [03_basic_modules](../03_basic_modules/README.md) 掌握模块使用
