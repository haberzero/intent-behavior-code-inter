# meta 层 / 代码作值设计（安全执行架构 + 安全模型选项 A）

> 状态：**设计交付，本运行不实施**（用户 2026-09-08 裁定：架构安全与长期收益优先，
> 不半接通 meta 层；实施待类型类/函数式方向 VISION-4/5 落地后按该方向推进）。
> 本文 = round3 阶段 D 单点设计文档。相关既载：R-2b meta.compile / R-6 行为表达式作值
> （长期登记，`_trial_round3_intake.md` §1.6/§二.1）、ihost.run_file（R3-⑥ 已落地）、
> `engine.compile_string`（既有机制）、VISION-4/5/6（`PENDING_TASKS.md` §八）。

## 一、定位与范围

**meta 层 = "代码作值"（code-as-value）**：IBCI 源码 / 行为表达式作为一等值，可进程内
编译、执行、判定——把"运行一段 IBCI 代码"从外部脚本动作提升为语言内的可组合操作。

三个入口面（本文统一设计）：

| 入口面 | 机制 | 现状 |
|--------|------|------|
| **meta.compile**（R-2b） | 字符串代码进程内**编译作值**（`engine.compile_string` 的语言级暴露） | 机制已存在（`compile_string`），语言面未接通 |
| **ihost.run_file**（R-2a） | 进程内运行另一 .ibci 文件 + **结果捕获作值** `{exit_status, stdout, exception}` | **R3-⑥ 已落地**（ihost 子环境基建 + E1 LLM 配置继承） |
| **R-6 行为表达式作值** | `@~ ... ~` 行为表达式作为一等值 | 长期登记（VISION-4/5 类型类/函数式方向） |

**范围**：本文统一设计三入口面的**安全执行架构**与**安全模型（选项 A）**，给出类型层
承诺需求清单（VISION-4 开工输入）、F5 档案重估结论、自举台阶 ④ 端到端架构。
**非目标**：不实施（本运行）；不设计 VISION-4 类型理论本身（仅给出"meta 层所需的
类型层承诺"清单作为开工输入）；不设计真 JIT / 缓存预编译（F5 档 A/B，见 §五）。

## 二、安全执行架构（run_file + meta.compile + R-6 统一）

核心问题：**如何安全地在进程内执行"代码作值"**。安全 = 三段正交关切，统一为
**原语面（内核提供）+ 治理面（调用方表达）** 的分层：

### 2.1 原语面（内核提供的安全基元）

| 原语 | 语义 | 既载机制 |
|------|------|---------|
| **compile**（meta.compile） | 代码字符串 → 编译工件（**不执行**）；静态校验 fail-fast（语法/语义/类型/依赖） | `engine.compile_string(code) -> CompilationArtifact`（既有） |
| **execute-isolated**（ihost.run_file/spawn） | 在**隔离子引擎**运行 .ibci 代码；变量不跨隔离边界继承（父→子显式 file 传递）；LLM 配置继承（E1 spawn 时点快照）；沙箱门禁（--root） | `ihost.run_file(path, policy) -> {exit_status, stdout, exception}`（R3-⑥ 已落地） |
| **capture**（结果作值） | 执行结果捕获为**值** `{exit_status, stdout, exception{code,message,source}}`——错误作值（非异常上抛） | `run_file` 返回 dict（R3-⑥ 已落地） |
| **judge**（机械判定） | 对捕获结果做**机器可判定**的判定（对预注册期望） | 调用方表达（见 §三 选项 A——非内核机制） |

### 2.2 治理面（调用方用 IBCI 表达）

安全治理策略（哪些代码可执行、如何判定结果、施加什么约束）**不在内核硬编码**——由
调用方用 IBCI 代码表达（选项 A，§三）。内核只提供 §2.1 的安全基元；治理 = 调用方对
基元的组合。

### 2.3 R-6 行为表达式作值的归位

