# 审计结论：内核接口层重审（2026-09-11 用户转向裁定，使命 1 产出）

> 本文件 = 使命 1（接口层/架构审计）结论文档。2026-09-11 用户裁定停止 ⑦ 增量移植，
> 转入 (1) Rust↔Python 接口层/架构审计 (2) 测试体系重设计 (3) 授权从 8129af0a 起
> 推翻重来的引擎级重构。本文档回答用户两问 + 复核嫌疑清单 3.1-3.7 + 三分类判定 +
> 总体判定（增量清理可解 vs 须推翻重来）+ 重设计方向。设计阶段文档，落地后收敛。

---

## 一、审计范围与方法

- **范围**：`git log 8129af0a..HEAD` 全部提交（08758567[⑦-1a/1b] / fe1dfcf7[⑦-1c] /
  b66a210a[WIP 会话 API 标本 + 交接文档] / 016f3716[转向裁定文档同步]），即 ⑦ 切换门
  批次阶段① 全部代码增量。
- **方法**：逐提交 diff + 逐落点读源（code-review 纪律：前序智能体报告 ≠ 结论，全部
  以源代码第一手证据复核）；对照 ⑦ 设计 v1（`tasks_docs/_p9_switch.md`）"设计意图 vs
  实现漂移"；对照 design-philosophy（单一权威源 / 机制同构 / 配合模式统一 / 一致性先于
  便利）+ code-quality（三条红线：兜底/历史包袱/双通道）+ 工作模式定论。
- **基线（实跑）**：4306 passed / 2 failed / 1 skipped / 140.94s（b66a210a 后，本审计
  开工时复跑确认；2 failed = 宿主 .call 面 WIP 未接线预期失败——审计对象，非待修项）。

---

## 二、用户两问的直接回答

### 问 1：到底有没有为了对接已有的测试项而在 rust 和 python 的接口层定义的不干净代码？

**有，已证实。** 证据（全部第一手读源）：

1. **WIP 会话 API（b66a210a，ibci-ext/src/lib.rs open_session/session_call/
   session_release + 全局 SESSIONS 注册表[raw pointer + unsafe impl Send] +
   core/runtime/kernels/__init__.py RustFunctionProxy + core/engine.py 第三分支）**：
   唯一动机 = 2 个既有测试（test_call_drive_convergence 宿主 .call 薄包装语义）。
   为对接测试新开一条**持久会话执行通道**，与既有 run_artifact_state（一次性执行）
   并存 = 同一"执行 artifact"语义的两个入口、生命周期/状态模型不同（双通道嫌疑
   实证）。且该 API 自身不完整（函数符号 declared_type 解析 None → proxy 分支未
   生效 → 2 测试仍失败）= 零功能增量 + 纯新增适配面。
2. **路由谓词堆（kernels/__init__.py artifact_is_rust_executable = 8 谓词串联短路 +
   4 硬编码集合）**：每条谓词 = ⑦-1c 推进中一个失败测试发现的一个语义角的静态近似
   （tuple 物化 / 内建名重定义 / meta.compile / Optional 实例同一性 / KB-vec 对象身份 /
   未移植内征 / 宿主模块导入 / 节点类型子集）。形式是函数式谓词，内核本质 = 自下而上
   的补丁决策链（碎片化 if-else 本质，形式非 if-else——与用户判断一致）。
3. **engine._execute_rust 镜像（core/engine.py）**：declared 家族白名单
   {int,float,str,bool,any,list,dict,Optional} 硬编码 + materialize_variable 旁路
   （runtime_context 新公共 API，直接 poke scope._symbols/_uid_to_symbol 内部）+
   _bind_container_specialization 复刻 VM leaf 逻辑 + quoted 特判 + 函数→proxy 分支
   ——全部为"让 Rust 执行结果能在 Python 状态容器里被既有测试读回"而写。
4. **_RUST_ERROR_CODES 映射表（core/engine.py）**：Python 侧异常类型→诊断码映射的
   第二真相（functions.py 已有同族逻辑）；错误跨边界 = 非类型化字符串协议
   （"IBCI: uncaught exception: {class}: {msg}@{line}:{col}"）+ engine 正则解析 +
   RecursionError 字符串 contains 特判。

