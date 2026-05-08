# IBC-Inter 架构原则（当前版）

> 本文档保留稳定且当前有效的架构原则。
> 任务控制与阶段进度不在此文档维护。
>
> 最后更新：2026-05-08

---

## 1. 核心定位

IBCI（Intent Behavior Code - Interactive）用于把：
- 确定性代码逻辑
- 非确定性 LLM 推理
统一在同一语言与运行时中表达。

---

## 2. 分层原则

- `base`：原子概念
- `kernel`：AST / spec / axioms / symbols
- `compiler`：解析、语义、序列化
- `runtime`：解释执行、VM、宿主服务
- `extension`：插件能力边界

依赖方向保持单向：
- compiler/runtime 依赖 kernel
- kernel 不依赖 runtime

---

## 3. 编译期与运行期边界

- 编译产物是可序列化结构
- 运行期通过 rehydration 执行，不反向依赖编译器实现细节

---

## 4. 类型系统与公理系统

- 类型定义：`TypeRef + TypeDef`
- 类型行为：`TypeAxiom`
- `CALLABLE_INSTANCE` 统一承载 callable value 分支（含 behavior/deferred 路线）

---

## 5. VM 与执行语义

- 主执行路径为 VMExecutor CPS 调度
- 控制流信号数据化（Signal）
- llmexcept 采用快照隔离和重试帧管理

---

## 6. Intent / Behavior 原则

- 意图上下文核心对象：`IbIntentContext`
- 函数调用意图上下文采用 fork 隔离
- `lambda` 使用调用时上下文；`snapshot` 使用创建时冻结上下文

---

## 7. 插件边界原则

- 插件通过 capabilities / registry 扩展能力
- 插件不应穿透核心层私有实现
- 任务与状态索引不在本文件维护
