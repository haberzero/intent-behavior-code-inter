# 03 - 高级特性

本章节介绍 IBCI 的高级特性：动态宿主（隔离运行）与插件系统。

## 目录结构

```
03_advanced_features/
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

IBCI 支持**动态宿主**：一段 IBCI 代码可以主动开启一个新脚本的独立编译执行环境，且完全不干扰主环境。子环境的入口文件甚至不需要在主环境启动前存在——允许主环境动态生成子脚本后再切换运行。

```
parent.ibci
  └── 子项目/
      ├── child.ibci
      └── plugins/
```

`child.ibci` 运行时是一个全新的独立 IBCI 实例（独立 Engine、独立插件发现、默认不继承父环境变量）。

### 插件系统

IBCI 支持通过 `plugins/` 目录扩展功能（详见 `docs/ARCHITECTURE.md §七`）：

```
my_project/
├── main.ibci
└── plugins/
    ├── my_plugin/
    │   ├── __init__.py     # create_implementation() 工厂入口
    │   └── _spec.py        # __ibcext_vtable__() 元数据声明
    └── another_plugin/
        ├── __init__.py
        └── _spec.py
```

## 学习路径

### 第一步：插件系统

```bash
python main.py run examples/03_advanced_features/plugins_demo/main.ibci
```

### 第二步：隔离机制

```bash
python main.py run examples/03_advanced_features/isolation_demo/parent.ibci
```

> 隔离示例默认使用 MOCK 模式，可零配置运行。

## 插件开发

### 创建插件

1. 在工程的 `plugins/` 下创建插件目录
2. 创建 `__init__.py` 提供 `create_implementation()` 工厂函数
3. 创建 `_spec.py` 通过 `__ibcext_vtable__()` 声明插件元数据

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

> 内核原生模块（如 `file`/`ai`/`ihost`）不位于插件目录；用户插件参考写法见 `examples/03_advanced_features/custom_plugin_demo/`（如存在）或 `docs/ARCHITECTURE.md` §7。

## 下一步

- 回到 `examples/01_getting_started/01_hello_world.ibci` 复习基础语法
- 学习 `examples/02_basic_modules/` 掌握模块使用
- 完整语法参考见 `docs/SYNTAX_REFERENCE.md`
