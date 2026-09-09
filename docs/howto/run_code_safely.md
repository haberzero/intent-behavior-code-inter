# 如何在 IBCI 内安全运行代码字符串（meta 层 / 代码作值）

> 面向需要在 IBCI 进程内运行"一段代码字符串"并对其结果做机器判定的开发者
> （典型：候选代码验证、自生成/结晶代码验收、批处理候选集评估）。解决"如何在 IBCI 内
> 安全地执行代码作值、如何捕获其结果、如何对结果做机器可判定的判定"的具体问题。
> 前置知识：`docs/syntax/11_modules.md` §11.6（ihost 模块：run_file/run_code）、§11.11
> （meta 模块：compile 编译门）。

## 何时需要

当"要运行的 IBCI 代码"本身是**数据**（字符串）而非静态源文件时使用——代码由上游
生成（LLM 提案、模板拼装、候选结晶），需在进程内校验、执行、判定。典型场景：

- **候选代码验证**：验证一段生成的候选代码能否编译 + 运行 + 输出符合预期。
- **自举验收**：IBCI 程序用 IBCI 表达"安全运行 IBCI 代码"的治理（自举台阶 ④）。
- **批处理候选集**：对一批候选代码逐一走校验/执行/判定管线。

安全执行代码作值固化为**三门管线**（推荐惯用法，非内核强制——治理策略由调用方表达）：

| 门 | 原语 | 职责 | fail-fast 面 |
|----|------|------|-------------|
| **门 1 编译门** | `meta.compile` | 代码字符串静态校验（**不执行**）——语法/语义错误在编译期暴露 | 编译错误（`CompilerError`，ibci 源定位） |
| **门 2 隔离门** | `ihost.run_code` | 隔离子引擎执行 + 结果捕获（`run_result`，**错误作值**） | 运行期错误作值（`exception{code,message,source}`）+ 越界 `RUN_PERMISSION_ERROR` |
| **门 3 判定门** | 调用方机械判定 | 对 `run_result` 做机器可判定判定（对**预注册期望**） | 判定不符 = 调用方代码的失败路径（非内核错误） |

安全保证由**内核原语**提供（门 1 编译 fail-fast、门 2 隔离/沙箱/防卡死）；**治理逻辑
（门 3 判定 + 门的组合顺序）由调用方表达**（选项 A）。

## 门 1 编译门：meta.compile

`meta.compile(code)` 对代码字符串做**静态校验（不执行）**：

```ibci
import meta

meta.compile("str a = '1'\nprint(a)\n")   # 成功：静默（void），不执行代码
# 编译失败：fail-fast 抛错（可被 try/except 捕获，message 含 ibci 源定位）
try:
    meta.compile("int x = = 5")
except Exception as e:
    print(e.message)   # [ERROR][PAR_UNEXPECTED_TOKEN] at <root>/__string_exec__.ibci:line 1, column 9: ...
```

- 编译门在隔离门**之前**：编译不过的候选代码不进入执行（fail-fast，省资源）。
- 源定位 file_path = 合成 entry `__string_exec__.ibci` + line/column（字符串源可辨识）。
- `meta.compile` 零父状态污染（子引擎独立）；无 LLM 依赖（compile-only）。

## 门 2 隔离门：ihost.run_code

`ihost.run_code(code, policy)` 在隔离子引擎执行代码字符串，返回 `run_result`
（**错误作值**——子失败不抛穿父）：

```ibci
import ihost

run_result r = ihost.run_code("print('hi')\n", {})
print(r.exit_status)     # "ok" / "error"
print(r.stdout)          # 子 print 输出（捕获，不经父 stdout 直接面）
# r.exception：None（成功）或结构化 dict {code, message, source{file,line,column,snippet}}
```

- 与 `ihost.run_file`（文件源）**机制同构**——同一 spawn 核心，仅源形式不同
  （字符串源子 project_root = 父 project_root）。
- `policy` 可含 `collect_timeout`（秒，防卡死）；默认无界。
- 子代码 fs 操作限父 project_root（越出 = `RUN_PERMISSION_ERROR` 经 exception 值面）。

## 门 3 判定门：机械判定（预注册期望向量）

