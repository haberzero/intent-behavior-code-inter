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

```ibci
import ai      # LLM provider 配置（API key、model、retry 等）
import isys    # 运行时路径查询（entry_path / entry_dir / project_root）
import idbg    # 调试探查工具
import ihost   # 动态宿主（隔离子环境运行）
import json    # JSON 解析
import file    # 受限文件系统操作
```

> **注意**：`@~ ... ~` 行为描述语句是语言核心特性，**不依赖 `import ai`**。`ai` 模块仅负责配置 LLM provider。

### 11.3 ai 模块

```ibci
import ai

ai.set_config("https://api.example.com", "API_KEY", "model-name")
ai.set_retry(3)           # 设置重试次数（默认 3）
ai.set_timeout(30)        # 设置超时（秒）
ai.register_model(name, url, key, model)   # 注册命名模型（供 @NAME~ 路由）
```

其它可用函数：`has_api_key()`、`probe_model()`、`get_retry()`、`is_auto_intent_injection_enabled()`、`set_global_intent(content)`、`clear_global_intents()`、`remove_global_intent(content)`、`get_global_intents()`、`get_current_intent_stack()`、`set_return_type_prompt(type, prompt)`、`get_return_type_prompt(type)`、`get_current_call_info()`、`run_batch()`、`stream()`、`mask(pattern)` 等。

TESTONLY 模式（结合 MOCK 指令使用）：

```ibci
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
```

### 11.4 isys 模块

```ibci
import isys

str entry  = isys.entry_path()    # 入口文件绝对路径
str dir    = isys.entry_dir()     # 入口文件所在目录
str root   = isys.project_root()  # 项目根目录
```

### 11.5 idbg 模块

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

子环境完全独立（独立 Engine 实例、独立插件发现、默认不继承父环境变量）。

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
list[int] bytes2 = file.read_bytes("data.txt")

# 统一写入：file.write(target, data, overwrite_flag)
#   overwrite_flag="new"（默认）：target 为路径，创建/覆盖文件，返回 file_handle
#   overwrite_flag="overwrite"：target 为路径或 file_handle，就地覆盖，返回 file_handle
# data 为 str（文本）或 list[int]（字节），自动判别
file_handle copy = file.write("data_v2.txt", "new content")
file_handle copy_b = file.write("data_v2.bin", [65, 66])

# 显式副作用写入：覆盖原文件，所有共享该路径引用的变量看到变化
file.write(fh, "mutated content", overwrite_flag="overwrite")
file.write(fh, [65, 66], overwrite_flag="overwrite")

# 创建新文件：无需 source handle，返回指向新文件的只读 handle
file_handle fresh = file.write("data_v3.txt", "brand new")

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

插件文件须放置于工程的 `./plugins` 目录，以 Python 编写，通过 `_spec.py` 声明元数据。内核原生模块（`ai`/`file`/`ihost`/`idbg`/`isys`）不位于插件目录，不可被用户插件覆盖。

---