`@~ ... ~` 行为表达式作值（R-6）= 三入口面中**最贴近类型层**的一个（行为表达式的
值类型须由类型层承诺——VISION-4/5）。其安全执行复用 §2.1 的 compile/execute-isolated
原语；但其**值类型**（行为表达式作为什么类型的一等值）依赖类型层承诺（§四）。故 R-6
在本文仅定**归位**（复用统一原语面），不单独设计其值类型（待 VISION-4）。

## 三、安全模型：选项 A（调用方表达治理 + 语言原语）

> 用户 2026-09-08 裁定选项 A：**调用方表达治理 + 语言原语**；治理策略用 IBCI 表达，
> 三门管线固化为**文档化惯用法 + 参考实现**；ihost policy 参数为未来策略模型演进点，
> A 不堵死此路。

### 3.1 选项 A 的含义

- **内核 = 安全基元提供者**（§2.1）：compile / execute-isolated / capture 原语 + 隔离/沙箱/
  继承的安全保证（变量不跨边界继承、LLM 配置继承、--root 门禁、collect_timeout 防卡死）。
- **调用方 = 治理策略表达者**：用 IBCI 代码组合原语、表达"哪些代码可执行 + 如何判定"。
  治理策略是**数据**（IBCI 代码 / 预注册期望），不是内核配置。
- **为何选项 A（而非内核内建治理引擎）**：
  1. **使命定位**：IBCI 是语言自动机（确定性代码 + LLM 融合），不是治理框架——内核内建
     治理引擎 = 范围漂移（违背使命定位，同 C2"不开放通用数值面"裁定同纪律）。
  2. **单一权威源**：治理策略若入内核，则"哪些代码可执行"的事实散落内核 + 调用方两处
     （双写真相）；选项 A 下治理策略单点 = 调用方代码。
  3. **可组合性**：调用方按场景组合原语（测试/验收/批处理各不同治理），内核不预设单一
     治理形态（避免 tricky 的通用治理引擎）。

### 3.2 三门管线（文档化惯用法 + 参考实现）

安全执行代码作值的**推荐管线** = 三道门，固化为**文档化惯用法 + 参考实现**
（非内核强制机制——选项 A 下是惯用法，不是编译器强制）：

| 门 | 原语 | 职责 | fail-fast 面 |
|----|------|------|-------------|
| **门 1 编译门** | `meta.compile` | 代码字符串静态校验（不执行）——语法/语义/类型/依赖错误在编译期暴露 | 编译错误（`CompilerError` + 诊断码 + 源定位） |
| **门 2 隔离门** | `ihost.run_file(path, policy)` | 隔离子引擎执行——变量不跨边界继承、沙箱门禁、LLM 配置继承、collect_timeout 防卡死 | 运行期错误作值（`exception{code,message,source}`）+ 越界 `RUN_PERMISSION_ERROR` |
| **门 3 判定门** | 调用方 `judge`（对捕获结果） | 对 `{exit_status, stdout, exception}` 做机器可判定判定——对**预注册期望**（e34_p4 形态：预注册向量 + 机械判定） | 判定不符 = 调用方代码的失败路径（非内核错误） |

**三门管线的参考实现**（惯用法形态，调用方 IBCI 代码）：

```ibci
# 安全执行代码作值的三门管线（惯用法参考实现）
import ihost

# 门 1 编译门：静态校验（不执行）
#   [meta.compile 接通后] artifact = meta.compile(code_str)
#   编译失败 → CompilerError（fail-fast，不进入执行）

# 门 2 隔离门：隔离执行 + 结果捕获
dict result = ihost.run_file("./candidate.ibci", {"collect_timeout": 5.0})

# 门 3 判定门：对预注册期望机械判定
if result["exit_status"] != 0:
    print("候选代码运行失败: " + result["exception"]["message"])
else:
    # 对 stdout 做预注册期望判定（e34_p4 形态）
    str out = result["stdout"]
    if not expected_match(out, "预注册期望向量"):
        print("输出漂移：不匹配预注册期望")
    else:
        print("通过：输出匹配预注册期望")
```

