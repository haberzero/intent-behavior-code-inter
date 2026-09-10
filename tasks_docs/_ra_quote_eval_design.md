# _ra_quote_eval_design — P1 R-A quote/eval 机制设计（数据/行为二元地基）

> **性质**：临时任务控制文档（设计阶段），P1 批次的**设计单点真理**。落地后删除，
> 最终内容按治理收敛入 `docs/`（11_modules §11.11 / 07_kernel_native_modules / KNOWN_LIMITS）。
> 上游需求权威源 = `_world_model_db_design.md`（§6 P1 + §7 决策点 #2/#7）+
> 试用方 v2 需求单 R-A 节（`ibci-trial/docs/REQ_IBCI_WORLD_MODEL_INTEGRATION.md`，D-ISO 只读）。

---

## 0. 一句话设计论点

> **quote/eval = meta 模块的"代码作值"数据侧与执行侧原语（`meta.quote(source) -> quoted` /
> `meta.eval(expr) -> any`）：quoted 是不可变一等值类型（被提及的表达式 = 自包含的、经
> 编译门验证的源串），quote 经子引擎 compile-only 验证使其**自包含性由构造成立**（单一验证
> 门），eval 经子进程 spawn + JSON 值通道**取回表达式值**（非 stdout 文本）——转换全程零 LLM，
> 复用 meta.compile（编译门）与 ihost.run_code/run_isolated（隔离门 + 值交换）既有机制，
> 不发明新机制。**

**与试用方 e06 POC 的本质区别**：e06 的 quote/eval 经 LLM 行为表达式实现（可行性演示，
**非**确定性原语）；本设计是**语言级确定性原语**（R-A 验收的"转换零 LLM、可复现"）。

---

## 1. 需求溯源（R-A 验收面）

- `quote(E)` 返回 E 的**数据形态**（可查询 / 可打印其自身 / 可精确对比）
- `eval(E)` **执行** E（作为命令），返回其**值**
- 转换**零 LLM、可复现**
- 自指表达式（"统计这句话用了多少个汉字"类）可被正确求值
- M1 场景：`load_kb` 后确定性模式 quote/eval 一条事实（query 数据形态 + 验证成立性）

**关键解读**：数据形态必须是**值**（可存储/可序列化/可跨引擎携带），非字符串裸串——
"不能永远用 IBCI 代码/JSON 承载数据"的同一原则在表达式层的落点。

---

## 2. 现状盘点（实证，2026-09-10）

| 子件 | 形态 | 对 R-A 的结论 |
|------|------|--------------|
| `__to_prompt__`/`__from_prompt__` | LLM 提示词协议（渲染有损 + 解析 LLM 输出，`tuple[bool, any]` 面） | **不够**——LLM 通道，非确定性数据↔命令转换；R-A 走**新原语**（决策点 #2 裁定） |
| `fn_callable`/`behavior` | 捕获 AST node uid + execution_context 引用；`to_native()` 未执行即抛错 | **不可移植**——node uid 绑定具体引擎（正是"代码不是值"的陷阱）；quoted 不继承此形态 |
| `meta.compile(code: str)` | 子引擎 compile-only 静态校验 + 返回产物摘要 dict（TYPE-1 行为作值） | **quote 的验证门复用此机制**（同一子引擎 compile-only 路径） |
| `ihost.run_code/run_file` | 子进程 spawn + JSON 结果记录（stdout 捕获，错误作值） | **机制同族**；eval 需要**值交换**而非 stdout |
| `ihost.run_isolated/collect` | 同一 spawn 核心 + `--export-variables`：子全局作用域变量 → JSON 原生值 dict | **eval 的值通道复用此协议**（子脚本把表达式结果赋给结果槽变量，collect 取回原生值） |
| `selfref.render/verify` | 模板 + 参数 → 源串；三关门验证 | **消费方**（决策点 #7：quote/eval 是独立语言原语，selfref 消费它） |

**实证核验**（venv 实跑）：
- `__qeval__ = 1 + 2`（双下划线顶层变量 + 表达式赋值包装）**编译/执行合法**；
- 语句源（`x = 1`）经 `__qeval__ = <源>` 包装 → **CompilerError**（包装即表达式性验证）;
- `meta.compile`/`ihost.run_code` 的 spawn 核心对字符串源子进程导出全局变量（`_extract_engine_variables`：
  排除内置符号/不可序列化值，其余 `to_native` + JSON 验证）。

---

## 3. 设计决策（self-grill 全部分支已消解，无待用户项）

