## 11. 模块与宿主绑定

> 本章描述 IBCI 的模块系统与 import 机制。面向已阅读健壮性章节的开发者。覆盖 import 约束、内置模块（ai/isys/idbg/ihost/file/json 等）的 API 与宿主绑定。

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

**模块路径解析**：用户模块（`.ibci` 文件）的 `import` 解析遵循两级搜索——
① **导入方文件所在目录**（同目录模块：多文件用例的入口目录模块可直接解析，
如 `cases/d02/main.ibci` 中 `import geo` 解析 `cases/d02/geo.ibci`）→
② **项目根**（项目级模块兜底）。逐级探测，首个命中即采用（同名下级遮蔽
上级的沙箱外候选）。**相对导入**（`.mod`/`..mod` 前缀）锚定导入方文件目录
逐级上溯，不经两级搜索。模块身份键 = 用户 import 名（`import geo` 的模块
键即 `geo`，与运行期模块注册/查询一致）；包路径形态（`import pkg.sub.mod`）
的模块键 = 完整包路径名。安全边界：解析结果须位于项目根沙箱内
（`DEP_SECURITY_ERROR`）；越界的 ① 级候选（如合成入口载体位于系统临时目录）
跳过回落 ② 级，不报错。

**`from mod import *` 冲突行为**：通配符导入时，若模块导出的符号与当前作用域已有的非模块符号同名，发出 `SEM_IMPORT_CONFLICT` WARNING 并跳过该符号（本地定义优先）。与已有模块符号同名时静默跳过。命名导入 `from mod import name` 冲突行为一致。

**模块导出规则**：模块的导出成员仅包含用户定义和显式导入的符号。语言内建（`int`/`str`/`print` 等）不出现在模块导出中——每个模块自动获得这些内建符号，无需跨模块重导出。

### 11.2 内置模块

**内核原生模块**（随内核发行，构造期注册，受 HostInterface 覆盖保护）：

```ibci
import ai      # LLM provider 配置（API key、model、retry 等）
import isys    # 运行时路径查询（entry_path / entry_dir / project_root）
import idbg    # 调试探查工具
import ihost   # 动态宿主（隔离子环境运行）
import fs    # 受限文件系统操作
import iruntime  # 运行时内省（snapshot / subscribe / configure）
import meta    # 代码作值（compile 编译门 + quote/eval 数据/命令二元）
import selfref # 自指性架构确定性原语（零 LLM）
import world_model  # 世界模型 KB 磁盘面（内容寻址 artifact 加载/保存）
```

**内置工具模块**（随内核发行，与内核原生模块同在 Engine 构造期一次注册，
见 `docs/architecture/07_kernel_native_modules.md`）：

```ibci
import json    # JSON 解析
import math    # 数学函数
import time    # 时间函数
import net     # 网络
```

> **注意**：`@~ ... ~` 行为描述语句是语言核心特性，**不依赖 `import ai`**。`ai` 模块仅负责配置 LLM provider。

### 11.3 ai 模块

配置加载为**显式动作**：引擎启动时不会自动加载配置。入口调用
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

> **`get_current_call_info()` 观测契约（两形态快照）**：最近一次 LLM 调用的
> 诊断信息分两阶段补全——**dispatch 时刻**（调用提交）写入请求面快照
> （`user_prompt`/`intents`/`output_contract` 等，`response` 为空）；
> **resolve 时刻**（结果就绪）补全 `response`/`raw_response`/`sys_prompt`/
> `finish_reason`/`generation`（采样姿态审计：已声明的生成参数有效值 +
> `max_tokens` 有效值）。行为表达式（`@~...~`）经 eager dispatch 提交——
> **变量读点（消费该变量）触发 resolve**。因此观测完整调用信息须在
> **读取/消费 LLM 结果变量之后**再调用 `get_current_call_info()`；
> 未消费的调用停留在 dispatch 快照形态（这是观测时序，非缺陷）。
> `finish_reason` = 供应商结束原因原值（`stop`/`length`/…）——**截断检测**：
> `length` = 达到生成预算被截断（截断 ≠ 解析失败）。

流式调用（增量渲染）：