> 三门管线的**安全保证由内核原语提供**（门 1 编译 fail-fast、门 2 隔离/沙箱/防卡死）；
> **治理逻辑（门 3 判定 + 门的组合顺序）由调用方表达**（选项 A）。参考实现是惯用法
> 模板，不是内核强制——调用方可按场景增减门（如只判定不隔离、或加资源约束门）。

### 3.3 ihost policy 参数 = 未来策略模型演进点（A 不堵死此路）

当前 `ihost.run_file(path, policy)` 的 `policy` = `IsolationPolicy`（收敛为单维
`collect_timeout`）。**选项 A 不堵死策略模型的演进**：

- **现状**：`policy` 是隔离维度（防卡死 `collect_timeout`）——最小策略面。
- **演进点**：未来策略模型可扩展 `policy`（资源上限 / 能力门禁 / 预算约束等），使
  "隔离门"的策略更丰富——**扩展 `policy` 维度不违背选项 A**（治理策略仍是调用方经
  `policy` 表达的数据，内核仍只提供基元 + 保证）。
- **边界**：策略扩展 = 内核原语的能力增强（新 policy 维度 + 对应保证），不是治理逻辑
  入内核（治理逻辑仍 = 调用方代码）。

## 四、类型层承诺需求清单（VISION-4 开工输入）

> 自举台阶 ④ 明确"**只差类型层承诺**"——机制面（`compile_string` / `run_file`）已存在，
> meta 层接通缺的是**类型层承诺**（代码工件 / 行为表达式 / 判定结果作为**有类型的一等值**）。
> 本清单 = VISION-4 开工输入（非 VISION-4 设计本身——类型理论设计不在本运行内）。

meta 层接通所需的类型层承诺（按依赖序）：

1. **编译工件作类型值**（meta.compile 的返回类型）：`compile(code: str) -> CompilationArtifact`
   ——`CompilationArtifact` 作为**有类型的一等值**（非裸 dict / 非 untyped），可传参/可存
   变量/可进 save_state。当前 `compile_string` 返回的 artifact 是内核内部对象，未暴露为
   语言级类型值。
2. **执行结果作类型值**（run_file 的返回类型精化）：`run_file(path, policy) -> RunResult`
   ——`RunResult` 作为**有类型的一等值**（字段 `exit_status: int` / `stdout: str` /
   `exception: Optional[ExceptionInfo]`），而非 `dict`（当前返回 dict——类型层接通后精化为
   具名类型 `RunResult`）。
   **MVP 注记（2026-09-08 §八 范围重划）**：run_result 类型**存在**半由 MVP 经既有
   值类型注册模式落地（字段面取 str/any 精化面，见 §8.3）；VISION-4 范畴收窄为
   ①③④⑤ + ② 的类型层深度参与（类型层内建/参与而非仅内核注册）。
3. **行为表达式值类型**（R-6 的归位）：`@~ ... ~` 行为表达式作为**有类型的一等值**
   （如 `BehaviorExpr` 类型，可传参/可作 LLM 可调用类的提案源）——依赖 VISION-4/5
   类型类/函数式方向（行为表达式的值类型语义）。
4. **fn[...] 高阶签名支持**（meta 函数的一等性）：`meta.compile` / `run_file` / `judge`
   作为**有签名的一等高阶函数**（`fn[...]` 形态），可引用/可组合（依赖 VISION-5 函数式
   地基）。
5. **判定结果类型**（门 3 的返回类型）：`judge(result, expectation) -> Verdict`
   ——`Verdict` 作为有类型的一等值（`pass/fail + 漂移度量`），供调用方消费。

**清单性质**：本清单是"meta 层所需"的**需求**（what），非"类型层如何提供"的**设计**
（how）——后者是 VISION-4/5 的范畴。本清单作为 VISION-4 开工输入，确保类型层设计覆盖
meta 层的类型需求。