| # | 决策 | 裁定 | 依据 |
|---|------|------|------|
| D1 | **承载模块** | `meta` 模块（`meta.quote` / `meta.eval`） | "代码作值"单一权威源（design-philosophy §一）：meta 已拥有代码作值轴（compile = 验证侧，TYPE-1）；quote/eval = 同轴的数据侧/执行侧。新模块（qeval）= 碎片化；语言 intrinsic = 错误形态（quote/eval 有引擎级成本：编译/子进程，属插件面） |
| D2 | **提及形态** | 源串形态：`meta.quote(source: str) -> quoted` | ① 系统代码作值轴全部以**源串**为传输形态（meta.compile/ihost.run_code/selfref.render）——机制同构；② AST 捕获形态 = node uid 绑定具体引擎（不可移植/不可序列化——R-A 数据形态的核心要求）；③ 零编译器/AST 改动（不引入 quote 特殊形式、不求值为运行期表达式）——公理层改动面最小 |
| D3 | **quote 验证** | 子引擎 compile-only（fresh scope）包装 `__qeval__ = <source>` | **自包含性由构造成立**：fresh scope 编译使"引用父模块自由名"在 quote 时刻即 fail-fast（无隐式捕获面）；**单一验证门**（quote 门）——eval 子进程同 root 重编译必然通过，错误面 = 纯运行期 |
| D4 | **eval 执行** | 子进程 spawn（`__qeval__ = <source>`）+ collect 值通道 | 复用 run_isolated 值交换协议（进程级隔离 + fresh scope + JSON 原生值）——唯一既有**值交换**通道（stdout 通道 = 文本，不满足"取回值"）；机制同构，不发明新机制 |
| D5 | **作用域语义** | fresh scope（子进程独立引擎，不注入父状态） | 确定性 + 可移植 + 隔离（P7 纪律）；自由名 = quote 门已拒（D3）；未来需传数据 = 显式参数面（P2+，不预置半成品） |
| D6 | **错误语义** | eval **fail-fast 抛错**（子进程编译/运行错误经 collect 上抛 → InterpreterError，IBCI try/except 可捕） | 与 `ihost.run_code`（错误作值 run_result）**不同概念不同面**：run_code 的**结果记录**是主题（观察一次运行）；eval 的**值**是主题（取值）——错误不是值。非双通道（两面对应两种意图，判定面由调用方选择） |
| D7 | **结果边界** | JSON 原生值（str/int/float/bool/list/dict/None）；结果槽缺失 = 显式 fail-fast 错误 | 既有值交换协议边界（`_extract_engine_variables` 安全网同语义）；**None 是合法值**（结果槽存在即取值，含 None）；缺失（不可序列化复杂值）= 显式错误，非静默 None（fail-fast 纪律） |
| D8 | **值类型** | `quoted`（不可变一等值类型；字段 `source: str`；无运算符面；无 call 能力；`__to_prompt__` = 完整 source；`to_native` = source） | 类型面与 `run_result` 先例同构（record 固定字段面 + 无运算符 + 不可变）；**无 call 能力** = 数据/命令二元性的结构保证（提及与使用的切换**必须**经显式操作——R-A 的主题）；无运算符 = 精确对比经 `q.source`（str == str，调用方表达——run_result 同纪律） |
| D9 | **对比语义** | 源串**逐字节**相等（`q1.source == q2.source`） | R-A"精确对比"的严格诚实读法；语义等价判定（归一化/AST 规范化打印）= 新子系统且对任意表达式判定等价不可判定——**不做**；P2（KB 事实层）若需事实身份 = 事实层 UID（归属事实层，不污染 quote 层） |
| D10 | **LLM 表达式** | eval 允许源含 `@~...~` 行为表达式（子进程继承 LLM 态） | **转换**零 LLM（quote/eval 机制本身不调 LLM）；**表达式语义**是否调 LLM 归表达式自身（R-C 确定性模式在 P4 以运行期 journal 断言"LLM=0"——横切面，不在 quote/eval 层） |
| D11 | **eval 返回类型** | spec `return_type = any` | 结果类型本质开放（表达式可产任意类型）——`any` 是诚实面（builtin_modules 既有 `any` 返回先例：ai 配置面）；`auto` 不适用（非编译期可决） |

---

## 4. 机制详案

### 4.1 类型面（quoted）