```ibci
class Steamer:
    func __llm_call__(self) -> dict:
        return {"user_prompt": "MOCK:STREAM:Hello| World|!"}

Steamer s = Steamer()
str full = await ai.stream_call(s)   # stream_call(target: LLMCallable) -> Waitable，await 后返回完整文本
any h = ai.stream_call(s)            # 赋值自动等待（auto-yield）

chan c = ai.stream_channel(s)        # stream_channel(target: LLMCallable) -> chan，逐块消费
```

> `stream_call` / `stream_channel` 接受任何 **LLMCallable 实例**（行为值或实现
> `__llm_call__` 的用户 llm 可调用类，见 `docs/syntax/08_llm_callable.md`），经统一装配入口
> 装配请求后流式执行；不接受字符串形态（`stream_call(sys_prompt, user_prompt)`）的调用。

**Embedding 服务面**（语义内容缝：词嵌入一等能力；OpenAI 兼容 embeddings 服务接入 +
MOCK:VEC 离线面）：

```ibci
import ai

# 模型配置（三选一入口）
ai.set_embedding_config(url, key, model)            # 直接配置
ai.register_embedding_model(name, url, key, model)  # 注册命名模型（api_config.json
                                                    #   embedding 条目 kind="embedding" 按名路由）
ai.set_embedding_model(name)                        # 激活命名模型
ai.set_embedding_mock(enable, dim, seed)            # MOCK:VEC 确定性向量（零网络零 key）

# 嵌入（动态重载）
vector v = ai.embed("hello")               # str → vector（单文本）
list[vector] vs = ai.embed(["a", "b"])     # list[str] → list[vector]（批量）
# 可选具名参数：ai.embed("t", model="m", dimensions=512)

# 检索最小闭包（线性 top-k，按 cosine 降序）
list hits = ai.retrieve(q, vs, k)          # q: vector, vs: list[vector], k: int → list[vector]
# k 越界/非法 = fail-fast（EMB_INVALID_INPUT）
```

- `vector` 内置值类型（方法面/值语义见 `docs/syntax/01_types.md` §1.5）。
- 内省面：`ai.get_embedding_call_info()`（最近调用记录）/ `ai.probe_embedding()`（探活）。
- 诊断：配置缺失 `EMB_CONFIG_MISSING` / 非法输入 `EMB_INVALID_INPUT`（`EMB_` 域，
  见 `docs/syntax/15_diagnostics.md`）。

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
idbg.show_environment()  # 打印当前一等环境（frames 栈：键值行 + 键数/帧数
                         #   统计；最内层帧在前——帧级环境状态可视化，
                         #   与 environment.get_current() 同源）
idbg.runtime()           # 返回当前运行环境信息（调用栈深度 + 活跃意图；
                         #   原名 env 与"OS 环境变量"同名不同物，已改名消歧）
idbg.show_runtime()      # 打印当前运行环境信息
idbg.fields(obj)         # 返回对象所有字段
```

> **已知限制**：`idbg.inspect(x)` 和 `idbg.dump_intent_stack()` **未实现**，调用会产生运行时错误。
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
run_result rec = ihost.run_file("./sub/child.ibci", policy)  # 独立子进程运行子脚本，返回结果记录（run_result）
run_result rc = ihost.run_code("print('hi')", policy)        # 独立子进程运行代码字符串，返回结果记录（run_result）
ihost.save_state(path)                # 保存当前状态
ihost.load_state(path)                # 加载状态
str src = ihost.get_source()          # 获取当前入口源码
str val = ihost.getenv("SOME_KEY")    # 读取宿主 OS 环境变量（缺失返回空串）
```

> **OS 环境变量通道**：`ihost.getenv(key)` 是 IBCI 脚本读取宿主 OS 环境变量的
> 一等语言面通道（缺失返回空串，对齐 `os.getenv(key, "")` 语义——语言层 str
> 类型无需空值分支）。高级/任意宿主 API 仍可经宿主绑定
> （`import python "os" as oslib: bind getenv(...) -> str`）直接访问，`ihost.getenv`
> 是常用路径的便捷面。

子环境完全独立（独立 Engine 实例、构造期自行注册同一组内置模块、不继承父环境变量
与全局变量——数据交换经 `run_isolated`/`collect` 的导出变量字典或显式 file 读写）。