## 五、F5 档案重估结论（VISION-6 档 B / 真 JIT / D-3.3）

> F5 = 原生宿主绑定评估（2026-08-18），全部列 VISION-6 远期（`PENDING_TASKS.md` §八
> VISION-6）。本里程碑（round3 收束）对 F5 档案项重估——结论：**维持远期，meta 层不
> 依赖 F5 档案项**。

| F5 档案项 | 重估结论 | 归位 |
|-----------|---------|------|
| **档 A 缓存预编译** | 维持远期（"引擎单次执行"模型下缓存失效/序列化保真/沙箱边界风险 > 收益）——**与 meta 层正交**（meta 层 = 进程内代码作值，不引入跨 run 缓存） | VISION-6 远期 |
| **档 B 隔离改造 / 反射能力** | **长期主线**（内核工程化）——隔离改造 = ihost 子环境隔离的强化面（meta 层门 2 的隔离保证可受益，但 meta 层不依赖档 B 落地）；反射能力 = 远期 | VISION-6 长期主线 |
| **真 JIT** | **挂数据平面性能线**（非 meta 层）——JIT = 执行性能面，与"代码作值"语义正交；meta 层不引入 JIT | 数据平面性能线（独立） |
| **D-3.3 VM 字符串扫描快速路径** | **本里程碑重估 = 维持长期登记**（VM 执行模型性能架构面，Tier C 专项候选）——与 meta 层正交（meta 层不动 VM 执行模型）；**与演化平面设计合流规划**（`LANGUAGE_DESIGN_EVOLUTION.md` 性能方向） | 演化平面（性能线） |

**重估要点**：meta 层（代码作值）**不依赖**任何 F5 档案项落地——meta 层复用既有原语
（`compile_string` / `ihost.run_file`），F5 档案项（缓存/JIT/隔离强化/反射/VM 快速路径）
是独立的内核工程化方向，与 meta 层正交。二者可并行推进，无依赖阻塞。

## 六、自举台阶 ④ 端到端架构

> 内核自举（bind 声明再表达内核契约）分台阶推进；**台阶 ④ = meta 层 / 代码作值**
> （自举的最高台阶——IBCI 用 IBCI 表达"运行 IBCI 代码"的治理）。台阶 ④ 明确"**只差
> 类型层承诺**"（§四清单）。

端到端架构（台阶 ④ 达成路径）：

```
台阶 ①-③（已达成/既有）：内核契约 bind 化 + 插件体系 + ihost 子环境基建
        │
        ▼
台阶 ④（meta 层 / 代码作值）：
  [机制面——已存在]                          [类型层承诺——待 VISION-4/5]
  engine.compile_string（编译）        →    ① CompilationArtifact 作类型值
  ihost.run_file（隔离执行+捕获）      →    ② RunResult 作类型值（dict→具名类型）
  隔离/沙箱/继承/防卡死保证（安全）     →    ③ BehaviorExpr 值类型（R-6）
                                            ④ fn[...] 高阶签名（meta 函数一等性）
                                            ⑤ Verdict 判定结果类型
        │
        ▼
  [治理面——选项 A，调用方表达]
  三门管线惯用法 + 参考实现（§三 3.2）
  预注册期望 + 机械判定（e34_p4 形态）
        │
        ▼
  自举闭环：IBCI 用 IBCI 代码表达"安全运行 IBCI 代码"的治理
  （治理策略 = IBCI 数据，安全基元 = 内核原语）
```

**台阶 ④ 的达成条件**：§四类型层承诺清单（①-⑤）经 VISION-4/5 落地 + 选项 A 治理面
（三门管线惯用法）文档化。机制面已就绪（`compile_string` / `run_file`），故台阶 ④
**只差类型层承诺**（§四）——这正是 VISION-4 的开工输入。

## 七、边界与非目标（防止半接通）

