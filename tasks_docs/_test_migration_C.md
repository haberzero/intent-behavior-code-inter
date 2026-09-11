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
| test_optional_value_model.py | Optional 值语义（is_none/unwrap/identity/包装） | 行为 | ✅ 迁移 tests/behavior/test_optional_behavior.py（28 断言）；**打破清单 #2 落地**：空 Optional = None 值语义统一（`a is b`=True——原 Python 包装实例身份废弃，optional_instance_identity 角移除，Rust 权威化）——白盒文件删除 |
| test_vector_type.py | vector 值语义/方法面 | 行为 | ✅ 迁移 tests/behavior/test_vector_behavior.py（18 可观察断言：值语义/构造封死/dim 不一致/dict 键/数学性质[精确值钉语义]；round-trip = Rust artifact 契约面；parity = 契约层 embedding_protocol）——白盒文件删除 |
| test_world_model_kb.py | KB 世界模型（治理/事实/查询） | 行为 | ✅ C7a+C7b 完成：tests/behavior/test_kb_world_model_behavior.py（30 断言——词表/事实/查找/对比展开/审计/deep_clone/entries 零回归）；索引结构（_indexes 内部形态）= 内部删除（契约 = 查询面[active vs 全日志]已承接）；legacy 序列化 round-trip = ⑦ 路径删除（Rust artifact 契约面 + ihost 宿主层状态测试）——白盒文件删除 |
| test_knowledge_type.py | KB 类型（store/快照/amend 门） | 行为/宿主 | ✅ 迁移 tests/behavior/test_knowledge_store_behavior.py（15 断言：store/get/快照隔离/keys/审计链/验证门[诊断码+定位]/check 纯度[编译诊断码]）+ tests/host/test_knowledge_state.py（2 断言：ihost 状态往返）；2 序列化 round-trip = ⑦ 路径删除+契约登记（Rust artifact 契约面）——白盒文件删除 |
| test_knowledge_to_ibci.py | KB → IBCI 投影（P7 to_ibci） | ⑦ 路径 | ✅ 删除 + 契约登记：to_ibci = Python 参考 KB 功能（Rust kb.rs 无此分派——角路由送 Python；行为层须内核无关，非本层材料）；投影语义 = PENDING（⑦ 终点裁决：移植 Rust kb.rs 或退役） |
| test_narrow_model_type.py | narrow_model 工件（score/topk，P5） | 宿主 | ✅ 迁移 tests/host/test_narrow_model.py（12 断言：TransE score/topk[序/k/确定性 tie-break/纯函数]/元数据/fail-fast[NAR_*]/不可变面/content_hash 篡改门——bind_artifact 语言路径 + artifact 夹具[canonical hash 正确计算]）；vtable 绑定/内部 to_native/deep_clone/legacy 序列化 collect = 内部/⑦ 路径删除——白盒文件删除 |
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
- **R3-C5**：test_knowledge_type.py → 行为层 15 断言 + 宿主层 2 断言迁移，2 序列化 round-trip = ⑦ 路径删除，白盒删除。
- **R3-C6**：test_optional_value_model.py → 行为层 28 断言（含打破清单 #2：Optional 空值 = None 值语义统一——`a is b`=True，optional_instance_identity 角移除），白盒删除。
- **R3-C7a/C7b**：test_world_model_kb.py → 行为层 30 断言全平面迁移（前置 GAP-vec-kb-failfast 已关闭）；索引结构 = 内部删除；legacy 序列化 = ⑦ 路径删除——白盒文件删除。
- **R3-C8**：test_narrow_model_type.py → 宿主层 12 断言（bind_artifact 语言路径 + artifact 夹具）；内部/⑦ 删除 8——白盒文件删除。
- **已归层无动作**：file_handle/media_file_handle/overlay_concurrency/pre_eval_fallback（宿主层）/ protocol_dispatch_contract/member_single_authority/serialization/run_result_type/storage_model_dispatch（契约层）——保留原文件仅归层。
- **剩余工作项**：optional_value_model（30 测试——identity 2 例 = 打破清单 #2 待重设计）/ world_model_kb（36 测试——大件，kb 治理 GAP 一并裁决）/ narrow_model（宿主层 + artifact 夹具）/ file_handle·generic_value_identity·storage_model_dispatch（clone_ref 内部断言重构）+ cargo test 内核层组建。

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