**LLM 配置继承**：子环境**自动继承父环境的 LLM provider 配置**（spawn 时点快照：
默认端点/模型、mock 态、`@NAME~` 命名模型注册表、生成参数）——子脚本无需自写
`api_config.json` 即可沿用父环境的 LLM 配置调用 LLM。快照语义：spawn 时点值
（spawn 后父配置变异不影响已 spawn 子）；子脚本显式 `ai.load_project_config()` /
`ai.set_config(...)` 在子代码执行期覆盖继承快照（时间序优先）。子环境 LLM 配置
继承失败（非标准 provider 等边界）不阻断子执行，经内核诊断
（`HOST_ISOLATE_LLM_INHERIT_FAILED`）显形，子 LLM 调用按其自身配置状态得清晰错误。

**`run_file` / `run_code` 结果记录（`run_result`）**：`ihost.run_file(path, policy)`
在独立子进程运行子脚本、`ihost.run_code(code, policy)` 在独立子进程运行一段 IBCI
代码字符串，
二者返回 `run_result` 值类型（**错误作值**——子失败不抛穿父；与 `run_isolated` 的
**错误作异常** + 变量字典互补，同一子 run 机制的两个消费面）。`run_code` 与
`run_file` **机制同构**（同一 spawn 核心：文件源 / 字符串源两形式；字符串源子
project_root = 父 project_root）——消除"手写临时文件 + `run_file`"的绕路：

```ibci
run_result rec = ihost.run_file("./sub/child.ibci", {})
run_result rc  = ihost.run_code("print('hi')", {})   # 字符串源，无需落盘
if rec.exit_status == "ok":
    print(rec.stdout)        # 子 print 输出（捕获，不经父 stdout 直接面）
else:
    dict ex = rec.exception  # 结构化异常记录（含编译失败/运行期异常/超时）
    print(ex["code"])        # 错误码（如 RUN_DIVISION_BY_ZERO / PAR_* / 沙箱拒绝）
    print(ex["message"])     # 错误消息
```

- `run_result` 三**字段**（attribute 访问，非 map 下标）：
  - `exit_status`：`"ok"` / `"error"`（子编译失败、运行期异常、collect 超时、沙箱
    越界均为 `"error"`）；
  - `stdout`：子 `print` 输出全文（捕获）；
  - `exception`：`None`（成功）或**结构化 dict** `{code, message,
    source{file, line, column, snippet}}`（与 CLI `--result-json` 的 exception 面
    同构，单一权威源）——子源码定位经 `source`（字符串源定位到合成入口 + 行列）。
- **防卡死**：`policy` 可含 `collect_timeout`（秒，墙钟上限）——默认无界
  （与 `run_isolated` 一致）；超时 = `exit_status = "error"` 且 `exception.message`
  携带 `timed out`（子线程无法强杀，作为 daemon 孤儿继续至自然结束，调用方不应
  假设子已停止）。

### 11.7 fs 模块

`fs` 模块提供受限文件系统操作；`file_handle` 是只读容器类型，`audio`/`image`/`video` 为其受限子类型（仅可经 `fs` 模块访问，受 kernel-native 覆盖保护）。

```ibci
import fs

# 创建只读 file_handle
file_handle fh = fs.open("data.txt")
str p = fh.path              # field，无 I/O
str content = fh.read()      # method，经沙箱校验后读取文本
list[int] bytes = fh.read_bytes()

# 直接按路径读取
str content2 = fs.read("data.txt")

# 统一写入：fs.write(target, data, overwrite_flag)
#   overwrite_flag="new"：target 为路径，创建/覆盖，返回 file_handle
#   overwrite_flag="overwrite"：target 为路径或 file_handle，就地覆盖
file_handle copy = fs.write("data_v2.txt", "new content")
fs.write(fh, "mutated content", overwrite_flag="overwrite")

# 存在检查与删除
bool exists = fs.exists("data.txt")
fs.remove("data.txt")
```

**只读语义**：`file_handle` 实例没有 `write()` 方法。所有写入必须通过 `fs` 模块的自由函数显式完成。

**写入模式的语义区分**（`overwrite_flag`）：
- `"new"`（默认）：`target` 为路径，创建新文件并返回 handle；若目标已存在则覆盖（等价于 Python `open(path, "w")`）。不依赖任何 source handle。
- `"overwrite"`：`target` 为路径或 `file_handle`，显式就地覆盖，所有共享同一 backing 路径的 handle 都会观察到变化。