- **本运行不实施**：meta.compile / R-6 / 类型层承诺均**不实施**（用户原则：架构安全与
  长期收益优先，不半接通 meta 层；工作模式定论：禁止半修复/半接通）。
  **范围重划注记（2026-09-08）**：用户定向再评估后（§八），meta 层按 **MVP / 全形态**
  重划——MVP（`meta.compile` fail-fast 校验面 + `ihost.run_code` 字符串形式 +
  `run_result` 值类型）= 机制完整、无空洞承诺的独立特性，**不依赖类型层**，列为
  下一主线稳健推进；本条"不实施"裁定继续约束**全形态**（artifact 作值 / R-6 /
  类型层参与）——不半接通原则不变，范围重划非推翻原则（对账详 §8.3）。
- **不设计 VISION-4 类型理论本身**：§四仅给出"meta 层所需的类型层承诺"需求清单（what），
  类型理论设计（how）= VISION-4/5 范畴，不在本运行内。
- **不设计真 JIT / 缓存预编译**：F5 档 A/真 JIT 挂独立性能线（§五），meta 层不引入。
- **不内建治理引擎**：选项 A 下治理 = 调用方 IBCI 代码（§三），内核只提供安全基元。
- **ihost policy 演进不堵死**：策略模型扩展（§三 3.3）= 未来方向，选项 A 保留此演进点。

## 八、实施任务规划（字符串级直接执行 MVP）——2026-09-08 用户定向再评估

> 用户 2026-09-08 定向："语言级字符串直接执行是否可以开始稳健推进？内核工程化是否
> 紧随其后或须先行？"——本节 = 充分评估结论 + 任务规划（实施入口）。

### 8.1 稳健推进评估：前置依赖实证（零前置结论）

**结论：MVP（字符串级直接执行）可以立即稳健推进——前置依赖 = 0（全部机制已存在并
验证）；VISION-6 内核工程化不是前置、不需要先行（独立线）；VISION-4/5 类型层只是
**全形态**（artifact 作值/R-6/fn[...]/Verdict）的前置，不是 MVP 的前置。**

MVP 所需机制面实证清单（逐项有代码/测试证据，非推演）：

| 机制面 | 既有证据 | 状态 |
|--------|----------|------|
| 字符串编译 | `engine.compile_string`（合成 entry `__string_exec__`，锚定 project_root，engine.py:316-337） | ✅ |
| 字符串执行 | `engine.run_string`（与 `run` 同参数面：silent/output_callback/on_ready/journal/budget） | ✅ |
| 隔离子环境 | `engine.request_spawn_isolated`（新 Engine + 子线程 + LLM 快照 + on_ready 继承，engine.py:608） | ✅ |
| 字符串源扩展点 | 子线程体 `sub_engine.run(abs_path)` ↔ `sub_engine.run_string(code)` **同构**——单扩展点（同一 spawn 核心，两源形式） | ✅ 插入点明确 |
| E1 LLM 配置继承 | spawn 时点活状态快照（R3-⑥ 已落地，判别 15 项） | ✅ |
| 防卡死 | `IsolationPolicy.collect_timeout`（R3-⑥ 已接线） | ✅ |
| 诊断面 | `CompilerError.diagnostics{code, location{file,line,column}, message, hint}`（R3-⑦ 精化） | ✅ |
| 值类型注册模式 | `file_handle`/`knowledge`/`environment` 先例（axiom + vtable + TypeDef + 深克隆 + 序列化 + to_native 全链） | ✅ 模式在 |
| 模块注册模式 | `ihost` TypeDef（KERNEL_NATIVE + IMPORT_GATED，builtin_modules.py:224）先例 | ✅ 模式在 |
| 命名占用 | `meta`（模块名）/ `run_result`（类型名）无占用、非保留词（lexer KEYWORDS 核验） | ✅ |

