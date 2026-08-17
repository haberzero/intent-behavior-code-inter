## 11. 模块与插件

> 本章描述 IBCI 的模块系统与 import 机制。面向已阅读健壮性章节的开发者。覆盖 import 约束、内置模块（ai/isys/idbg/ihost/file/json）的 API 与插件使用。

### 11.1 import 位置约束

**`import` 语句必须出现在模块文件的顶部**，在任何非 import 语句之前。不允许在函数、类、条件块或循环体内部使用 `import`。`from X import Y` 语法同样受此约束。

```ibci
# 正确：import 在文件顶部
import ai
import json
from json import parse, stringify

int x = 10
func main():
    ...
```

```ibci
# 错误：import 不能出现在函数内或其他语句后面
int x = 10
import ai    # DEP_INVALID_IMPORT_POSITION 编译错误

func main():
    import json  # DEP_INVALID_IMPORT_POSITION 编译错误
```

此约束使编译器能够高效地在不执行代码的前提下进行无副作用的依赖扫描。

**禁止循环导入**：模块间的 `import` 依赖图必须为有向无环图（DAG）。循环导入触发致命编译错误 `DEP_CIRCULAR_IMPORT`。详见 `docs/KNOWN_LIMITS.md §十八`。

**`from mod import *` 冲突行为**：通配符导入时，若模块导出的符号与当前作用域已有的非模块符号同名，发出 `SEM_IMPORT_CONFLICT` WARNING 并跳过该符号（本地定义优先）。与已有模块符号同名时静默跳过。命名导入 `from mod import name` 冲突行为一致。

**模块导出规则**：模块的导出成员仅包含用户定义和显式导入的符号。语言内建（`int`/`str`/`print` 等）不出现在模块导出中——每个模块自动获得这些内建符号，无需跨模块重导出。

### 11.2 内置模块

**内核原生模块**（随内核发行，构造期预注册，不可被用户插件覆盖）：

```ibci
import ai      # LLM provider 配置（API key、model、retry 等）
import isys    # 运行时路径查询（entry_path / entry_dir / project_root）
import idbg    # 调试探查工具
import ihost   # 动态宿主（隔离子环境运行）
import file    # 受限文件系统操作
import iruntime  # 运行时内省（snapshot / subscribe / configure）
```

**随仓库发行插件**（经插件发现机制自动加载；同名冲突按插件发现优先级裁决，
见 §11.6）：

```ibci
import json    # JSON 解析
import math    # 数学函数
import time    # 时间函数
import net     # 网络
```

> **注意**：`@~ ... ~` 行为描述语句是语言核心特性，**不依赖 `import ai`**。`ai` 模块仅负责配置 LLM provider。

### 11.3 ai 模块

配置加载为**显式动作**（F9：引擎启动不再自动加载）。入口调用
`ai.load_project_config()` 加载项目根目录 `api_config.json`；也可显式加载或配置：

```ibci
import ai

# 配置入口（四选一）
ai.load_project_config()                        # 加载 project_root/api_config.json（一等入口，不存在则 no-op）
ai.load_config("./api_config.json")              # 从指定文件加载（路径入口）
ai.apply_config({"default_model": {...}})         # 应用结构化 dict
ai.set_config(url, key, model)                    # 低级位置参数配置

ai.set_retry(3)           # 设置重试次数（默认 3）
ai.set_timeout(30)        # 设置超时（秒）
ai.register_model(name, url, key, model)   # 注册命名模型（供 @NAME~ 路由）
```

MOCK 模式（离线测试/开发，结合 MOCK 指令使用）：

```ibci
ai.set_mock_mode()            # 进入 MOCK 模式（替代 url/key 字符串嗅探）
ai.set_mock_mode(False)       # 退出 MOCK 模式，重建真实客户端
```

`set_mock_mode(enable: bool = True)` 是对称开关：`enable=True`（默认）进入 MOCK
模式；`enable=False` 退出并重新初始化真实客户端（未配置 url/key 时 fail-fast，
不静默停留在半配置状态）。也可经 `ai.set_config(url, key, model)` 或
`ai.apply_config({...})`（`defaults.mock` 为假）退出 MOCK 模式。

其它可用函数：`has_api_key()`、`probe_model()`、`get_retry()`、`is_auto_intent_injection_enabled()`、`set_global_intent(content)`、`clear_global_intents()`、`remove_global_intent(content)`、`get_global_intents()`、`get_current_intent_stack()`、`set_return_type_prompt(type, prompt)`、`get_return_type_prompt(type)`、`get_current_call_info()`、`run_batch()`、`mask(pattern)` 等。

