# P9 全量 Rust 化评估（核心逻辑面盘点 + Rust 化覆盖分析 + 可行性评估）

> **用户 2026-09-10 裁定**：Rust 部分任务完成后，开启新评估 + 新自主执行模式，评估
> **全核心逻辑、全量 Rust 化**。保留关键部分的 Python 接口（提供灵活性和供 Python
> 使用的入口能力）。证明绝大部分关键核心逻辑都可以 Rust 化的时候，全量转向 Rust，
> 不再保留 Python 双通道和对比。
>
> 本评估 = P9 Rust 部分（阶段②③④）完成后的**全量 Rust 化评估前置**——盘点全核心
> 逻辑面、分析 Rust 化覆盖、评估可行性、识别关键 Python 接口。
>
> 本文件为设计阶段临时任务控制文档（评估/决策），落地后收敛（删除或归档）。

## 一、全核心逻辑面盘点（规模 + 当前 Rust 化状态）

IBC 核心逻辑 = 编译（前端）→ 语义 → 序列化 → 执行（VM）→ 调度 → 并发 → 值对象 →
宿主服务。规模（Python 行数）+ 当前 Rust 化状态：

| 核心逻辑面 | 规模（Python 行） | 当前 Rust 化状态 | 说明 |
|---|---|---|---|
| **编译·lexer** | 1238 | ✅ 已 Rust 化 | Rust lexer（`ibci-ext/src/lexer.rs`），token 级差分等价 |
| **编译·parser** | 3267 | ✅ 已 Rust 化 | Rust parser（`ibci-ext/src/parser.rs`），AST 级差分等价（34 语料） |
| **编译·semantic** | 8317 | ⏸ 推迟（最大面） | 多 pass 语义管线（符号表/类型表/scope/作用域）——Rust 执行核心消费 Python 前端产出的 artifact（FlatSerializer JSON），语义层移植 = 全量 Rust 化后续 |
| **序列化** | 329 | ⏸ 未 Rust 化 | FlatSerializer（AST + 语义 → JSON artifact）——Rust 执行核心消费其 JSON 产物 |
| **执行·VM（CPS 执行核心）** | 4404（core/runtime/vm）+ 6589（core/runtime/interpreter）≈ 11000 | 🟡 部分 Rust 化 | Rust 执行核心 = tree-walking 解释器（消费 artifact，数据面 34/34 全级差分等价，23–30x）；全量 CPS VM（LLM/意图/宿主面）= Python |
| **调度·task_scheduler** | 229 | 🟡 GIL-free 集成已验证 | Python task_scheduler（协作式 IO 调度）+ Rust TaskPool（GIL-free 并行 CPU）——集成验证（并发比 1.04）；task_scheduler 原生 CPU 任务类型 = 全量 Rust 化后续 |
| **并发** | —（横切） | ✅ 已 Rust 化 | GIL-free 并行执行（py.allow_threads + run_artifacts_parallel + TaskPool，4 线程 ≈3.3x） |
| **值对象** | 8902（core/runtime/objects） | ⏸ 未 Rust 化 | IBC 值对象（IbInt/IbStr/IbList/... + IbQuoted/IbKnowledge 等）——Rust 执行核心用 IbValue（Rust 侧值类型），宿主值经 Py<PyAny> 桥接 |
| **宿主服务** | 670（core/runtime/host） | ⏸ 未 Rust 化 | HostService（LLM/quote/eval/KB 操作）——Rust 执行核心经桥接委托（host-service bridge） |

**关键观察**：
1. **编译（前端）+ 并发 + 执行核心（数据面）已 Rust 化**——Rust 内核覆盖 IBCI 确定性
   代码的核心路径（lexer + parser + 执行核心 + GIL-free 并发）。
2. **语义层（8317 行，最大面）推迟**——Rust 执行核心消费 Python 前端产出的 artifact
   （FlatSerializer JSON），语义层移植 = 全量 Rust 化的关键剩余项。
