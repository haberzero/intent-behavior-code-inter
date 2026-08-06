# IBCI 插件与模块指南

> 本文档详细说明 IBCI 的模块系统、内置模块 API、用户插件开发流程。
> 语法参考见 `docs/SYNTAX_REFERENCE.md` §11（模块与插件基础）。

---

## 1. 模块分类

### 1.1 内核原生模块（kernel-native）

随内核发行，构造期预注册，`IMPORT_GATED`，不可被用户插件覆盖。

| 模块 | 功能 |
|------|------|
| `ai` | LLM provider 配置（API key、model、retry 等） |
| `file` | 受限文件系统操作 |
| `ihost` | 动态宿主（隔离子环境运行） |
| `idbg` | 调试探查工具 |
| `isys` | 运行时状态与路径查询 |

### 1.2 内置用户插件（随仓库发行）

位于 `ibci_modules/` 目录，通过插件发现机制自动加载：

| 插件 | 功能 |
|------|------|
| `ibci_json` | JSON 解析与序列化 |
| `ibci_math` | 数学运算 |
| `ibci_time` | 时间查询 |
| `ibci_schema` | 数据验证 |
| `ibci_net` | 网络请求 |

### 1.3 用户自定义插件

用户可在工程中放置 Python 编写的插件。

---

## 2. 插件发现路径

插件发现按以下优先级搜索：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1（最高） | 内核安装路径 | kernel-native 模块 |
| 2 | `ibci.json` 中 `global_plugin` | 全局插件路径 |
| 3 | `ibci.json` 中 `plugin_paths` | 显式插件路径列表 |
| 4 | 嗅探 | 当 `plugin_paths` 未配置时，自动嗅探以下目录：`./plugins`、`./ibci_modules`、`./.ibci/plugins` |
| 5 | 全局配置（预留） | 尚未实现 |
| 6（最低） | 继承父环境 | 隔离子环境继承父环境的插件路径 |

> 当 `ibci.json` 显式配置了 `plugin_paths` 时，嗅探（优先级 4）不会触发。

---

## 3. 内核原生模块 API

### 3.1 ai 模块

```ibci
import ai

ai.set_config(url, key, model)         # 配置默认 LLM provider
ai.set_retry(count)                     # 设置重试次数（默认 3）
ai.set_timeout(seconds)                 # 设置超时（秒）
ai.register_model(name, url, key, model)  # 注册命名模型
```

其它可用函数：`has_api_key()`、`probe_model()`、`get_retry()`、`is_auto_intent_injection_enabled()`、`set_global_intent(content)`、`clear_global_intents()`、`remove_global_intent(content)`、`get_global_intents()`、`get_current_intent_stack()`、`set_return_type_prompt(type, prompt)`、`get_return_type_prompt(type)`、`get_current_call_info()`、`run_batch()`、`stream()`、`mask(pattern)` 等。

### 3.2 file 模块

详见 `docs/SYNTAX_REFERENCE.md` §11.7。

### 3.3 isys 模块

```ibci
import isys

str entry  = isys.entry_path()         # 入口文件绝对路径
str dir    = isys.entry_dir()          # 入口文件所在目录
str root   = isys.project_root()       # 项目根目录（沙箱边界）
bool sand  = isys.is_sandboxed()       # 是否处于沙箱模式
str ext    = isys.request_external_access()  # 请求外部访问权限
```

### 3.4 idbg 模块

```ibci
import idbg

idbg.vars()                # 返回当前作用域所有变量及值（dict）
idbg.print_vars()          # 打印当前作用域所有变量
idbg.current_llm()         # 返回最近一次 LLM 调用详细信息（dict）
idbg.current_result()      # 返回最近一次 LLM 调用结果对象
idbg.show_target_prompt()  # 打印最近一次 LLM 调用提示词
idbg.show_target_result()  # 打印最近一次 LLM 调用结果
idbg.show_all()            # 打印全部调试信息
idbg.retry_stack()         # 返回当前 llmexcept 重试栈
idbg.show_retry_stack()    # 打印重试栈
idbg.protection_map()      # 返回 llmexcept 保护映射
idbg.show_protection_map() # 打印保护映射
idbg.intents()             # 返回当前意图栈列表
idbg.show_intents()        # 打印意图栈
idbg.env()                 # 返回运行环境信息
idbg.show_env()            # 打印环境信息
idbg.fields(obj)           # 返回对象所有字段
```