### 问 2：现有的 rust 和 python 的分层、职责分配是不是真的合理？

**不合理，已证实。** 三个层面的职责错位：

1. **engine = 组装者，却在执行面做语义判断**：engine.py 模块头自述 "Engine = 组装者，
   不参与执行"；但 _execute_rust 内：对 Rust 执行结果**重跑 Python 类型检查**
   （define_variable → ScopeImpl.define → _check_type——ibci-ext 执行面不检查、
   镜像检查 = 类型检查语义双执行面，若 Rust 未来移植检查 = 双真相）；复刻容器特化
   绑定逻辑（VM leaf._bind_container_specialization 的第二实现）；quoted 物化特判。
   状态容器写入路径被用来承载执行面语义判断（职责混淆）。
2. **runtime_context（核心状态模块）被开旁路**：materialize_variable = 绕过正常
   define 路径的符号表第二写入通道，直接写 scope._symbols/_uid_to_symbol 内部
   （封装纪律侵蚀——为镜像专用开的旁路 API，污染核心模块）。
3. **kernels 加载层膨胀为路由裁判**：core/runtime/kernels/__init__.py 从"加载 .so"
   膨胀为 327 行路由判定面（8 谓词 + 4 集合 + 2 扫描助手 + 1 代理类）——单一入口
   是好的，但判定内容 = 自下而上补丁堆，非从内核能力面自上而下声明的能力表。

---

## 三、嫌疑清单 3.1-3.7 复核结果（逐项证实/证伪 + 证据）

| # | 嫌疑 | 复核 | 证据（第一手读源） | 分类 |
|---|------|------|--------------------|------|
| 3.1 | 碎片化路由谓词堆 | **证实** | kernels/__init__.py artifact_is_rust_executable：8 谓词串联（节点类型⊆支持集 / 无宿主模块导入 / 无单符号元组赋值[子树 BFS] / 无内建名重定义[_INTRINSIC_TYPE_NAMES 硬编码集] / 无 Optional 实例同一性[node_to_type 扫描] / 无 meta.compile / 内征⊆rust_intrinsic_names / 无对象身份内征[_OBJECT_IDENTITY_INTRINSICS]）+ 4 硬编码集合（RUST_NATIVE_MODULES / _DATA_PLANE_EXCLUSIONS / _OBJECT_IDENTITY_INTRINSICS / _INTRINSIC_TYPE_NAMES）。设计 v1（_p9_switch.md §一）只写"节点类型集合判定"单检查，实现漂移为 8 谓词。 | (c) 碎片化 |
| 3.2 | 镜像双路径 + 三补丁 | **证实** | engine.py _execute_rust：declared 家族白名单硬编码 + define_variable[触发 _check_type——runtime_context.py ScopeImpl.define:193 实证] vs materialize_variable[旁路：scope.py 无此方法，runtime_context.py:813 新加，直接写 _symbols/_uid_to_symbol] + _bind_container_specialization[engine.py 复刻 leaf 逻辑] + quoted 特判 + WIP 函数→proxy 第三分支。 | (b)+(c) |
| 3.3 | 错误跨边界字符串协议 | **证实** | lib.rs/interpreter.rs:2395-2405 "IBCI: uncaught exception: {repr}@{line}:{col}"（repr = `<class>: <message>` 字符串）；engine.py 两段正则（`uncaught exception: (\w+)` + `@(\d+):(\d+)$`）+ _RUST_ERROR_CODES 映射 + RecursionError contains 特判。Rust 侧 Thrown 已结构化（value: IbValue::Error{class,message} + pos: Option<(i64,i64)>）——结构化信息在边界降级为字符串再被正则解析回来。 | (c) |
| 3.4 | 内征集合双真相 | **证实** | lib.rs:733 rust_intrinsic_names 硬编码 15 名（print/len/range/knowledge/vec + 8 异常构造类 + quote/eval）；interpreter.rs:1518 call_function match 臂（print/len/异常类[is_exception_class]/range/knowledge/vec）+ call_meta_fn（quote/eval）——两处手工同步，移植新内征忘同步 = 路由静默分叉无报警。 | (b) |
| 3.5 | 双真相语言语义面（结构性） | **证实** | Python VM handlers + Rust interpreter 双实现运行时语义；engine 镜像 + 路由谓词 = 粘合适配层，且随移植进度**单调增长**（⑦-1a/1b：kernels 加载层 → 1c：路由谓词 +1、镜像/错误/位置 +5 机制 → WIP：会话通道 +1）。适配层无体系化收敛机制——⑦ 完成后 Python VM 退役时适配层每层要再拆一次。 | (c) 结构性 |
| 3.6 | WIP 会话 API | **证实** | lib.rs:599-731 open_session/session_call/session_release + SESSIONS LazyLock<Mutex<HashMap<u64,(RawSessionPtr,u64)>>> + NEXT_HANDLE AtomicU64 + unsafe impl Send + Python __del__ 引用计数；与 run_artifact_state（lib.rs:756，一次性）并存双通道；唯一动机 = 2 测试。 | (b) |
| 3.7 | 测试体系时代错位 | **证实** | e2e test_ihost_run_code.py:81 / test_ihost_run_file.py:112 超时校准 100000→15000000 迭代（注释明写"⑦ 切换后子源 = Rust 面，按 Rust 速度重校准"——测试隐含 VM 速度假设破裂）；diff_harness 新增 test_rust_state_surface/test_rust_routing_decision（白盒断言 rc.get_variable payload 类型 + 状态回读——断言面仍耦合实现形态）；conftest expect_runtime_error 消息子串匹配（既有，时代错位）。 | 使命 2 对象 |
| ? | diff_harness 语料/探针资产（34 语料 + 探针） | **证实为 (a)** | tests/diff_harness/corpus.py + harness.py + divergence.py——内核无关行为资产（源 → 数据面/五池 artifact 面），新测试体系种子，须升格保留。 | (a) 契约驱动 |

