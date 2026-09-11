# R3 阶段 C：白盒断言迁移映射（2026-09-11）

> 测试体系五层重构·阶段 C：runtime/kernel 白盒断言（VM 内部形态）降级删除。
> 纪律（使命 2 设计固化）：**删除前必须确认契约面已被新体系承接（契约不留空洞）
> ——每个被删测试的断言 = 可观察面/契约面 的显式迁移映射，记入本表**。
> 分类：行为（→语言行为层）/ 契约（→契约层）/ 宿主（→宿主面层）/
> 内部（→删除——VM 内部形态，契约经行为/契约/宿主层承接或显式迁移）。

## 一、强白盒文件（21 个，82 测试函数触及内部）逐文件映射

| 文件 | 断言面 | 分类 | 承接面/动作 |
|------|--------|------|------------|
| test_vm_run_many.py | VMExecutor.run_many 多根并发（extract uid + make_vm + 内部编排） | 内部 | 删除；可观察契约（2 独立 LLM 行为根并发求值 + LLM 请求数）= 宿主层新测试承接（R3-C1） |
| test_execution_context.py | ExecutionContextImpl 结构化查询（llmexcept 语句/内联保护/filtered expr/节点池） | 内部 | 删除；llmexcept 行为契约 = e2e/test_llmexcept.py + 既有 e2e 覆盖（快照隔离警告在测试运行可见） |
| test_file_handle.py | 文件句柄（读/写/克隆/序列化）+ clone_ref/deep_clone 内部 | 宿主（文件 IO）+ 内部 | 保留（宿主层归类）；clone_ref/deep_clone 内部断言 → 后续重构为可观察（阶段 C 续） |
| test_media_file_handle.py | media 文件句柄（audio/image/video） | 宿主 | 保留（宿主层）；media Phase 4 封存——验证其仍为活跃资产（PT-SEALED-1 不触碰，仅归类） |
| test_overlay_concurrency.py | overlay 并发窗口 | 宿主 | 保留（宿主层归类） |
| test_pre_eval_fallback.py | pre-eval 回退 + 诊断 | 宿主 | 保留（宿主层归类） |
| test_protocol_dispatch_contract.py | receive/vtable 协议分发（对象系统契约） | 契约 | 保留（契约层归类） |
| test_member_single_authority.py | spec 成员/方法表单一权威 | 契约 | 保留（契约层归类） |
| test_serialization.py | 序列化/artifact | 契约 | 保留（契约层归类） |
| test_generic_value_identity.py | 值身份/特化 + deep_clone 内部 | 契约（序列化往返）+ 内部 | 保留（契约层）；deep_clone 内部断言 → 后续重构（阶段 C 续） |
| test_optional_value_model.py | Optional 值语义（is_none/unwrap/identity/包装） | 行为 | 保留并迁移行为层（Optional 语言语义；identity 2 例 = 打破清单 #2 待重设计） |
| test_vector_type.py | vector 值语义/方法面 | 行为 | ✅ 迁移 tests/behavior/test_vector_behavior.py（18 可观察断言：值语义/构造封死/dim 不一致/dict 键/数学性质[精确值钉语义]；round-trip = Rust artifact 契约面；parity = 契约层 embedding_protocol）——白盒文件删除 |
| test_world_model_kb.py | KB 世界模型（治理/事实/查询） | 行为 | 保留并迁移行为层（KB 语义） |
| test_knowledge_type.py | KB 类型（store/快照/amend 门） | 行为 | 保留并迁移行为层 |
| test_knowledge_to_ibci.py | KB → IBCI 投影（P7 to_ibci） | ⑦ 路径 | ✅ 删除 + 契约登记：to_ibci = Python 参考 KB 功能（Rust kb.rs 无此分派——角路由送 Python；行为层须内核无关，非本层材料）；投影语义 = PENDING（⑦ 终点裁决：移植 Rust kb.rs 或退役） |
| test_narrow_model_type.py | narrow_model 工件（score/topk，P5） | 行为 | 保留并迁移行为层 |
| test_run_result_type.py | run_result 值类型 | 行为/契约 | 保留（契约层归类） |
| test_specialization_identity_runtime.py | 容器特化身份（运行时） | 行为/内部 | ✅ 迁移行为层（跨模块特化独立 = 可观察类型不匹配断言）；3 个 VM 内部函数直调（_resolve_type_identifier/_type_ref_name）= 删除（VM 内部形态，无语言级契约）——白盒文件删除 |
| test_storage_model_dispatch.py | 存储模型分发 | 内部/契约 | 保留（契约层）；内部断言后续重构 |
| test_thread_cleanup.py | 线程清理 | 宿主 | 保留（宿主层归类） |
| test_quoted_type.py | quoted 值类型/序列化 | 行为/契约 | 保留（契约层 + 行为层引用） |

## 二、R3-C1/C2 执行切片

- **R3-C1**：test_vm_run_many.py / test_execution_context.py 删除（契约承接）。
- **R3-C2**：test_vector_type.py → 行为层迁移（18 断言，白盒删除）。
- **R3-C3**：test_specialization_identity_runtime.py → 行为层迁移（跨模块特化独立可观察断言；3 个 VM 内部直调删除），白盒删除。
- **R3-C4**：test_knowledge_to_ibci.py 删除（to_ibci = Python 参考 KB 功能，⑦ 路径；契约登记 PENDING——移植 Rust 或退役，⑦ 终点裁决）。

### C1 切片（原记录）

| 动作 | 文件 | 映射依据 |
|------|------|---------|
| 删除 | test_vm_run_many.py | 断言 = VM 内部编排（run_many/UUID 提取）；可观察契约 = 2 独立 LLM 行为根并发求值 + LLM 请求数——**宿主层新测试承接**（R3-C1 新增 tests/host/test_llm_behavior_roots.py） |
| 删除 | test_execution_context.py | 断言 = ExecutionContextImpl 查询 API 内部形态；llmexcept 行为契约 = e2e/test_llmexcept.py 承接（快照隔离 + 重试行为可观察） |

## 三、宿主面层组建（R3-C1 同步）

- 新建 tests/host/ 层（LLM/意图/IO/线程/对象系统 = Python 宿主契约）：
  test_llm_behavior_roots.py（LLM 行为根可观察契约——承接 vm_run_many 删除面）。
- 既有宿主族文件（file_handle/media/overlay/pre_eval/thread_cleanup + e2e 宿主族）
  归类登记（本表"宿主"行），物理移动 = 阶段 C 续（避免大范围移动引入回归）。

## 四、纪律

- 每删除一项 = 本表登记 + 全量 pytest 零回归确认（合并门）。
- 不为规避缺陷改套件（缺陷触发用例保留）。
- 行为/契约/宿主层承接面须实跑验证（新承接测试先落，再删旧测试——本切片顺序）。