**安全限制**：
1. 所有 FS I/O 均受沙箱约束（默认禁止越出 `project_root`）。
2. `save_state` 遇到活跃 `file_handle`/`audio`/`image`/`video` 变量时直接报错。
3. `llmexcept` retry body 中禁用 `fs.write`（避免污染 gold snapshot；磁盘型快照是浅路径引用，无法静态判别目标是否已入快照）。涉及可能失败的 LLM 调用时，先完成文件写入再进入可能重试的调用。

**写入目标基准与越界（`--root` 场景最小示例）**：

`fs.write` 的**相对路径**以 `project_root` 为基准解析（`project_root` 由 CLI `--root`
旗标 / 入口文件位置确立，`isys.project_root()` 可查询当前基准）。越出 `project_root`
的写入被沙箱拒绝，抛 `RUN_PERMISSION_ERROR`（非静默、非写成功）。

```ibci
import fs
import isys

str root = isys.project_root()      # 当前 project_root（写入基准）
print(root)

# 相对路径 = 落在 project_root 之下（基准内，合法）
file_handle h = fs.write("data/out.txt", "content")
str back = fs.read("data/out.txt")  # 读回验证
print(back)
fs.remove("data/out.txt")

# 越界路径（../../ 逃逸出 project_root）= 沙箱拒绝
try:
    file_handle bad = fs.write("../../escape.txt", "nope")
except Exception:
    print("越界写入被拒（RUN_PERMISSION_ERROR）")
```

- **基准内**（相对路径 / `project_root` 下的绝对路径）：正常读写。
- **越界**（`..` 逃逸、`project_root` 外的绝对路径）：`RUN_PERMISSION_ERROR`
  （"Security Error: Permission denied ... path outside workspace"）。需外部访问时
  显式 `isys.request_external_access()`（谨慎使用）。

### 11.8 json 模块

JSON 解析与序列化。

```ibci
import json

str raw = '{"name": "Alice", "age": 30}'
dict parsed = json.parse(raw)          # 对象 → dict
list items  = json.parse("[1, 2, 3]")  # 数组 → list（直接，无包装）
int n       = json.parse("42")         # 原始值 → 标量（直接，无包装）
str serialized = json.stringify(parsed)
str pretty = json.pretty(obj)        # 格式化输出
dict merged = json.merge(a, b)       # 合并两个 dict
list keys = json.keys(obj)           # 获取 dict 的键列表
list vals = json.values(obj)         # 获取 dict 的值列表
any val = json.get_nested(obj, path) # 按路径取嵌套值
json.set_nested(obj, path, value)    # 按路径设置嵌套值
```

- **`json.parse(s)`**：返回解析后的**实际值**（JSON 对象 → `dict`、数组 →
  `list`、原始值 → 标量；无包装键）。`s` 为非法 JSON 时**抛出可捕获异常**
  （`RUN_JSON_PARSE_ERROR`，经 `try/except` 处理）——fail-fast，不静默返回空值、
  无 print 副作用。
- **`json.parse_or_none(s)`**：显式宽松形态——非法 JSON 返回 `None`（无副作用：
  不抛、不 print）。调用方按数据形态在"抛错（parse）"与"None 判定
  （parse_or_none）"间显式选择失败面。

```ibci
# 失败面示例
try:
    dict d = json.parse(raw)
except Exception:
    print("malformed JSON")

any maybe = json.parse_or_none(raw)   # malformed = None
if maybe == None:
    print("absent/invalid")
```

### 11.9 用户扩展：宿主绑定

用户扩展 IBCI 的唯一通道是**宿主绑定**（见 §11.10）：在 `.ibci` 文件内用
`import python "..." as lib: bind ...` 显式声明要绑定的宿主成员。内核原生模块
（`ai`/`file`/`ihost`/`idbg`/`isys`/`iruntime`）受覆盖保护，绑定名不可与之重名。

### 11.10 宿主绑定（import python）

宿主绑定允许 IBCI 直接导入**裸 Python 模块/包**并显式声明绑定成员，绑定声明即
契约（详见 `docs/architecture/01_native_host_binding.md`）。

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
- 安全模型与内置模块一致：成员访问强制经 vtable/whitelist 门控，无隐式反射。

#### 11.10.1 宿主类型绑定（bind class）