**新增嫌疑（审计发现，前序清单未列）**：
- **N1：状态镜像的"非数据值显示形态串"契约（engine.py 镜像 + lib.rs ibvalue_to_json
  repr 契约）**：函数值/vector/quoted 等经状态导出 = 显示形态字符串（repr），engine
  镜像再按 declared_type 特判物化回对象（quoted→IbQuoted / 函数→RustFunctionProxy /
  容器→特化绑定）。这是**值模型跨边界降级 + 再水化**的双重特判——比单纯双路径更
  深：状态导出本身携带类型信息丢失（字符串无法区分"真字符串"与"函数显示串"），
  镜像靠 declared_type 内省补回。正确形态 = 状态契约按值携带类型标签（typed value
  通道），非 repr 字符串。
- **N2：diff_harness harness.py artifact_is_rust_executable 委托生产面**：测试 harness
  直接 import 生产路由判定（tests/diff_harness/harness.py:208-218 委托
  core.runtime.kernels.artifact_is_rust_executable）——测试资产与生产路由耦合
  （生产面改动即测试面漂移；且 .so 缺失 = 静默 False = 测试语义随环境漂移，
  fail-fast 纪律违反——不过此处为 harness 验证面语义，属可容忍的明确降级）。

---

## 四、三分类判定汇总