3. **值对象（8902 行）+ 宿主服务（670 行）未 Rust 化**——Rust 执行核心用 IbValue
   （Rust 侧值类型），宿主值经 Py<PyAny> 桥接；值对象/宿主服务 Rust 化 = 全量 Rust 化
   后续。
4. **CPS VM（LLM/意图/宿主面）未 Rust 化**——Rust 执行核心是 tree-walking 解释器
   （确定性代码面），全量 CPS VM（LLM/意图/宿主面）= Python。

## 二、Rust 化覆盖分析（已证明 vs 剩余）

**已证明（差分等价，34 语料全级）**：
- lexer（token 级）✅
- parser（AST 级）✅
- 反序列化（artifact → Rust AST）✅
- 执行核心·数据面（确定性代码，含闭包/KB/quoted 值/from-import）✅
- 符号表 + 类型表（artifact 消费）✅
- 并发（GIL-free 并行执行 + TaskPool）✅

**剩余（未 Rust 化）**：
- **语义层**（8317 行，多 pass 管线）——最大剩余项。
- **序列化**（FlatSerializer，329 行）——artifact 产出。
- **值对象**（8902 行，IBC 值类型）——IbInt/IbStr/IbList/... + IbQuoted/IbKnowledge。
- **宿主服务**（670 行，LLM/quote/eval/KB）——HostService。
- **CPS VM（LLM/意图/宿主面）**——全量 CPS 执行核心（非 tree-walking 解释器）。

**覆盖比例**：已 Rust 化 ≈ 编译（前端 4505 行）+ 执行核心（数据面）+ 并发；剩余 ≈
语义（8317）+ 序列化（329）+ 值对象（8902）+ 宿主服务（670）+ CPS VM（LLM/意图/宿主面）。
**绝大部分关键核心逻辑（确定性代码路径：编译 + 执行 + 并发）已 Rust 化**；剩余关键
项 = 语义层（最大）+ 值对象 + 宿主服务 + CPS VM（LLM/意图/宿主面）。

## 三、全量 Rust 化可行性评估（逐面）

| 面 | Rust 化可行性 | 依据 | 风险/难点 |
|---|---|---|---|
| **语义层**（8317 行） | 🟡 高（最大工作量） | 多 pass 管线（符号表/类型表/scope）——纯计算（无 IO/LLM），Rust 移植可行（lexer/parser 已证 Rust 前端可行） | 工作量大（8317 行）；多 pass 依赖链复杂；差分验证需扩语料（语义面） |
| **序列化**（FlatSerializer，329 行） | 🟢 高 | AST + 语义 → JSON——纯计算，Rust 移植可行（Rust 反序列化器已证） | 规模小（329 行）；与语义层耦合 |
| **值对象**（8902 行） | 🟡 中 | IBC 值类型——纯数据 + 少量计算；Rust 侧已有 IbValue（执行核心价值类型） | 规模大（8902 行）；IbQuoted/IbKnowledge 等复杂值对象；与宿主服务耦合 |
| **宿主服务**（670 行） | 🔴 低（保留 Python） | LLM/quote/eval/KB 操作——涉及 LLM IO + 宿主集成；Rust 化需 LLM 客户端（Rust）+ 宿主桥接 | LLM IO 面（非纯计算）；宿主集成面（保留 Python 接口） |
| **CPS VM（LLM/意图/宿主面）** | 🔴 低（保留 Python） | 全量 CPS 执行核心——涉及 LLM/意图/宿主（非纯计算）；Rust 执行核心（tree-walking）已覆盖确定性代码面 | LLM/意图/宿主面（非纯计算）；保留 Python 接口 |

**可行性结论**：
1. **确定性代码路径（编译 + 执行 + 并发）已 Rust 化**——绝大部分关键核心逻辑（确定性
   代码）可 Rust 化（已证明）。
2. **语义层 + 序列化 + 值对象 = 可 Rust 化（纯计算）**——语义层（最大工作量）+ 序列化
   + 值对象是纯计算面，Rust 化可行（lexer/parser 已证 Rust 前端可行，IbValue 已证 Rust
   值类型可行）。