`bind class` 把裸 Python **类**绑定为一等 IBCI 类型，可作类型注解、构造、
`impl` 目标与协议满足判定：

```ibci
import python "datetime" as dt:
    bind class datetime:
        bind year -> int
        bind replace(year: int) -> datetime

func test() -> auto:
    datetime d = dt.datetime(2026, 8, 17)
    datetime y = d.replace(year=2027)
    print((str)y.year)   # 2027
```

- `bind class Name:` 块内嵌套成员声明（方法/属性，规则与模块成员绑定一致）。
- `bind class Name -> any` 简写：仅建立类型身份，能力由 `impl` 补充。
- **impl 目标**：宿主类型可作为 `impl` 目标（`impl P for Name`），补充宿主没有的方法；
  协议满足在"bind 声明 + impl 补充"并集上静态判定。
- **编译期冲突 fail-fast（SEM_REDEFINITION）**：impl 方法不得与 bind 声明成员同名；
  同一 bind class 块内不得重复绑定同名成员。
- 实例 = 宿主原生实例（一等值）：bind 方法返回裸宿主实例时自动重包装，契约随返回
  对象延续（如 `datetime.replace` 返回新 datetime 仍是 IBCI `datetime`）。
- 契约外成员 / 缺失宿主类 / 缺失成员 → fail-fast。

### 11.11 meta 模块（代码作值：编译门 + quote/eval）

`meta` 暴露"代码作值"的两组原语：**编译门**（`compile`：代码字符串进程内
**静态校验**，**不执行**，与 `ihost.run_file`/`run_code`（隔离门）+ 调用方判定
（判定门）构成安全执行代码作值的三门管线，操作指南：`docs/howto/run_code_safely.md`）
与 **quote/eval 数据/命令二元**（`quote`/`eval`：表达式同时是数据——可查询/可
打印自身/精确对比——又是命令——执行取回其值，转换确定性）。

```ibci
import meta

meta.compile("str a = '1'\nprint(a)\n")   # 编译门：静态校验，不执行；成功静默（void）
# 编译失败 → fail-fast 抛错（可被 try/except 捕获，message 含 ibci 源定位）
try:
    meta.compile("int x = = 5")           # 语法错误
except Exception as e:
    print(e.message)   # [ERROR][PAR_UNEXPECTED_TOKEN] at <root>/__string_exec__.ibci:line 1, column 9: ...
```

- `meta.compile(code)`：代码字符串进程内 **compile-only** 静态校验（**不执行**），成功
  静默返回（void）；语法/语义错误 **fail-fast** 抛出，可被 IBCI `try/except` 捕获。
  子引擎独立（**零父状态污染**——父程序可能自身即字符串运行[合成 entry 同名冲突面]）。
- **ibci 源定位**：错误 message 含诊断码 + 合成 entry 标记 `__string_exec__.ibci` +
  line/column（字符串源可辨识，替代 tempfile 载体路径）——与 CLI `check` 面同构
  （compile-only + 失败即断）。
- **无 LLM 依赖**：compile-only 不调用 LLM（mock 态与非 mock 态行为一致）。
- **三门管线用法**：`meta.compile`（编译门）→ `ihost.run_code`（隔离门 + 结果捕获
  `run_result`）→ 调用方机械判定（判定门；操作指南见 `docs/howto/run_code_safely.md`）。

**`meta.quote(source)` / `meta.eval(expr)`（数据/命令二元）**：

```ibci
import meta

quoted q = meta.quote("2 * (3 + 4)")   # quote：验证门冻结为 quoted 值（数据形态）
print(q.source)                        # 数据形态：完整源串（可查询/可打印自身）
int v = meta.eval(q)                   # eval：执行并取回表达式的**值**（命令形态）
print(v)                               # 14
print(meta.eval(q) == v)               # 确定性：同源两次 eval 逐值一致
```

- `meta.quote(source) -> quoted`：表达式源串经**验证门**（子引擎 compile-only，
  同 `meta.compile` 路径）冻结为 `quoted` 值。验证门一次门尽：语法 / 语义 /
  **表达式性**（语句源 = 非表达式，fail-fast）/ **自包含性**（fresh scope——
  引用父模块自由名的源在 quote 时刻即 fail-fast，无隐式捕获面）。失败上抛
  （IBCI `try/except` 可捕获，message 含 ibci 源定位，同 `meta.compile` 面）。
