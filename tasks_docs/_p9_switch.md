# ⑦ 全量转向 Rust——切换门批次设计（v1，2026-09-11）

> 设计阶段临时文档（tasks_docs/_<task>.md 规约）。前置 = 增量 2a-3f（全 Rust
> 管线安全证明面：34 语料 + 全探针数据面逐字节等价 + full_artifact 5 池 + 2 侧表
> 内容归一等价；LLM 面 15 节点 = HostService 边界保留面裁定）。本设计 = 生产
> 切换（engine 内核选择面）的架构面；实施 = 分阶段放行门。

## 一、目标架构（切换后执行模型）

- **数据面**（确定性计算：算术/控制流/声明/异常/KB/vector/函数值/print）=
  **Rust 内核唯一执行者**（core/runtime/kernels/ibci_ext.so——run_artifact /
  rust_run_source 全管线）。
- **LLM/意图/宿主 IO 面** = **Python HostService**（engine service_context：
  LLM executor / journal / budget guard / deterministic guard / intent 注入）。
- **engine.execute 路由**（面分区，非双通道）：
  ```
  artifact → 节点类型集合判定
    无 LLM 面 15 节点 → ibci_ext.run_artifact(artifact_json, host_service_bridge)
    含 LLM 面节点   → Python 运行时（LLM 面语义宿主，保留）
  ```
  每个源按节点类型归属单一内核（无对比/无静默回退——双内核协议维持）；
  LLM 面 = Python 面（主线目标"仅 LLM/意图/宿主 IO 面保留 Python 接口"）。

## 二、HostService 桥接面（Rust bridge 承载）

Rust 现有 bridge 机制（Py<PyAny> 委托：call_host_function /
get_host_attribute / call_host_method）= 切换面承载。HostService 对象
（Python 侧）契约：
- **LLM 调用**（llm() 内征 → Python LLM executor → 值/quoted 返回）
- **意图面**（intent 解析/注入/上下文）
- **journal 写**（LLM 审计侧信道——run 级挂载）
- **budget guard 检查**（api_config budget 节驱动）
- **KB** = Rust 原生（41 成员面——不经桥[2a-2c 已去 Host 化]）
- 桥接调用 = GIL 协作（Python::with_gil 重取）；纯 CPU 段 = GIL 释放
  （allow_threads——现有机制）

## 三、LLM 面 15 节点（边界保留面——Python 语义宿主）

IbCastExpr/IbRetry/IbIntentAnnotation/IbImplDef/IbProtocolDef/IbHostImport/
IbBehaviorExpr/IbChannelExpr/IbAwaitExpr/IbYieldExpr/IbYieldFromExpr/
IbFilteredExpr/IbSlotExpr/IbIntentStackOperation/IbWithOverlay：
- 语义宿主 = Python LLM 运行时（协程/通道/行为执行——非纯 CPU 数据面）
- Rust 反序列化器不实现此 15 类（边界裁定[3f]）；含此 15 类的源 = Python
  运行时全源执行（不混跑——单一内核归属纪律）
- 长期演进（b 模型，非本批次）：Rust 实现 LLM 节点语义 + LLM IO 经
  HostService 桥——数据面/LLM 面全 Rust 化

## 四、变量/执行后状态面（缺口项——切换门内解决）

- **初始变量注入**：engine set_variable / run_string(variables) → Rust 内核
  需接受初始环境（Python 对象 → IbValue 转换面：py_to_ibvalue——现有
  to_py 为反方向；int/str/float/bool/None/list/dict = 原生面，其余 = Host
  残差值承载）
- **执行后变量导出**：engine get_variable → Rust 执行态导出（run_artifact
  需返回最终环境面，或 engine 数据面源 = print 输出即全部数据面契约[LLM
  面变量经 Python 侧]——裁定：数据面源执行后状态 = 仅 print 输出（Rust
  执行函数化[artifact + 初始变量 → 输出列表]，无残留态）；get_variable 对
  数据面源 = 初始变量回读（无执行期写入语义）——与 engine 现有契约对齐
  核查在实施期做（set_variable 注入的执行期可见性 = 现有 engine 语义）
- **output_callback**：Rust 输出列表 → engine output_callback 逐行回调
  （现有 run_artifact 返回列表——engine 侧适配）

## 五、切换阶段（每阶段独立放行门）

1. **阶段 1：engine 路由 + HostService 桥 + 初始变量**（本批次起点）
   - engine.execute：无 LLM 节点源 → Rust 内核（run_artifact + bridge）
   - 初始变量注入面（py_to_ibvalue + run_artifact 参数扩展）
   - 门：全量 pytest 零回归 + LLM 源行为不变（e2e overlay 等）+ 差分门
     维持（Python 数据面 VM 仍在——对比期）
2. **阶段 2：Python 数据面 VM 退役**
   - core/runtime/vm 数据面 handler 废弃（LLM handler 保留）——双通道消亡
   - 门：全量 pytest 零回归 + 差分 harness 最后一次全绿（退场前终验）
3. **阶段 3：差分 harness 退场 + 基线重建**
   - tests/diff_harness 数据面对比测试退役（保留 artifact 面对比至阶段 2 完成）
   - 全量基线重建（测试数收缩 = 差分面退役）+ 文档收敛

## 六、红线（维持）

- 双内核协议：kernel_info.status / run 入口 = 显式态（无静默回退）
- LLM 面行为契约不变（e2e/contracts 层）
- 公理层 + contracts 语义错误集不变（Rust 化不改变语言语义）
- 禁 push（硬原则）；每阶段 commit + 文档同步
