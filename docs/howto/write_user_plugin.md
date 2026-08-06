# 如何编写用户插件

> 面向需要为 IBCI 扩展 Python 模块的开发者。解决"从零编写一个可被 `import` 的用户插件"的具体问题。
> 前置知识：`docs/syntax/11_modules.md`（模块与 import）、Python 基础。

## 目录结构

插件放在工程的 `./plugins` 目录下，一个插件一个子目录：

```
my_project/
├── main.ibci
└── plugins/
    └── my_plugin/
        ├── __init__.py   # 实现类 + 工厂
        └── _spec.py      # 元数据与虚表声明
```

## 最小实现

`_spec.py` 声明函数签名与返回类型：

```python
def __ibcext_metadata__():
    return {"name": "my_plugin", "version": "1.0.0"}

def __ibcext_vtable__():
    return {
        "functions": {
            "greet": {
                "params": [{"name": "name", "type": "str"}],
                "return_type": "str",
            },
        },
        "variables": {},
    }
```

`__init__.py` 提供实现类与工厂：

```python
class Impl:
    def greet(self, name):
        return "Hello, " + name

def create_implementation():
    return Impl()
```

## 在 IBCI 中使用

```ibci
import my_plugin

str msg = my_plugin.greet("Alice")   # "Hello, Alice"
```

## 开发阶段校验

提交前用 SDK 离线检查插件：

```bash
python -c "from ibci_sdk.check import check_plugin; r = check_plugin('plugins/my_plugin'); print(r.errors)"
```

检查项包括：`_spec.py` 存在性、元数据/虚表函数合法性、工厂函数存在性、虚表声明的方法在实现类上存在、参数数量匹配。

## 可选：状态化插件

实现 `IbStatefulPlugin` 协议可在引擎生命周期内持有实例状态（详见 `docs/subsystems/04_plugin_system.md`）。

## 约定与边界

- 插件名不可与内核原生模块（`ai`/`file`/`ihost`/`idbg`/`isys`）重名。
- 插件应保持无状态：可变数据放在实例字段，不放 Python 模块级全局变量（多引擎共享进程时隔离依赖此约定）。
- `import` 必须出现在文件顶部。

## 深入指引

- 插件系统内部设计：`docs/subsystems/04_plugin_system.md`
- 模块语法与 import 约束：`docs/syntax/11_modules.md`
- 插件可见性隔离：`docs/KNOWN_LIMITS.md` §十九