| 接口元素 | 位置 | 分类 | 判定依据 |
|----------|------|------|----------|
| node_types() 反序列化器节点类型集 | deserializer.rs:594 | (a) 契约驱动 | 内核能力面声明，单一真相（Rust 侧）——保留 |
| rust_intrinsic_names() | lib.rs:733 | (b) 测试驱动适配 | 手工同步的清单（call_function 臂第二真相）——须消除 |
| run_artifact / run_artifact_state | lib.rs:481/756 | (a) 契约驱动 | 内核执行入口 + 状态面（契约设计合理）——保留 |
| open_session / session_call / session_release + SESSIONS | lib.rs:599-731 | (b) 测试驱动适配 | 为 2 测试开的持久会话第二执行通道——删除/重设计 |
| RustFunctionProxy | kernels/__init__.py:54 | (b) 测试驱动适配 | WIP 会话 API 的 Python 侧代理——随会话面重设计 |
| artifact_is_rust_executable 8 谓词 + 4 集合 | kernels/__init__.py:292 | (c) 碎片化 | 自下而上补丁决策链——收敛为能力声明表 |
| _execute_rust 镜像（白名单 + define/materialize 双路径 + 特化复刻 + quoted 特判 + proxy） | engine.py | (b)+(c) | 状态面做执行面判断 + 双实现——重设计单一物化机制 |
| materialize_variable 旁路 | runtime_context.py:813 | (b) 测试驱动适配 | 符号表第二写入通道 + 封装侵蚀——删除（随物化机制重设计） |
| 错误字符串协议 + 正则 + _RUST_ERROR_CODES | engine.py + lib.rs | (c) 碎片化 | 非类型化跨边界契约 + 诊断码第二真相——类型化 |
| 非数据值显示形态串状态导出 | lib.rs ibvalue_to_json | (c) 碎片化（新增 N1） | 类型信息丢失 + 镜像再水化特判——typed value 通道 |
| 34 语料 + 探针 + divergence 注册表 | tests/diff_harness/ | (a) 契约驱动 | 内核无关行为资产——升格为新测试体系种子 |

---

## 五、总体判定：**须推翻重来（触发使命 3）**

**判定基准（交接任务书 §四 使命 1 固化）**：若"路由谓词堆 + 镜像双路径 + 字符串协议 +
双真相语义面"在增量清理下**无法收敛为** [单一内核能力声明表 + 单一状态物化机制 +
类型化跨边界契约]，则触发使命 3（推翻重来）。

**判定：无法收敛。** 三个收敛目标的达成都需要**接口契约层面的重新设计**，而非现有
层边界内的重构：

1. **单一状态物化机制**：镜像存在的根本动因 = Rust 执行值与 Python 状态容器是两个
   值模型（Rust IbValue vs Python boxed 对象 + IbClass 特化身份 + Optional 包装 +
   quoted 物化 + 函数代理 + 非数据值显示串）。在现有 engine.py + runtime_context.py
   层边界内"重构镜像"只能把特判整理得更有序，**无法消除其第二真相本质**——"执行后
   状态归谁、以什么形态暴露给 get_variable/runtime_context 契约"是接口契约决策。
2. **单一能力声明表**：路由谓词堆编码的语义角（tuple 物化 / Optional 实例同一性 /
   meta.compile / KB-vec payload 物化 / 内建名重定义保护）= **未移植到 Rust 的语义
   缺口**。增量整理路由 = 整理补丁摆放位置，不消除补丁本身；收敛为声明表需要这些角
   要么移植（消除路由需求）要么显式声明为 Python 宿主语言特性（接口契约决策）。
3. **类型化跨边界契约**：单独可增量（Thrown 已结构化），但它是边界设计的症状之一——
   与状态导出（N1）同属"跨边界协议"整体重设计面。

**触发使命 3（用户已授权，verbatim："从 8129af0a 开始整个把接口层、架构设计、甚至
整个 ibci 的内核体系全部推翻重来，都可以被允许，做一次代价巨大的引擎级重构"）。**

**推翻范围（精确边界）**：
- **推翻/重设计**：8129af0a 之后的接口适配层——engine 路由 + 镜像 + 状态契约、
  kernels 加载层路由判定面、错误跨边界协议、WIP 会话 API、materialize_variable 旁路、
  非数据值 repr 导出通道；以及测试体系（使命 2，另行设计文档）。
- **复用（8129af0a 之前可信地基，交接任务书明示优先复用）**：Rust 构建链（crate/
  build_rust_ext.sh/CARGO pin）、Rust lexer/parser/deserializer/serializer 本体、
  Rust 解释器执行核心（interpreter.rs 数据面语义）、Python 前端（compiler/semantic/
  serialization）、artifact 契约（FlatSerializer JSON 五池 + 侧表）、diff_harness
  语料/探针/divergence 注册表资产、3e-3f 全管线证明。
