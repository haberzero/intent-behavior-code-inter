# 测试体系体系级重设计（2026-09-11 用户转向裁定，使命 2 设计文档）

> 本文件 = 使命 2（测试体系重设计）设计文档。用户裁定：内核已彻底变动，测试脚本体系
> 必须全部重新设计（哪怕上千测试项、代价巨大），必须是**体系/架构级重设计**，避免旧
> 测试体系拖累 Rust 新内核。本设计 = 自顶向下重构（非修补）。设计阶段文档，落地后收敛
> 入 docs/；与使命 3（接口层重设计）协同推进。

---

## 一、现状盘点（2026-09-11 实跑）

### 1.1 层分布（当前目录结构 = Python-VM 时代分层）

| 层 | 目录 | 测试函数数 | 现状评估 |
|----|------|-----------|---------|
| VM 内部契约 | tests/contracts | 317 | 语言语义红线（公理+语义错误集）——**保留为契约层种子** |
| 前端 | tests/compiler | 455 | 编译/语义/序列化——前端层（Python 独立面）保留 |
| VM 白盒 | tests/runtime | 955（88 文件，~50 触及内部形态） | **时代错位主体**：断言 payload 类型/符号表/作用域对象/深克隆内部 |
| 行为 | tests/e2e | 940（81 文件） | 行为面——按可观察面重构 |
| 内核 | tests/kernel | 215 | 混合：部分契约面 + 部分 VM 内部形态 |
| 差分 | tests/diff_harness | 50 | **临时机制**（⑦ 终点退场）——语料/探针 = 新体系种子资产 |
| 合规 | tests/compliance | 36 | 语言合规（行为面）——归语言行为层 |
| meta/plugins | tests/meta + tests/plugins | 9 + 46 | 宿主/扩展面 |

全量 = 4306 passed / 2 failed / 1 skipped / 140.94s（实跑）。

### 1.2 时代错位证据（审计 §三 3.7 + 实测）

1. **VM 白盒断言**（tests/runtime + tests/kernel ~50 文件触及内部形态）：
   - `make_vm`（构造 VMExecutor）、`find_node*`（node_pool 内部）、`native()`、
     `payload` 对象类型断言、`get_variable` 返回 payload 形态、`_symbols`/
     `_uid_to_symbol` 符号表内部、`deep_clone` 内部——内核换 Rust 后这些"被断言面"
     整体不存在/异构。
2. **错误断言 = 消息子串**（conftest `expect_runtime_error(code, error_pattern)`）：
   测试与 VM 时代错误文本形态耦合（与审计 3.3 错误字符串协议同族）。
3. **速度假设破裂**：test_ihost_* 超时校准 100000→15000000 迭代（⑦ 切换后子源 =
   Rust 面，注释明写"按 Rust 速度重校准"）——测试隐含执行内核速度假设。
4. **差分临时壳**：tests/diff_harness = ⑦ 设计的临时差分机制（阶段 3 退场），但其
   34 语料 + 探针（print 数据面 + 五池 artifact 面）= **内核无关行为资产**——新体系
   种子，须升格。
5. **生产路由耦合**：diff_harness/harness.py 委托生产面
   `artifact_is_rust_executable`（审计新增 N2）——测试资产与生产路由耦合。

---

## 二、目标架构：五层测试体系

> 顶层原则（用户裁定 + 审计结论）：测试断言**可观察面/契约面**（内核无关），不断言
> 实现内部形态；错误断言经**诊断码 + 结构化现场**，不经异常消息子串；临时差分机制
> 退场，其资产升格为正式行为层。