- `meta.eval(expr) -> any`：执行 `quoted` 值（入参类型静态锁定 `quoted`——str
  直调 = 编译期类型违约），经子进程独立引擎（fresh scope + 进程级隔离 + LLM
  态继承，同 `ihost.run_code` 机制族）取回表达式的**值**（值交换通道，非
  stdout 文本）。错误面 fail-fast：子编译/运行失败、或结果不可经值通道取回
  （复杂值/函数值——边界见 `docs/KNOWN_LIMITS.md` §二十六）均上抛（`try/except`
  可捕获）。`None` 是合法结果值。
- **确定性**：转换路径零 LLM；纯代码表达式的 eval 子进程 LLM 调用 = 0；同源
  两次 eval 逐值一致（可复现）。
- **精确对比**：`quoted` 值按 `source` 逐字节相等（`q1.source == q2.source`）；
  无运算符面——判定门由调用方普通 IBCI 代码表达（同 `run_result` 纪律）。

**`quoted` 值类型**（`meta.quote` 返回值；不可变，单字段）：

- **字段**：`source: str`——被提及表达式的完整源串（`q.source` attribute 访问；
  `print(q)` / `(str)q` = 完整源串，无截断——数据形态即源串，截断即失真）。
- **核心不变量**：
  - **良构由构造成立**：`quoted` 仅经 `meta.quote` 验证门产出——str→quoted 无
    隐式转换（`(quoted)s` 编译期拒绝）；
  - **值语义**：按 `source` 逐字节相等；不可变（无修改面）；
  - **可移植**：可序列化 / 可跨引擎携带（数据形态是**值**，非 AST 引用）。
- **与 `behavior`/`fn_callable` 区分**：后两者捕获 AST 节点引用（绑定具体引擎
  上下文，非可移植值）；`quoted` 自包含（源串），非可调用（提及/使用的切换
  必经显式 `meta.eval`——二元性的结构保证）。

### 11.12 world_model 模块（工件磁盘面：内容寻址 artifact）

`world_model` 提供世界模型**工件磁盘面**：KB（`knowledge` 值的 KB 面——facts
事实日志 + vocab 治理词表，见 §16 知识注册表）与推理时窄模型（`narrow_model` 值 = 冻结
KG 嵌入工件，值类型面见本节"窄模型 artifact"）两类内容寻址 artifact 的加载
/保存。磁盘文件是**传输格式**，运行时模型 = 加载后水化的**活值**（非文件
本体）。

#### KB artifact（load_kb / save_kb）

`load_kb`/`save_kb` 辖 KB 面（facts/vocab/seq）：加载 = 三级验证门后水化为**活
KB 值**（可查询 + 可增量 `add_fact`，无需重编译）。

```ibci
import world_model

# 保存：KB 面序列化落盘，返回 content_hash（钉扎/审计基准）
kb = knowledge()
kb.register_world("modern", "现代物理世界", 3)
kb.register_relation("composed_of", "组成关系", False, False)
kb.register_word("atom", "原子", False, [], {})
kb.register_word("proton", "质子", False, [], {})
kb.add_fact("modern", "atom", "composed_of", "proton", "v30")
str h = world_model.save_kb(kb, "./kb.json")

# 加载：三级验证门后水化为活 KB 值（加载后增量可用）
kb2 = world_model.load_kb("./kb.json")
print(kb2.lookup_pair("atom", "composed_of")[0]["o"])   # proton
kb2.add_fact("modern", "atom", "composed_of", "electron", "v31")  # 增量
```

**artifact 格式**（共享契约；单 JSON 文件）：

```
{ schema_version: 1, content_hash: <sha256 64-hex>,
  facts: [ {id, world, s, r, o, source, status, events}, ... ],   // seq 序
  vocab: { words: {...}, relations: {...}, worlds: {...} },
  seq: <int> }
```

- **`content_hash`** = canonical 载荷（`facts`/`vocab`/`seq` 经键排序 + 紧凑
  分隔规范形态）的 sha256 全摘要——**内容即身份**：同内容不同文件排版
  （缩进/键序）= 同 hash；文件布局是传输，身份是 canonical。