3. **宿主服务 + CPS VM（LLM/意图/宿主面）= 保留 Python**——涉及 LLM IO + 宿主集成
   （非纯计算），保留 Python 接口（用户裁定：保留关键部分 Python 接口）。

## 四、关键 Python 接口识别（保留供 Python 使用的入口能力）

用户裁定：**保留关键部分的 Python 接口**（提供灵活性和供 Python 使用的入口能力）。关键
Python 接口 = 供 Python 使用的入口 + LLM/意图/宿主面：

1. **入口能力**（供 Python 使用）：
   - `run_ibci(code)` / `compile_ibci(code)`——IBC 代码入口（保留 Python 接口）。
   - `run_artifact(artifact_json, bridge)` / `run_artifacts_parallel` / `TaskPool`——
     Rust 内核入口（已 Python 可调用，经 pyo3）。
2. **LLM/意图/宿主面**（保留 Python）：
   - HostService（LLM/quote/eval/KB 操作）——保留 Python（LLM IO + 宿主集成）。
   - CPS VM（LLM/意图/宿主面）——保留 Python（非纯计算）。
   - 值对象（IbQuoted/IbKnowledge 等）——保留 Python 接口（宿主值类型）。

**保留策略**：确定性代码路径（编译 + 执行 + 并发 + 语义 + 序列化 + 值对象）Rust 化；
LLM/意图/宿主面（宿主服务 + CPS VM）保留 Python 接口。Rust 内核经 pyo3 暴露 Python
可调用入口（run_artifact/run_artifacts_parallel/TaskPool），供 Python 使用。

## 五、全量 Rust 化执行计划（评估结论）

1. **阶段 A（已证明）**：确定性代码路径（编译 + 执行 + 并发）Rust 化——✅ 完成（P9
   阶段②③④）。
2. **阶段 B（可 Rust 化，纯计算）**：
   - 语义层（8317 行，最大）——Rust 移植（多 pass 管线，纯计算）。
   - 序列化（FlatSerializer，329 行）——Rust 移植（AST + 语义 → JSON）。
   - 值对象（8902 行）——Rust 移植（IBC 值类型，扩展 IbValue）。
   - 验证：差分 harness 扩语料（语义/序列化/值对象面），逐级差分等价。
3. **阶段 C（保留 Python，LLM/意图/宿主面）**：
   - 宿主服务（HostService）——保留 Python（LLM IO + 宿主集成）。
   - CPS VM（LLM/意图/宿主面）——保留 Python（非纯计算）。
   - Rust 内核经 pyo3 暴露 Python 可调用入口（run_artifact/TaskPool），供 Python 使用。
4. **全量转向 Rust（不保留双通道）**：阶段 B 证明绝大部分关键核心逻辑（语义 + 序列化
   + 值对象）可 Rust 化后，全量转向 Rust（确定性代码路径全 Rust），不再保留 Python
   双通道和对比；LLM/意图/宿主面保留 Python 接口（关键部分 Python 接口）。

**评估结论**：**绝大部分关键核心逻辑（确定性代码路径：编译 + 执行 + 并发 + 语义 + 序列
化 + 值对象）可 Rust 化**（已证明 + 可证明）；**LLM/意图/宿主面保留 Python 接口**（非
纯计算）。全量 Rust 化 = 阶段 B（语义 + 序列化 + 值对象）Rust 化 + 差分验证，之后全量
转向 Rust。

## 六、下一步（评估落地）

1. **阶段 B 启动**：语义层 Rust 移植（最大面，8317 行）——或序列化（FlatSerializer，
   329 行，规模小，先启动）——或值对象（IbValue 扩展）。
2. **差分 harness 扩语料**：语义/序列化/值对象面（扩 34 语料，覆盖语义面）。
3. **保留 Python 接口**：HostService + CPS VM（LLM/意图/宿主面）保留 Python；Rust 核
   心经 pyo3 暴露 Python 可调用入口。