> **`probe_model()` 与推理模型判定**：若在 `api_config.json` 的 `default_model` 声明了 `reasoning: false`（非思考模型）或 `reasoning: true`（强制推理模型），引擎**跳过实际探测**，直接按声明分类（两侧都落能力缓存）。`probe_model()` 是手动探测工具，用启发式判定（专用 reasoning 字段 / "Thinking Process" 特征串 / 输出冗长程度），存在**保守误判**可能——模型无视"只回一词"指令输出冗长内容时会被保守判为强制推理模型。本地非思考模型建议直接声明 `reasoning: false`，而非依赖自动探测。

流式调用（增量渲染）：

```ibci
str full = await ai.stream_call("sys", "MOCK:STREAM:Hello| World|!")
# stream_call(sys_prompt: str, user_prompt: str) -> Waitable，await 后返回完整文本
any h = ai.stream_call("sys", "MOCK:STREAM:Hi| there")   # 赋值自动等待（auto-yield）

chan c = ai.stream_channel("sys", "MOCK:STREAM:Hello| World|!")
# stream_channel(sys_prompt: str, user_prompt: str) -> chan，逐块消费
```

### 11.4 isys 模块

运行时路径查询：入口文件与项目根目录的定位。

```ibci
import isys

str entry  = isys.entry_path()    # 入口文件绝对路径
str dir    = isys.entry_dir()     # 入口文件所在目录
str root   = isys.project_root()  # 项目根目录
```

### 11.5 idbg 模块

调试探查：变量、LLM 调用、重试栈与意图栈的运行时检查。

```ibci
import idbg

int x = 42
idbg.vars()                # 返回当前作用域所有变量及其值（dict）
idbg.print_vars()          # 打印当前作用域所有变量
idbg.current_llm()         # 返回最近一次 LLM 调用的详细信息（dict）
idbg.current_result()      # 返回最近一次 LLM 调用的结果对象
idbg.show_target_prompt()  # 打印最近一次 LLM 调用的提示词
idbg.show_target_result()  # 打印最近一次 LLM 调用的结果
idbg.show_all()            # 打印变量、最近结果等全部调试信息
idbg.retry_stack()       # 返回当前 llmexcept 重试栈
idbg.show_retry_stack()  # 打印当前 llmexcept 重试栈
idbg.protection_map()    # 返回 llmexcept 保护映射（target_uid -> handler_uid）
idbg.show_protection_map() # 打印 llmexcept 保护映射
idbg.intents()           # 返回当前意图栈列表
idbg.show_intents()      # 打印当前意图栈
idbg.env()               # 返回当前运行环境信息
idbg.show_env()          # 打印当前运行环境信息
idbg.fields(obj)         # 返回对象所有字段
```

> **已知限制**：`idbg.inspect(x)` 和 `idbg.dump_intent_stack()` 在当前版本中**未实现**，调用会产生运行时错误。
> 请使用 `idbg.vars()` 代替 `idbg.inspect()`，使用 `idbg.show_intents()` 代替 `idbg.dump_intent_stack()`。

### 11.6 ihost 动态宿主

隔离子环境运行：启动、收集与状态保存/恢复。

```ibci
import ihost
import isys

dict policy = {"isolated": True}
dict result = ihost.run_isolated("./sub/child.ibci", policy)  # 隔离运行子脚本，返回子环境变量字典
str handle = ihost.spawn_isolated("./sub/child.ibci", policy) # 启动子环境（不等待），返回 handle
dict result = ihost.collect(handle)   # 等待子环境完成，返回子环境变量字典
ihost.save_state(path)                # 保存当前状态
ihost.load_state(path)                # 加载状态
str src = ihost.get_source()          # 获取当前入口源码
```

子环境完全独立（独立 Engine 实例、独立插件发现、默认不继承父环境变量）。**LLM provider 配置也不继承**——子环境经 `ai.load_project_config()` 按自身 `project_root` 显式加载 `api_config.json`；子脚本若需真实 LLM，须在子项目目录放置自己的 `api_config.json` 并调用 `ai.load_project_config()`（父环境的 `ai.set_config(...)` / 命名模型配置不传递到子环境）。

### 11.7 file 模块

`file` 模块提供受限文件系统操作；`file_handle` 是只读容器类型，`audio`/`image`/`video` 为其受限子类型（仅可经 `file` 模块访问，不可由用户插件覆盖）。