**MVP 缺口 = 纯新增面**（一个值类型 + 一个模块 + 一个 ihost 成员 + 执行路径统一化）——
不触碰类型层（无 ADT/match/泛型/HM）、不触碰 VISION-6（无缓存/JIT/隔离改造/反射）。

### 8.2 与 VISION-6 内核工程化的关系裁定（用户问题二的答案）

**VISION-6 不是 MVP 前置；推荐顺序 = MVP 先行 → MVP 落地后联合重估 VISION-6 档 B →
VISION-4/5 类型层（全形态前置）。**

逐档案项关系（§五 重估结论的延伸）：

| VISION-6 档案项 | 与 MVP 关系 | 裁定 |
|----------------|-------------|------|
| 档 A 缓存预编译 | 跨运行性能面；MVP = 进程内单次（每 `run_code` 一次子引擎构造） | 无关（热循环用法出现时上修） |
| 内核自举（bind 表达内核契约） | 自举台阶另一方向；MVP 新增 `meta` 模块 = 既有 builtin_modules.py 注册模式，不要求内核契约 bind 化 | 无关（台阶 ④ = meta 层，本 MVP 即台阶 ④ 的执行/结果面推进） |
| 真 JIT / 反射 | 性能/元数据面 | 无关 |
| 档 B 隔离改造 | **唯一交点**：MVP 隔离保证 = 既有进程内子环境（变量不继承/LLM 继承/fs 沙箱/防卡死）——对 MVP 威胁模型（受信任候选代码，选项 A 调用方治理）**充分**；威胁模型演进到对抗性代码 → 档 B（进程级隔离）上修 | **MVP 落地后联合重估**（新增隔离消费方 + 威胁模型边界已入 KNOWN_LIMITS） |

**"内核工程化先走才能到字符串级直接执行？"= 否**——依赖方向反了：字符串级直接执行
（MVP）不依赖内核工程化；内核工程化的档 B 反而在 MVP 落地后获得新的重估输入
（隔离消费方面 + 威胁模型边界实证）。

### 8.3 MVP 与全形态的范围重划（对 §七"防半接通"裁定的对账）

§七 裁定（Phase D）："meta.compile / R-6 / 类型层承诺均不实施（不半接通）"——针对
**全形态**（artifact 作类型值 + R-6 行为表达式作值 + 类型层参与）。本 MVP = **范围重划**，
非推翻该原则：

- **MVP 边界 crisp 自洽，无空洞承诺**：编译门 = fail-fast 校验操作（成功 void / 失败
  抛 CompilerError——纯既有机制）；隔离门 = `ihost.run_code` 字符串形式（与 run_file
  同一执行路径 + 错误作值 + 类型化结果）；判定门 = 调用方普通 IBCI 代码。试用方真实
  用例（候选代码执行 + 机械判定，e34_p4 形态：预注册向量 + 判定）MVP 全满足。
- **不半接通原则遵守**：MVP 不交付任何"看似完整、语义空洞"的接口——每个交付面机制
  完整、有判别测试；全形态（artifact 作值 / R-6 / fn[...] / Verdict）继续登记、
  前置 = VISION-4/5（§四清单，其中承诺 ② RunResult 类型存在半被 MVP 满足——
  run_result 值类型经既有注册模式落地，VISION-4 清单收窄为 ①③④⑤ + ② 的类型层深度参与）。
- **user-principles 裁决四问**（范围重划合法性）：
  1. 普适性：code-as-value / 进程内字符串执行 = 主流语言惯用模式（Python
     compile/exec、Lua load+pcall、JS new Function、Lisp eval-apply）✅
  2. 架构合理性：机制同构（文件/字符串 = 同一 spawn 路径两源形式；结果作值与 run_file
     纪律一致；值类型注册走既有模式；无新执行模型）✅
  3. 实测优于现状：试用方 R-2b 需求实证 + 现工作绕路 = 手写临时文件 + run_file
     （胶水式绕行，MVP 消除）✅
  4. 非机械遵循历史：§七 的"不实施"针对全形态空洞接口；MVP/全形态重划尊重原则
     （不半接通）而重划范围（MVP 边界自洽非空洞）✅