```
公理 QuotedAxiom（core/kernel/axioms/primitives/quoted.py）
- name = "quoted"；parent = Object；不可变值类型
- 字段面：source: str（MemberSpec kind=field，attribute 访问 q.source）
- 方法面：cast_to / __to_prompt__（= 完整 source，无截断——数据面忠实呈现）
- 运算符面：无（精确对比 = 调用方对 q.source 做 str ==，run_result 同纪律）
- call 能力：无（提及/使用切换必经显式 eval——二元性结构保证）
- can_convert_from：仅 "quoted"（**不含 str**——str→quoted 必须经 meta.quote 验证门，
  无隐式转换面，保"良构由构造成立"）

规格 QUOTED_SPEC（core/kernel/spec/specs.py）
- kind=CLASS，provenance=KERNEL_NATIVE，visibility=PRELUDE_VISIBLE（同 run_result：
  类型名任意作用域可解析——变量声明 `quoted q = meta.quote(...)`）

运行时对象 IbQuoted（core/runtime/objects/primitives/quoted.py）
- payload = {source: str}；不可变（引用复用克隆——deep_clone 不可变集登记）
- to_native = source（str）——边界拆箱单一入口自然成立
- 序列化（runtime_serializer）：_collect_quoted {_type, source} + hydration 对称重建
  （同 run_result 直存纪律——全原生值，无拓扑引用）
```

### 4.2 HostService 面（core/runtime/host/service.py）

```
quote_expression(source: str) -> IbQuoted
- 非空 str fail-fast
- 子引擎（父 project_root，同 meta_compile 路径）compile-only 包装体
  `__qeval__ = {source}` —— 语法/语义/表达式性/自包含性一次门（fail-fast：
  InterpreterError 携带 ibci 源定位，合成 entry 标记）
- 成功 → 装箱 IbQuoted（registry.get_class("quoted")）

eval_quoted(source: str) -> native（JSON 原生值）
- 代码 = `__qeval__ = {source}\n`
- request_spawn_isolated(code=...) + request_collect（同 run_code 机制的
  值交换消费面：子进程独立引擎 = fresh scope + 进程级隔离 + LLM 态继承）
- collect 上抛 RuntimeError（子编译/运行失败，携带 error_code）→ 自然经
  create_proxy 翻译为 InterpreterError（IBCI try/except 可捕）
- variables 中 __qeval__ 键**存在** → 返回其值（含 None 合法）；**缺失** →
  显式 fail-fast（"eval 结果不可经值通道序列化（复杂值/函数值）或表达式无值"）
```

**结果槽命名**：`__qeval__`（双下划线内部槽，单一权威源 = 本 HostService 面；
实证核验 IBCI 合法顶层变量名）。

### 4.3 meta 插件面（ibci_modules/ibci_meta/core.py）

```
quote(source: str) -> quoted      # → HostService.quote_expression
eval(expr: str) -> any            # 边界拆箱后 = source 串；→ HostService.eval_quoted
```

- spec（_SPEC_META 扩展）：`quote`（param str → return quoted）/ `eval`
  （param **quoted** → return any）——静态类型面强制入参为 quoted 值
  （str 直调 = 编译期类型错，无隐式通道）。
- 调用边界：create_proxy 默认 unbox（quoted → to_native = source 串），
  返回经 reg.box 装箱（native → 对应 IBCI 值类型）。

### 4.4 确定性论证（R-A 验收"零 LLM、可复现"）

- quote：compile-only 零 LLM（meta_compile 既有保证）。
- eval：spawn/collect 机制零 LLM；**表达式自身**若为纯结构化代码 → 子进程
  LLM 调用 = 0（R-C 的 journal 凭证在 P4 横切断言）；若含 `@~` → 按 LLM 语义
  （继承态），转换路径仍零 LLM。
- 可复现：同 source + 同 root + 同 LLM 态 → 子进程执行同构；quoted 值不可变
  （源串逐字节 = 对比/序列化/哈希面全确定）。

### 4.5 与 selfref 弧线的配合（决策点 #7 落法）

quote/eval = **独立语言原语**（meta 模块），selfref **消费**它：
- `selfref.verify` 三关门中的编译门可改走 `meta.quote`（验证门单点化）——C3 批
  评估（本批不动 selfref）；
- SR-4 行为值直接执行（Phase D）的"行为值"若需可移植形态，quoted 是候选承载
  （本批不预设——SR-4 归 Phase D 裁定）。

---

## 5. 改动面清单（12 点，全部既有模式）

| # | 文件 | 改动 |
|---|------|------|
| 1 | `core/kernel/axioms/primitives/quoted.py` | **新增** QuotedAxiom |
| 2 | `core/kernel/axioms/primitives/registry.py` | 注册 QuotedAxiom |
| 3 | `core/kernel/spec/specs.py` | **新增** QUOTED_SPEC |
| 4 | `core/kernel/spec/registry/_runtime.py` | 规格注册 |
| 5 | `core/runtime/objects/primitives/quoted.py` | **新增** IbQuoted |
| 6 | `core/runtime/objects/primitives/__init__.py` | 导出 |
| 7 | `core/runtime/objects/deep_clone.py` | 不可变复用集 + "quoted" |
| 8 | `core/runtime/serialization/runtime_serializer.py` | _collect_quoted + hydration |
| 9 | `core/runtime/host/service.py` | quote_expression + eval_quoted |
| 10 | `core/runtime/interfaces.py` | IHostService 协议面 |
| 11 | `ibci_modules/ibci_meta/core.py` | quote + eval 插件方法 |
| 12 | `core/runtime/bootstrap/builtin_modules.py` | _SPEC_META 扩展（quote/eval 成员） |