判定门由**调用方**用普通 IBCI 代码表达——对 `run_result` 做机器可判定判定，对
**预注册期望**（e34_p4 形态：期望作为数据 + 机械比对，非 LLM 判官）。预注册期望
= 候选代码 → 期望输出的映射（数据，先于运行确定）：

```ibci
str expected = "42"
if r.exit_status != "ok":
    dict ex = r.exception
    print("拒绝：运行失败 " + ex["message"])
else if r.stdout != expected:
    print("漂移：输出 " + r.stdout + " ≠ 期望 " + expected)
else:
    print("通过：输出匹配预注册期望")
```

## 完整参考实现：三门管线

对一批候选代码走完整管线（编译门 → 隔离门 → 判定门），预注册期望向量 + 机械判定：

```ibci
import meta
import ihost

# 预注册期望向量：候选 -> 期望 stdout（数据，机器可判定，非 LLM 判官）
dict expectations = {"cand_a": "42", "cand_bad": "never"}
# 候选代码（上游生成/结晶的候选）
dict candidates = {
    "cand_a": "int r = 6 * 7\nprint(r)\n",
    "cand_bad": "int x = = 5\n",
}

# —— 候选 A：三门全通过 ——
str key = "cand_a"
str code = candidates[key]

# 门 1 编译门：静态校验（不执行）——失败即拒绝（fail-fast，不进入执行）
bool compile_ok = True
try:
    meta.compile(code)
except Exception as e:
    compile_ok = False
    print("reject-compile: " + e.message)

if compile_ok:
    # 门 2 隔离门：隔离执行 + 结果捕获（run_result，错误作值）
    run_result r = ihost.run_code(code, {})
    # 门 3 判定门：对预注册期望机械判定（调用方表达治理）
    str expected = expectations[key]
    if r.exit_status != "ok":
        dict ex = r.exception
        print("reject-run: " + ex["message"])
    else if r.stdout != expected:
        print("drift: got " + r.stdout + " expected " + expected)
    else:
        print("pass: output matches pre-registered expectation")

# —— 候选 B（编译门拒绝）——
key = "cand_bad"
code = candidates[key]
compile_ok = True
try:
    meta.compile(code)
except Exception as e:
    compile_ok = False
    print("reject-compile-bad: " + e.message)
if compile_ok:
    print("unexpected: cand_bad compiled")
```

运行输出：

```
pass: output matches pre-registered expectation
reject-compile-bad: [ERROR][PAR_UNEXPECTED_TOKEN] at <root>/__string_exec__.ibci:line 1, column 9: ...
```

- 三门管线是**惯用法模板**，非内核强制——调用方可按场景增减门（如只判定不隔离、
  或加资源约束门）。

## 安全保证与边界

- **威胁模型 = 受信任候选代码**：子运行隔离为**进程内子环境**（变量不继承 / LLM 配置
  继承 / fs 沙箱 / 防卡死），**非对抗性代码安全边界**（无进程级隔离）。需运行
  **不可信/对抗性**代码时不得依赖本机制（进程级隔离见 `docs/KNOWN_LIMITS.md` §二十六）。
- **性能**：每次 `run_code` / `meta.compile` 构造一次子引擎——候选验证场景（非热循环）
  充分；热循环上修见 `docs/KNOWN_LIMITS.md` §二十六。

## 常见陷阱

- **布尔字面量大小写**：IBCI 布尔/空值字面量为 `True`/`False`/`None`（首字母大写），
  非 `true`/`false`/`none`。
- **`run_result` 是值类型，非 dict**：字段经 attribute 访问（`r.exit_status`），非下标
  （`r["exit_status"]`）；`r.exception` 为 `any`（None 或 dict），取字段需
  `dict ex = r.exception; ex["message"]`。
- **编译门须在隔离门之前**：编译不过的候选不进入执行（省资源 + fail-fast）。
- **判定门是调用方职责**：内核只提供 `run_result`（结果作值），"是否符合预期"的判定
  由调用方代码表达（预注册期望 + 机械比对）。

## 深入指引

- ihost 模块完整语法（run_file/run_code/run_result）：`docs/syntax/11_modules.md` §11.6
- meta 模块（compile 编译门）：`docs/syntax/11_modules.md` §11.11
- 隔离的工程示例：`examples/03_advanced_features/isolation_demo/`
- 威胁模型 / 性能边界：`docs/KNOWN_LIMITS.md` §二十六