```
┌────────────────────────────────────────────────────────────┐
│ 语言行为层 tests/behavior/     源 → 可观察面（内核无关）       │
│   - 数据面（print 行列表）                                   │
│   - 错误码 + 现场位置（诊断码 + line/col/file_path）           │
│   - 状态读回（get_variable 语义值——typed 契约）              │
│   - artifact 五池 + 侧表（契约面规范形态）                    │
│   经公共 engine API（run_string/compile_string）验证          │
│   Rust/Python 内核皆可过；种子 = diff_harness 语料/探针升格    │
├────────────────────────────────────────────────────────────┤
│ 契约层 tests/contracts/        稳定契约面（跨内核不变）         │
│   - 诊断码表（RUN_* 全集单一真相）                            │
│   - 错误现场格式（Location 结构）                            │
│   - artifact 格式（schema_version / 五池 / 侧表 / hash）       │
│   - 语言语义红线（公理 + contracts 语义错误集）——继承现有      │
├────────────────────────────────────────────────────────────┤
│ 内核内部层 ibci-ext/tests（Rust cargo test）                 │
│   - parser / deserializer / serializer / interpreter 单元    │
│   - Rust 侧集成（run_artifact / capability() / typed 通道）   │
│   经 Rust 测试或内核 API，不经 Python 测试垫片                │
├────────────────────────────────────────────────────────────┤
│ 前端层 tests/compiler/         编译/语义/序列化（Python 独立面）│
│   - lexer / parser / semantic / serializer / 诊断码发射       │
│   前端与执行内核解耦（消费 artifact 契约）                    │
├────────────────────────────────────────────────────────────┤
│ 宿主面 tests/host/（原 meta/plugins/e2e 宿主族）              │
│   - HostService：LLM / IO / 线程 / 对象系统（Python 宿主契约）│
│   - 意图面 / overlay / journal / budget / deterministic       │
└────────────────────────────────────────────────────────────┘
```

### 2.1 层职责与边界

- **语言行为层**（新核心层）：唯一"内核无关行为验证"层。每条用例 = (源, 可观察断言)。
  经公共 engine API（`run_string(code, output_callback)` / `compile_string`），
  断言 = 数据面行列表 / 诊断码+位置 / 状态语义值 / artifact 规范形态。
  **双内核皆可过**——迁移期 Python 参考 + Rust 生产双跑（差分保证），迁移后 Rust 单跑
  （差分机制删除）。
- **契约层**：公开契约的**形式化规范测试**——诊断码表、错误现场格式、artifact 格式、
  语言语义红线。跨内核不变。现有 tests/contracts 语义红线族继承。
- **内核内部层**：Rust 侧单元/集成测试（cargo test，ibci-ext/tests/）——parser/
  deserializer/serializer/interpreter 独立高速；跨语言集成（pyo3 暴露函数）经 Python
  薄探针（只测"契约输入 → 契约输出"，不测实现内部）。
- **前端层**：Python 前端（lexer/parser/semantic/serializer/诊断码发射）独立测试面，
  消费 artifact 契约与 Python 前端解耦。
- **宿主面**：LLM/意图/IO/线程/对象系统 = Python 宿主契约（保留面）——LLM 语义、
  overlay、journal、budget、deterministic、ihost 等。

### 2.2 断言面纪律（强制）

1. **断言可观察面**：数据面（print 行）、错误码 + 现场位置、状态语义值、artifact 规范
   形态。**禁止**断言 payload 对象类型 / 符号表结构 / 作用域对象 / VM 内部形态（这些
   断言随 VM 退役整体删除或降级为契约面测试）。
2. **错误断言经诊断码 + 结构化现场**：`expect_runtime_error` 弃用消息子串，改
   `assert_error(code, location=...)`（诊断码 + 结构化 Location）。新 helper 统一经
   公共错误契约（使命 3 D3 类型化契约落地后 = 单一断言通道）。
3. **内核无关**：行为/契约层测试不 import 内核实现细节（不 import ibci_ext /
   core.runtime.vm / kernels 内部）；内核能力验证走内核内部层。

---

## 三、临时机制退场纪律

- **diff_harness 差分机制**（双内核对比面）= ⑦ 终点退场（迁移期临时安全网，非永久）。
- **资产升格**：34 语料 + 探针（print 数据面 / 五池 artifact 面 / 错误面探针）**正式
  迁入语言行为层**（tests/behavior/），作为内核无关行为用例（显式预期，非双内核对比）。
  divergence.py 注册表（GAP/DIVERGENCE 三态）随迁移推进收缩至清零后删除。
- **退场时点**：⑦ 终点（全量转向 Rust，Python 参考内核退役）→ 差分机制 + 注册表 +
  harness 壳删除，只留行为层显式用例。