**公理层变更**（新值类型入类型系统）→ **全量 pytest 放行门**（Phase 4 纪律）。
不新增 AST 字段/侧表（quoted 为运行时值类型，payload = str）；不新增语义错误集
（错误经既有诊断码 + collect 上抛路径）。

---

## 6. 验证与验收

### 6.1 测试计划

| 层 | 内容 |
|----|------|
| runtime 单测（`tests/runtime/test_meta_quote_eval.py`，进程内白箱） | ① quote 成功：类型 = quoted，q.source == 输入源串；② quote 失败面：语法错 / 语句源（非表达式）/ 非自包含源（引用未定义名）→ fail-fast 上抛（含诊断码可辨）；③ eval 值语义：算术/str/list/dict 表达式 → 取回**值**（非文本）；④ eval 错误面：子运行期错误 → fail-fast 上抛（try/except 可捕）；⑤ 确定性：同源两次 eval → 逐字节一致；⑥ 精确对比：同源两 quote → source == ；异源 → 不等；⑦ 边界：None 结果合法取值；复杂值（用户类实例）结果 → 显式 fail-fast；⑧ 类型面：`quoted q = ...` 声明 + q.source 字段访问 + print(q) 渲染 source；⑨ 嵌套：quoted 入 list/dict（deep_clone/序列化路径） |
| e2e（`tests/e2e/test_meta_quote_eval_e2e.py`，子进程全链路） | 自指验收演示（R-A 验收面）：quote 含句源串 → eval 取回句值（D↔I 同像性）+ 算术自指 + 三门管线的 quote 门（quote 失败 → try/except 捕获源定位） |
| 差分 harness 语料（`scripts/differential_harness.py`） | 追加 quote/eval 判别例（P9 语料 = 世界模型里程碑的首批：数据/命令二元 + 确定性可复现断言） |
| 全量 pytest（放行门） | 公理层变更 → 全量零回归（本批 commit 前） |

### 6.2 验收对照（试用方 R-A 面）

- "quote(E) 返回 E 的数据形态（可查询/可打印自身/可精确对比）" → `q.source`（查询/
  打印）+ 源串逐字节 ==（精确对比）✅
- "eval(E) 执行 E，转换零 LLM、可复现" → eval 值通道 + 确定性论证（§4.4）✅
- "统计这句话用了多少个汉字类自指表达式可被正确求值" → e2e 自指演示
  （句作数据 + 句作表达式值）；"汉字计数"的具体字符串算法 = 调用方普通 IBCI
  代码（语言面已有 str 原语），非 quote/eval 职责 ✅

---

## 7. 边界与非目标（本批不做，P2+ 裁定）

- **归一化/语义等价对比**（D9）：不做——事实身份归 P2 事实层 UID。
- **eval 显式环境参数**（向 eval 传数据入参）：不预置——D5 fresh scope；
  P2 若 KB 场景需要再立（届时裁定形态：env-dict 参数 vs 源内联）。
- **selfref.verify 改用 meta.quote**：C3 批评估（本批零 selfref 改动）。
- **SR-4 行为值直接执行**：Phase D（quoted 为候选承载，不预设）。
- **R-C 确定性模式**（P4）：横切面——本批保证转换零 LLM，运行期"LLM=0"凭证归 P4。

## 8. 硬约束对照

- 工作模式定论：新设计 = 真设计（quoted 为一等值类型，非字符串裸串/胶水）；
  协议驱动（类型面/字段面走公理+vtable，无能力标志分派）；fail-fast（quote 门/
  结果槽缺失/非 str 入参全显式上抛，无静默回退）；无 compat shim（不改
  meta.compile/run_code 既有面，只增）。
- design-philosophy：单一权威（代码作值 = meta 一处）；机制同构（类型面同构
  run_result；验证门复用 meta_compile 路径；值通道复用 run_isolated 协议）；
  命名统一（quote/eval/quoted/source——一个概念一个名字）。
- 9 VM 不变量：eval 子运行经统一 spawn 核心（进程级隔离既有面）；quote 零 LLM。
- 公理层变更纪律：全量 pytest 放行门 + WORKLOG 详尽记录变化前后。