> `idbg.inspect(x)` 和 `idbg.dump_intent_stack()` 未实现，调用会产生运行时错误。

### 3.5 ihost 模块

```ibci
import ihost

dict result = ihost.run_isolated(path, policy)   # 隔离运行子脚本，返回子环境变量字典
ihost.save_state(path)                         # 保存当前状态
ihost.load_state(path)                         # 加载状态
str handle = ihost.spawn_isolated(path, policy)   # 启动隔离子环境（不等待），返回 handle
dict result = ihost.collect(handle)             # 等待子环境完成，返回子环境变量字典
str src = ihost.get_source()                   # 获取当前入口源码
```

### 3.6 json 模块

```ibci
import json

dict parsed = json.parse(raw_str)        # 解析 JSON 字符串
str serialized = json.stringify(obj)     # 序列化为 JSON 字符串
str pretty = json.pretty(obj)            # 格式化输出
dict merged = json.merge(a, b)           # 合并两个 dict/list
list keys = json.keys(obj)               # 获取 dict 的键列表
list vals = json.values(obj)             # 获取 dict 的值列表
any val = json.get_nested(obj, path)     # 按路径取嵌套值
json.set_nested(obj, path, value)        # 按路径设置嵌套值
```

---

## 4. 用户插件开发

### 4.1 目录结构

```
my_project/
├── api_config.json
├── main.ibci
└── plugins/              ← 插件目录（自动嗅探）
    └── my_plugin/
        ├── __init__.py   ← 实现入口
        └── _spec.py      ← 元数据声明
```

### 4.2 _spec.py 模板

```python
def __ibcext_metadata__():
    return {
        "name": "my_plugin",
        "version": "1.0.0",
        "description": "My custom plugin",
    }

def __ibcext_vtable__():
    return {
        "functions": {
            "greet": {
                "params": [
                    {"name": "name", "type": "str"},
                    {"name": "punct", "type": "str", "default": "!", "kind": "POSITIONAL_OR_KEYWORD"},
                ],
                "return_type": "str",
            },
        },
        "variables": {},
    }
```

`params` 中每个参数可声明字段：`name`（必填）、`type`（IBCI 类型名）、`default`（默认字面值，声明后参数可选）、`kind`（`POSITIONAL_OR_KEYWORD` 默认 / `VAR_POSITIONAL` / `VAR_KEYWORD` / `KEYWORD_ONLY`）。声明了 `name` 后，IBCI 侧即可对该模块函数进行具名调用与默认值填充；声明的参数名必须被实现函数按名接受（或实现接受 `**kwargs`），否则加载失败。声明 `VAR_KEYWORD`（`**kwargs`）时，实现必须接受 `**kwargs`，未声明的具名实参会在 IBCI 侧归集为 dict 并分传给它。

### 4.3 __init__.py 模板

```python
class Impl:
    def greet(self, name):
        return "Hello, " + name

def create_implementation():
    return Impl()
```

### 4.4 插件检查

使用 `ibci_sdk.check` 模块在开发阶段预检插件：

```python
from ibci_sdk.check import check_plugin

result = check_plugin("plugins/my_plugin")
if not result.ok:
    for err in result.errors:
        print(err)
```

检查项包括：`_spec.py` 存在性、`__ibcext_metadata__`/`__ibcext_vtable__` 函数合法性、`create_implementation()` 工厂函数存在性、vtable 声明的方法在实现类上存在、参数数量匹配、`IbStatefulPlugin` 协议完整性等。

---

## 5. from X import Y 语法

除 `import X` 外，IBCI 也支持 `from X import Y` 语法：

```ibci
from json import parse, stringify
from json import parse as p

dict d = parse('{"a": 1}')
str s = stringify(d)
dict d2 = p('{"b": 2}')
```

支持相对导入（`from . import x`）、别名（`as`）、星号导入（`from x import *`）。所有 import 语句（含 `from...import`）必须出现在文件顶部。