- **迁移期保留**：迁移中 Python 参考内核仍 = 行为层用例的参考实现（双跑差分），但
  差分机制 = 壳（数据驱动对比），不寄生测试语义。

---

## 四、历史资产迁移映射（契约不留空洞）

> 每个被重构/删除的测试，其断言的可观察面/契约面须显式迁移映射——删除前确认新体系
> 承接，不留契约空洞。

| 现有资产 | 迁移动作 | 承接面 |
|----------|---------|--------|
| tests/contracts 语义红线族（317） | **保留**（契约层） | 语言语义红线，继承不动 |
| tests/contracts 非红线族 | 归类：契约面→契约层；行为面→语言行为层；内部形态→删除 | 按断言面三分类 |
| tests/compiler（455） | **保留**（前端层） | 前端独立面；错误码断言迁移至诊断码契约 |
| tests/runtime 白盒（955） | **重构为主**：断言可观察面者→语言行为层/契约层；断言 VM 内部形态者→删除（契约面经行为层承接或显式迁移） | 逐个显式映射，登记迁移表 |
| tests/runtime 行为面（print/状态/错误码） | **升格**至语言行为层 | 内核无关行为用例 |
| tests/e2e（940） | **归类重构**：纯数据面行为→语言行为层；宿主面（LLM/ihost/overlay/journal）→宿主面层 | 按层归属拆分 |
| tests/kernel（215） | 契约面→契约层；内部形态→删除/内核内部层（Rust cargo test） | 显式映射 |
| tests/diff_harness 语料/探针 | **升格**至语言行为层（显式预期用例） | 新体系种子（审计判定 (a) 保留） |
| tests/diff_harness 差分机制 | ⑦ 终点**删除** | 不留双内核对比面 |
| tests/compliance（36） | 归语言行为层 | 行为面 |
| tests/meta + tests/plugins（9+46） | 归宿主面层 | 宿主契约 |
| conftest expect_runtime_error（消息子串） | **重构**为 assert_error(code, location)（诊断码 + 结构化现场） | 契约层错误断言通道 |

**删除纪律**：① 先确认断言面被新体系承接（迁移映射登记）；② 缺陷触发用例必须保留
（真实缺陷复现证据——不为规避缺陷删测试）；③ 语义随修复演进的可重构为新语义；④
每删除一项 = 登记迁移映射（无映射不删除）。

---

## 五、实施阶段（与使命 3 协同）

> 顺序依赖：新接口层契约（使命 3 D1-D5）先落地 → 测试体系按新契约重构断言面。

- **阶段 A（使命 3 后）**：新接口契约落地（typed 状态通道 / 类型化错误契约 / 能力
  声明表）→ 语言行为层骨架（tests/behavior/ + assert_error helper + 语料升格）。
- **阶段 B**：行为层用例扩充（现有 e2e/runtime 行为面归类迁移）+ 契约层巩固（诊断码
  表单一真相测试）。
- **阶段 C**：白盒断言降级删除（逐个迁移映射登记）+ 宿主面层组建（meta/plugins/e2e
  宿主族）+ 前端层独立。
- **阶段 D（⑦ 终点）**：差分机制 + divergence 注册表 + harness 壳删除；全量基线重建
  （测试数收缩 = 差分面退役）；文档收敛（docs/ 测试体系章节）。

**每阶段门**：受影响子集 + smoke 零回归 + commit + WORKLOG 记录（变化前后/迁移映射）。

---

## 六、红线与纪律

- **唯一测试命令不变**：`.venv/bin/python -m pytest tests/`。
- **语言语义红线不变**（公理 + contracts 语义错误集）：契约层继承，重构不得削弱。
- **不为规避缺陷改套件**（唯一底线）：缺陷触发用例保留。
- **测试资产处理授权**（2026-09-11 用户裁定）：过期/被证不正确测试可自由处理（重构/
  修正/删除），重构质量原则大于维持现状；删除前登记迁移映射。
- **速度目标**：语言行为层秒级（纯进程内 + Rust 执行快）+ 内核内部层（cargo test）
  独立高速；全量基线随差分面退役收缩。
- **文档单点真理**：设计落地后收敛入 docs/（人类手册），智能体过程信息留 tasks_docs/。