```ibci
import file

# 创建只读 file_handle
file_handle fh = file.open("data.txt")
str p = fh.path              # field，无 I/O
str content = fh.read()      # method，经沙箱校验后读取文本
list[int] bytes = fh.read_bytes()

# 直接按路径读取
str content2 = file.read("data.txt")

# 统一写入：file.write(target, data, overwrite_flag)
#   overwrite_flag="new"：target 为路径，创建/覆盖，返回 file_handle
#   overwrite_flag="overwrite"：target 为路径或 file_handle，就地覆盖
file_handle copy = file.write("data_v2.txt", "new content")
file.write(fh, "mutated content", overwrite_flag="overwrite")

# 存在检查与删除
bool exists = file.exists("data.txt")
file.remove("data.txt")
```

**只读语义**：`file_handle` 实例没有 `write()` 方法。所有写入必须通过 `file` 模块的自由函数显式完成。

**写入模式的语义区分**（`overwrite_flag`）：
- `"new"`（默认）：`target` 为路径，创建新文件并返回 handle；若目标已存在则覆盖（等价于 Python `open(path, "w")`）。不依赖任何 source handle。
- `"overwrite"`：`target` 为路径或 `file_handle`，显式就地覆盖，所有共享同一 backing 路径的 handle 都会观察到变化。

**安全限制**：
1. 所有 FS I/O 均受沙箱约束（默认禁止越出 `project_root`）。
2. `save_state` 遇到活跃 `file_handle`/`audio`/`image`/`video` 变量时直接报错。
3. `llmexcept` retry body 中禁用 `file.write`（避免污染 gold snapshot；磁盘型快照是浅路径引用，无法静态判别目标是否已入快照）。涉及可能失败的 LLM 调用时，先完成文件写入再进入可能重试的调用。

### 11.8 json 模块

JSON 解析与序列化。

```ibci
import json

str raw = '{"name": "Alice", "age": 30}'
dict parsed = json.parse(raw)
str serialized = json.stringify(parsed)
str pretty = json.pretty(obj)        # 格式化输出
dict merged = json.merge(a, b)       # 合并两个 dict/list
list keys = json.keys(obj)           # 获取 dict 的键列表
list vals = json.values(obj)         # 获取 dict 的值列表
any val = json.get_nested(obj, path) # 按路径取嵌套值
json.set_nested(obj, path, value)    # 按路径设置嵌套值
```

### 11.9 用户插件

插件文件须放置于工程的 `./plugins` 目录，以 Python 编写，通过 `_spec.py` 声明元数据。内核原生模块（`ai`/`file`/`ihost`/`idbg`/`isys`/`iruntime`）不位于插件目录，不可被用户插件覆盖。

### 11.10 宿主绑定（import python）

宿主绑定允许 IBCI 直接导入**裸 Python 模块/包**并显式声明绑定成员，无需 Python 侧
`_spec.py` 契约。这是 F 段远期主线的 F1 成果，走向"用户在 IBCI 侧声明式绑定宿主
内容"（详见 `docs/architecture/01_native_host_binding.md`）。

```ibci
import python "math" as m:
    bind sqrt(x: float) -> float
    bind pow(x: float, y: float) -> float
    bind pi -> float

func test() -> auto:
    float r = m.sqrt(16.0)   # 4.0
    print((str)m.pi)         # 3.141592653589793
```

- `python` 伪模块关键字标记"宿主空间导入"，后跟字符串模块名（任意 Python 模块/包）。
- `bind name(params) -> type`：方法成员（IBCI 签名声明，编译期类型检查 + 运行时
  unbox→调→box 代理）。`bind name -> type`：属性/常量成员（白名单）。
- **显式声明式绑定（非自动穿透）**：只有 `bind` 声明的成员可访问；契约外成员
  fail-fast（运行时 AttributeError）。bind 声明但宿主模块缺失该成员 → 绑定期报错。
- `lib` 是一等值（模块级变量），用户 IBCI 类/`any` 字段可持有并在方法内调用。
- 安全模型与既有插件一致：成员访问强制经 vtable/whitelist 门控，无隐式反射。
---

## 深入指引

- 插件系统内部实现：docs/subsystems/04_plugin_system.md
- 循环导入限制：docs/KNOWN_LIMITS.md §十八
- 插件可见性隔离：docs/KNOWN_LIMITS.md §十九