**命名/语义面决策（MVP 内定型）**：

- `meta.compile(code: str)` → **void**（fail-fast 校验：失败抛 CompilerError[ibci 源
  定位：合成 entry 标记 + line/column]，成功静默）——编译门 = 校验操作（与 CLI
  `check` 面同构：compile-only + 失败即断；D2 已落地）。全形态扩展路径 = 返回值
  void → Compilation artifact 类型值（接口扩展非语义变更，既有调用点[忽略返回值]不受影响）。
- `ihost.run_code(code: str, policy: dict) -> run_result`——隔离门字符串形式（与
  `run_file` 机制同构：同一 spawn 核心、同一 E1 继承、同一沙箱/防卡死、同一错误作值
  纪律；`run_file` 返回值 dict → run_result 类型化精化[破坏性精化：消费方仅本轮判别
  测试 → 安全，user-principles 授权]）。
- `run_result`（新内核原生值类型）字段面：`exit_status: str`（ok/error，与既有 dict
  形态一致）/ `stdout: str`（子输出捕获）/ `exception: any`（None 或
  `{code, message, source{file, line, column, snippet}}` 结构化 dict——MVP 判定门只需
  code + location；异构异常内容 = any 诚实面，knowledge.value 先例；全形态可演进为
  ExceptionInfo 类型值）。命名与 `thread_result[T]`（线程 join 结果容器）区分——
  不同概念不同名。
  **字段面精化注记**：MVP 相对 §四 原设计（`exit_status: int` /
  `exception: Optional[ExceptionInfo]`）取 str/any 面——对既有 `run_file` dict 面
  （exit_status: "ok"/"error" 字符串 + exception 平坦错误串）的最小诚实精化；
  exception 捕获面同步从**平坦错误串**升级为**结构化 dict**（{code, message, source}——
  与 CLI `--result-json` 的 exception 面同构，统一设计语言；机制已存在：异常携带
  error_code + Location，CLI 面已做此提取）。M1 的 run_file dict → run_result 精化
  含此面升级（消费方仅本轮判别测试 → 安全）。
- **meta.compile 用子引擎**（新 Engine 实例 + compile_string，独立 scheduler）——
  零父状态污染（父程序可能自身即字符串运行[合成 entry 同名冲突面]）；机制同构
  （meta.compile 与 ihost.run_code 均用子引擎；compile-only 无需 LLM 继承/无需防卡
  死——编译不执行）。
- **威胁模型边界**（入 KNOWN_LIMITS）：MVP 隔离保证 = 进程内子环境（变量不继承 /
  LLM 配置继承 / fs 沙箱[project_root 基准] / 防卡死 collect_timeout）；**非对抗性
  代码安全边界**（无进程级隔离）——选项 A 下调用方表达治理（调用方决定运行什么）；
  试用方场景 = 受信任候选代码（自生成/结晶候选）。对抗性代码威胁模型 = VISION-6
  档 B 上修输入。
- **性能边界**（入 KNOWN_LIMITS）：每 `run_code`/`meta.compile` 一次子引擎构造
  （scheduler + registry + 合成 entry）——候选验证场景（非热循环）充分；热循环用法
  = VISION-6 档 A 缓存/真 JIT 上修输入。
- **诊断码面**：预期零新码——meta.compile 失败复用 PAR_*/SEM_* 码族（CompilerError
  既有面）；run_code 子运行失败 = 子运行既有码经 exception 值面传递；timeout = 既有
  collect_timeout 语义。若实施中发现确需新码，按纯增面纪律（catalog + 15_diagnostics
  + parity 门）。

### 8.4 批次计划（每批 = 设计确认 → 实现 → 全量 pytest 零回归 → 落账 → commit）