- **加载三级验证门**（fail-fast 不静默降级）：
  1. **结构门**（合法 JSON + 封套键齐备 + 记录形态）→ `KNW_KB_ARTIFACT_MALFORMED`；
  2. **版本门**（`schema_version` 未知；无自动迁移）→ `KNW_KB_SCHEMA_VERSION`；
  3. **完整性门**（canonical 重算 hash ≠ 所载 `content_hash`——篡改/损坏）
     → `KNW_KB_HASH_MISMATCH`。
- **保存同构结构门**：`save_kb` 落盘前经同一结构验证（畸形 KB 面 fail-fast，
  不落盘半成品）。
- **沙箱纪律**（同 `fs`）：相对路径以 `project_root` 为基准解析 +
  `PermissionManager` 校验；越界/缺失文件复用 `fs` 面诊断（`RUN_PERMISSION_ERROR`
  / `RUN_GENERIC_ERROR`），不另造码。
- **entries 面不入 artifact**：artifact 只辖 KB 面（facts/vocab/seq）；通用
  登记面（entries）的持久化通道 = `ihost.save_state` 全状态面（两通道各辖
  其面）。加载的 KB 值 entries 面为空。

#### 窄模型 artifact（bind_artifact / save_artifact）

`bind_artifact`/`save_artifact` 辖**推理时窄模型**（`narrow_model` 值 = 冻结
KG 嵌入工件）：加载 = 三级验证门后水化为**活 narrow_model 值**（推理时
`score`/`topk`，**纯推理零训练**）。窄模型在宿主侧离线训练成工件，IBCI 仅
加载冻结权重做确定性推理（无 optimizer / 反向传播）。

```ibci
import world_model

# 加载：三级验证门后水化为活 narrow_model（纯推理零训练）
m = world_model.bind_artifact("./model.json")
print(m.score("atom", "composed_of", "proton"))   # TransE 距离（越小越优）
print(m.topk("atom", "composed_of", 3))           # [{o, score}, ...] 前 3 候选
str h = world_model.save_artifact(m, "./model2.json")  # 重导出，返回 content_hash
```

**artifact 格式**（共享契约；单 JSON 文件）：

```
{ schema_version: 1, content_hash: <sha256 64-hex>,
  model_name: <str>, architecture: "transe", dim: <int>,
  entities: [ <str>, ... ],                 // 候选实体空间（固定序）
  entity_embeddings:  { <name>: [float, ...], ... },  // dim 维向量
  relations: [ <str>, ... ],                // 关系空间（固定序）
  relation_embeddings: { <name>: [float, ...], ... } }
```

- **`content_hash`** = canonical 载荷（model_name/architecture/dim/
  entities/entity_embeddings/relations/relation_embeddings 经键排序 + 紧凑
  分隔规范形态）的 sha256 全摘要——**内容即身份**（同 KB 纪律）。
- **加载三级验证门**（fail-fast 不静默降级，同 KB）：
  1. **结构门**（合法 JSON + 封套键齐备 + 向量维度与 `dim` 一致 + 名-嵌入键
     匹配 + `architecture` 受支持[当前仅 `transe`]）→ `NAR_ARTIFACT_MALFORMED`；
  2. **版本门**（`schema_version` 未知；无自动迁移）→ `NAR_SCHEMA_VERSION`；
  3. **完整性门**（canonical 重算 hash ≠ 所载 `content_hash`——篡改/损坏）
     → `NAR_HASH_MISMATCH`。
- **保存同构结构门**：`save_artifact` 落盘前经同一结构验证（畸形工件面
  fail-fast，不落盘半成品）。
- **纯推理零训练**：`score(s,r,o)` = `‖e_s + r_r − e_o‖`（TransE 平移距离，
  越小越优）；`topk(s,r,k)` = 全部候选按距离升序取前 `k`（确定性 tie-break =
  (距离, 实体名) 升序）。权重加载即冻结——推理不触发任何训练/学习态。
- **沙箱纪律**（同 `fs`）：相对路径以 `project_root` 为基准解析 +
  `PermissionManager` 校验；越界/缺失文件复用 `fs` 面诊断，不另造码。

## 深入指引

- 内置模块系统与宿主绑定内部实现：docs/subsystems/04_plugin_system.md
- 隔离子环境的实际操作指南：docs/howto/use_isolation.md
- 循环导入限制：docs/KNOWN_LIMITS.md §十八
- 模块可见性隔离：docs/KNOWN_LIMITS.md §十九
