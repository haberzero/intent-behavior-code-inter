## 11. 模块与插件

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
import ai    # DEP_003 编译错误

func main():
    import json  # DEP_003 编译错误
```

此约束使调度器（Scheduler）能够高效地在不执行代码的前提下进行无副作用的依赖扫描。

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
```

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
idbg.vars()              # 返回当前作用域所有变量及其值（dict）
idbg.print_vars()        # 打印当前作用域所有变量
idbg.last_llm()          # 返回最后一次 LLM 调用的详细信息（dict）
idbg.last_result()       # 返回最后一次 LLM 调用的结果对象
idbg.show_last_prompt()  # 打印最后一次 LLM 调用的提示词
idbg.show_last_result()  # 打印最后一次 LLM 调用的结果
idbg.show_all()          # 打印变量、最后结果等全部调试信息
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
ihost.run_isolated("./sub/child.ibci", policy)
```

子环境完全独立（独立 Engine 实例、独立插件发现、默认不继承父环境变量）。

### 11.7 file 模块

`file` 模块提供受限文件系统操作；`file_handle` 是只读容器类型，`audio`/`image`/`video` 为其 IMPORT_GATED 子类型。

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

# Copy-on-write：创建新文件，原 handle 及其所有别名不受影响
file_handle copy = file.write_copy(fh, "data_v2.txt", "new content")
file_handle copy_b = file.write_copy_bytes(fh, "data_v2.bin", [65, 66])

# 显式副作用写入：覆盖原文件，所有共享该路径引用的变量看到变化
file.write_overwrite(fh, "mutated content")
file.write_overwrite_bytes(fh, [65, 66])

# 创建新文件：无需 source handle，返回指向新文件的只读 handle
file_handle fresh = file.write_new("data_v3.txt", "brand new")
file_handle fresh_b = file.write_new_bytes("data_v3.bin", [65, 66])

# 存在检查与删除
bool exists = file.exists("data.txt")
file.remove("data.txt")
```

**只读语义**：`file_handle` 实例没有 `write()` 方法。所有写入必须通过 `file` 模块的自由函数显式完成。

**三种写入的语义区分**：
- `write_copy` / `write_copy_bytes`：以已有 handle/路径为 lineage 创建新文件，不污染任何现有 handle；适合在 `llmexcept` retry 等需要隔离副作用的场景使用。
- `write_overwrite` / `write_overwrite_bytes`：显式副作用，覆盖已有文件，所有共享同一 backing 路径的 handle 都会观察到变化。
- `write_new` / `write_new_bytes`：从无到有创建新文件，不需要 source handle；若目标已存在则覆盖（等价于 Python `open(path, "w")`）。

**安全限制**：
1. 所有 FS I/O 均受 `PermissionManager` 沙箱约束（默认禁止越出 `project_root`）。
2. `save_state` 遇到活跃 `file_handle`/`audio`/`image`/`video` 变量时直接报错。
3. `llmexcept` retry body 中禁用 `write_overwrite` / `write_overwrite_bytes`（避免污染 gold snapshot）。涉及可能失败的 LLM 调用时，优先使用 `write_copy` 或 `write_new` 生成新文件。

**未来 API 演进（待函数动态/命名参数支持后）**：
`file.write(target, data, overwrite_flag="copy"|"overwrite"|"new")` 将统一当前三种写入函数，默认 `"overwrite"`。

### 11.8 json 模块

```ibci
import json

str raw = '{"name": "Alice", "age": 30}'
dict parsed = json.parse(raw)
str serialized = json.stringify(parsed)
```

### 11.9 用户插件

插件文件须放置于工程的 `./plugins` 目录，以 Python 编写，通过 `_spec.py` 声明元数据。内核原生模块（`ai`/`file`/`ihost`/`idbg`/`isys`）不位于插件目录，不可被用户插件覆盖。

---