**M1：run_result 值类型 + 执行路径统一（ihost.run_file 精化 + ihost.run_code 落地）**
- 新内核原生值类型 `run_result`（axiom `core/kernel/axioms/primitives/run_result.py`
  + TypeDef[KERNEL_NATIVE] + 深克隆 + runtime_serializer[collect + 水化] + to_native
  ——全链照 file_handle/knowledge 模式）。
- 执行路径统一化：`request_spawn_isolated` 子线程体提取为单一 spawn 核心
  （文件形式 = `sub_engine.run(abs_path)`[R3-⑥ 验证行为不变] / 字符串形式 =
  `sub_engine.run_string(code)`[新]）——两源形式共享 E1 继承/沙箱/防卡死/输出捕获。
  字符串形式派生：sub project_root = 父 project_root（合成 entry 锚定，
  `__string_exec__` 既有锚定语义）；隔离反转校验对字符串形式平凡成立（锚定即父内）。
- host service：`run_file` 返回值 dict → run_result（判别测试同步精化）+ 新
  `run_code(code, policy)`（run_file 镜像：spawn + collect + 结果）。
- ihost TypeDef：`run_file` return_type → run_result + 新 `run_code` 成员。
- 判别：run_code 正常路径（输出捕获）/ 异常路径（错误作值：code + source 定位）/
  超时路径（collect_timeout）/ E1 继承（子环境 LLM 配置）/ 沙箱边界（字符串代码
  fs 操作限 project_root）/ run_result 序列化往返 / run_file 精化行为保持。
- 文档：11_modules §11.6 更新（run_file 返回类型精化 + run_code）+ KNOWN_LIMITS
  威胁模型/性能边界条目。

**M2：meta.compile 编译门面**
- 新内核原生模块 `meta`（_SPEC_META：KERNEL_NATIVE + IMPORT_GATED；
  `compile(code: str) -> void`）。
- 实现 = 子引擎 compile-only（新 Engine + compile_string；失败抛 CompilerError
  [diagnostics 带 ibci 源定位：合成 entry 标记 + line/column]，成功静默）。
- 模块注册：builtin_modules.py（import gating 同 ihost 模式）。
- 判别：正常编译静默通过 / 语法错误抛出（code + location 精确定位）/ 语义错误
  抛出 / 父状态零污染（meta.compile 后父程序后续行为不变[含父自身为字符串运行
  场景]）/ mock 模式行为。
- 文档：11_modules meta 节 + 15_diagnostics（若零新码则仅引用既有码族）。

**M3：三门管线惯用法固化（文档 + 参考实现）**
- 本文档更新：§四 VISION-4 清单收窄注记（承诺 ② 类型存在半被 MVP 满足）+
  §七 边界对账（MVP/全形态范围重划）。
- 新 howto `docs/howto/run_code_safely.md`（如何在 IBCI 内安全运行代码字符串：
  三门管线参考实现——meta.compile 校验 + ihost.run_code 执行 + 机械判定
  [预注册向量 + 判定惯用法，e34_p4 形态]）；README 单点真理表登记。
- NEXT_STEPS / PENDING_TASKS（R-2b 状态：MVP 落地 → 全形态登记 VISION-4 依赖）/
  HANDOFF 同步。

**M4（登记不启动本轮）：meta 层全形态**
- CompilationArtifact 作类型值（meta.compile 返回值 void → Compilation）/ R-6 行为
  表达式作值 / fn[...] 高阶签名（meta.compile 作值）/ Verdict 判定结果类型。
- 前置 = VISION-4/5 类型层（§四清单 ①③④⑤ + ② 类型层深度参与）。
- 触发：VISION-4 开工（用户指示或重估触发条件成立）——MVP 落地后自举台阶 ④ 的
  类型层缺口清单即 VISION-4 开工输入。

**批次依赖**：M1 → M2 → M3（M1 的 run_result + 统一执行路径是 M2/M3 的地基；M2 与
M1 可并行设计但 M1 先行落地）。M4 = 独立阶段（VISION-4 后）。