- **红线不变**：语言语义（公理 + contracts 语义错误集）；双内核协议（显式态无静默
  回退）；禁 push；main 永不触碰；大范围破坏性重构走独立隔离分支。

---

## 六、重设计方向（使命 3 实施蓝图，自上而下）

### D1：内核能力声明表（替代路由谓词堆）

- Rust 内核导出**能力清单**（结构化数据，非函数）：`capability()` = {
  node_types（已存在）, intrinsic_names（消除 rust_intrinsic_names 手工清单——从
  call_function 分发表**生成**或改为单一声明表驱动分发表）, native_modules,
  unported_corners: [{feature, reason, status}]（tuple 物化 / Optional 实例同一性 /
  meta.compile / KB-vec payload 物化 / 内建名重定义保护——随移植进度条目翻转，消除
  后即从清单移除）}。
- Python 侧路由 = **能力清单查询**（节点类型 ⊆ 声明集 + 内征 ⊆ 声明集 + 角 ⊆
  unported 集），**零谓词堆、零硬编码集合**（RUST_NATIVE_MODULES / _DATA_PLANE_
  EXCLUSIONS / _OBJECT_IDENTITY_INTRINSICS / _INTRINSIC_TYPE_NAMES 全部入清单）。
- 机制同构：能力声明 = 单一权威源（design-philosophy §一），路由 = 查询结果。

### D2：单一状态物化机制（替代镜像双路径 + 旁路 + repr 降级）

- **状态契约重设计**：Rust 执行后状态经 **typed value 通道**导出（值 + 类型标签：
  {kind: int|float|str|bool|none|list|dict|function|quoted|vector|knowledge|error,
  value}），不经 repr 字符串降级（消除 N1 的类型信息丢失 + 镜像再水化特判）。
- **单一物化转换表**：值 (kind, value) + declared_type → Python 对象模型 = 一张
  数据驱动的转换表（每个 kind 一个转换器，注册式），engine **不做语义判断**——
  类型检查归属执行核心（Rust 内移植），状态容器只做物化。
- materialize_variable 旁路删除（物化统一走转换表 + 正常 define 路径）。

### D3：类型化跨边界契约（替代字符串协议 + 正则 + _RUST_ERROR_CODES）

- Rust 边界返回结构化错误：{class, code, line, col, message}（Thrown 已含
  class/message/pos——直接在边界结构化，不降级字符串）。
- 诊断码映射**单一真相**：由 Rust 侧持有（每个 runtime_error(class) 调用点直接带码）
  或结构化 class 字段由 Python 侧一张表映射——二选一，**消除 _RUST_ERROR_CODES 与
  functions.py 的双真相**（推荐：诊断码 = Rust 侧单一声明，Python 契约层引用）。
- RecursionError contains 特判删除（结构化 class 直接判定）。

### D4：宿主 callable 统一协议（替代 WIP 会话 API）

- 函数值宿主调用 = **HostService 面统一 callable 协议**：Rust 函数值状态经 typed
  通道导出后，宿主侧经协议调用（不另开持久会话通道）；会话生命周期 = 状态值持有
  期（随物化对象引用计数），非全局 SESSIONS 注册表 + unsafe raw ptr。
- open_session/session_call/session_release/RustFunctionProxy 删除。

### D5：执行通道收敛（消除双通道）

- run_artifact_state（一次性 + 状态导出）为**唯一**执行入口；删除持久会话通道。
  函数值跨调用状态（闭包/计数器）经 typed 函数值通道 + HostService 协议承载
  （若契约需要），不经第二条执行通道。

---

## 七、执行纪律（使命 3）

- **独立隔离分支**（大范围破坏性重构 100% 授权；零风险确认[全量 pytest 零回归 +
  复核放行]后直接 merge unsafe-vibe-dev；merge 即删分支；main 永不触碰；禁 push）。
- 分阶段实施 + 每阶段差分门/受影响子集+smoke 零回归 + commit + 文档同步。
- 测试体系重设计（使命 2）与接口层重设计（使命 3）协同推进：新接口落地后测试断言
  面按新体系承接（契约不留空洞）。
- 每步 WORKLOG 详尽记录（决策依据/方案取舍/变化前后）。
