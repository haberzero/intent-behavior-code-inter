# COMPLETED — 极简时间线归档

> 本文档以**极简时间线**记录主线工作的完成节点。
> 更早期的详细日志见 `docs/HISTORY_LOG.md`。
> 设计与实现细节见对应正式文档：`docs/TYPE_SYSTEM_DESIGN.md`、`docs/VM_AND_INTERPRETER_DESIGN.md`、`docs/VM_SPEC.md`、`docs/ARCH_DETAILS.md`。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；阻塞项见 `docs/PENDING_TASKS.md`。
>
> **最后更新**：2026-05-28（super() 修复 + __restore__ 冗余消除）

---

## 2026-05-28：super() 修复 + __snapshot__/__restore__ 协议完善

测试基线：**838 passed, 2 skipped**（0 failures）。

- **super() SEM_001 修复**：`SymbolResolutionPass.visit_IbFunctionDef` 现在为类方法注入 `super` 符号（使用固定 UID `"builtin:super"` 与 runtime `IbSuperProxy` 注入对齐）。此前 `super()` 在编译期被标记为"未定义符号"，导致 `IBCI_SYNTAX_REFERENCE §6.4` 文档示例无法编译。
- **__restore__ 冗余调用消除**：
  - `vm_handle_IbRetry`：移除 `restore_snapshot` 调用——`retry` 语句现只设置 hint + `should_retry` 标志
  - `vm_handle_IbLLMExceptionalStmt`：添加 `first_iteration` 守卫，首次迭代跳过 restore（刚 save_context 完成，状态一致）
  - 效果：`__snapshot__` 恰好调用 1 次（帧创建），`__restore__` 恰好每轮 retry 调用 1 次（无冗余）
- **super() e2e 测试**：新增 `TestE2ESuperCall` 测试类（6 个测试用例），覆盖 `super().__init__`、`super().method()`、多级继承、虚方法分发保持等场景
- **文档更新**：KNOWN_LIMITS §六更新 `super()` 规避方案代码示例

---

## 2026-05-27：紧急 Bug 修复 + KNOWN_LIMITS 文档大扫除

测试基线：**832 passed, 2 skipped**（0 failures）。

- **BUG #A 修复**：统一 `if`/`while`/`for` 在 LLM 条件不确定时的语义——`vm_handle_IbIf` 和 `vm_handle_IbWhile` 原先静默吞掉 uncertain 条件（跳过分支/退出循环），现改为与 `vm_handle_IbFor` 一致，抛出 `LLMParseError`（由 `llmexcept` 接管或向用户报错）
- **示例修复**：`examples/01_getting_started/03_flow_control_and_behavior.ibci` 改用 MOCK 指令确保零配置跑通
- **示例修复**：`examples/03_advanced_features/isolation_demo/parent.ibci` 路径修正（`./sub_project/child.ibci`）
- **KNOWN_LIMITS 文档大扫除**：
  - 移除已修复条目（旧§1/§2/§6/§8/§9/§16.1-16.3/§16.5/§16.6/§22/§23/§24/§25）
  - 修正过时描述：旧§12.3（容器快照已通过 deep_clone 正确还原）、旧§20.4（`__snapshot__`/`__restore__` 协议已实现）、旧§10（VMExecutor 已支持复杂表达式字段默认值）、旧§20.3/§20.5（SEM_092/SEM_091 已实现）
  - 重新编号，精简至 16 节（从 26 节缩减）

---

## 2026-05-27：Phase 2 `__payload_prompt__` 多模态 payload 协议实现完成

测试基线：**832 passed, 2 skipped**（0 failures）。

- **Phase 2**：多模态 payload 构建基础设施——`__payload_prompt__` 协议层 + `_obj_to_payload()` 分发 + `_evaluate_segments_cps` 混合 content blocks + AIPlugin 多模态 API 调用
- **新协议**：`has_payload_prompt_cap` 标志 + `__payload_prompt__` 方法（TypeAxiom/BaseAxiom 层）
- **新方法**：`LLMExecutorImpl._obj_to_payload()`、`AIPlugin._flatten_content_parts()`、`AIPlugin._build_user_content()`
- **架构特性**：receive() 分发一致性、相邻 str 合并、纯文本路径零开销向后兼容、MOCK 模式展平处理
- **测试**：`tests/e2e/test_e2e_multimodal_payload.py` 覆盖 13 个场景（向后兼容、辅助方法、协议分发）
- **技术债记录**：payload 验证层待实现、`_call_llm_raw` 待 Phase 4、dispatch_eager 多模态交互测试待补充

## 2026-05-27：Phase 1 命名模型路由实现完成

测试基线：**818 passed, 2 skipped**（0 failures）。

- **Phase 1**：`@NAME~` 语法端到端路由实现——VM handler 提取 `tag` 字段 → `LLMExecutorImpl` 接收 `target_model` 参数 → `AIPlugin.__call__` 路由到命名模型配置
- **新 API**：`ai.register_model(name, url, key, model)` — 注册命名模型用于路由
- **架构特性**：命名模型客户端缓存、tag 大小写敏感（精确匹配）、后向兼容（空 tag 走默认路径）
- **测试**：`tests/e2e/test_e2e_model_routing.py` 覆盖 7 个场景（默认路径、注册模型路由、字母数字 tag、MOCK 模式兼容、多模型并存、大小写敏感、大小写区分注册）
- **文档修正**：更正 `MULTIMODAL_BEHAVIOR_DESIGN.md` 中关于 `isalpha()` 的错误声明（实际源码使用 `isalnum()`），更新 Phase 1 状态为已完成

## 2026-05-27：P0-3 统一初始化路径完成

测试基线：**812 passed, 2 skipped**（0 failures）。

- **P0-3**：实现 `_bind_operator_method()` 显式绑定运算符方法，消除技术债，架构对称性完成
- 用户类与内置类运算符绑定机制差异已文档化
- 编译期保证 + 运行期 `receive()` 统一派发

---

## 2026-05-26：P0-C `nonlocal` 关键字全链路实现完成

测试基线：**790 passed, 2 skipped**（0 failures）。

- **P0-C**：`nonlocal` 关键字完整实现——Lexer（`TokenType.NONLOCAL`）→ Parser（`IbNonlocalStmt`）→ SymbolResolutionPass（`_collect_nonlocal_names` + `_prescan_body_locals` 跳过 + `visit_IbNonlocalStmt` 外部绑定验证）→ BindingAnalysisPass（Cell 提升标记）→ VM（`vm_handle_IbFunctionDef` Cell 闭包构建 + 写回）
- **错误诊断**：SEM_060（模块级 nonlocal 禁止）、SEM_061（外部作用域无此变量）
- **测试**：`tests/compiler/semantic/test_nonlocal.py` 覆盖 11 个场景（简单写回、多变量、计数器模式、两层嵌套、返回闭包读/写、多闭包共享 Cell、错误诊断、lambda 交互）
- **INV-CONTEXT-2 合约测试解除 SKIP**：使用 nonlocal 语法实现"多闭包独立帧"测试

---

## 2026-05-26：P0-A/B 行为表达式一般化完成

测试基线：**778 passed, 3 skipped**（0 failures）。

- **P0-A**：解除 3 项 SKIP 测试（INV-BEHAVIOR-4, INV-CONTEXT-1, INV-CELL-2）— 底层实现已到位，编写正式测试验证
- **P0-B**：行为表达式参与二元运算（INV-BEHAVIOR-3）— `TypeCheckingPass.visit_IbBinOp/visit_IbCompare` 增加 behavior 操作数适配
- **确认为设计限制**（保持 SKIP）：INV-LAMBDA-3（无 walrus/lambda 体赋值）、INV-SCOPE-1（SEM_002 禁止 if-block 重声明）

---

## 2026-05-25：Semantic Pipeline 5 步架构改进全部完成 + OOP 诊断增强

测试基线高峰：**806 passed, 7 skipped**（后经测试合并降至 778）。

- **PT-ARCH-1→5 全部完成**：
  - Step 1: TypeEnvironment → TypeInferenceState（frozen dataclass）
  - Step 2: ScopedVisitor 统一基类
  - Step 3: `SpecRegistry.resolve_call_return()` 统一类型决议
  - Step 4: 7-Pass 归并为 4-Phase（SymbolPhase → TypePhase → BindingPhase → IntegrityPhase）
  - Step 5: PassOutput + Immutable Pipeline + MetadataStore.from_outputs()
- **P2-B SEM_090**：intent_context 静默无效陷阱警告
- **P2-C SEM_091**：编译期 cast 转换合法性校验
- **P2-D SEM_092**：方法重写签名兼容性检查（逆变参数 + 协变返回）
- **P2-E SEM_093**：super() 调用合法性检查

---

## 2026-05-24–25：v2 Semantic 全面替代 v1

- **v2 默认启用 + 12 项 parity 修复**（锚点 C）
- **v2 100% 输出 parity**（锚点 B）：SEM_052 read-only + node_to_symbol 100% + 对比测试套件
- **TypeCheckingPass 静态诊断补全**（锚点 D）：fn 签名结构检查、Lambda 类型安全、泛型容器、Optional、Tuple 位置推断
- **v1 代码完全删除**：`semantic_v2` → `semantic` 重命名完成

---

## 2026-05-22：P1 全套完成 + P0 三项基础修复

- **P1-A**：文档与 v2 自我矛盾收口
- **P1-B**：核心设计原则补全（auto 单次锁定、any 永久动态、-> auto 统一、BinOp 公理自决议）
- **P1-C**：TypeCheckingPass 新增 17 个 visitor
- **P1-E**：独立 TypeResolutionPass
- **P1-F**：`_bind_llm_except` 复刻到 v2
- **P0 三项**：H5 测试基线恢复 + 双写真相收敛 + v2 阻塞 bug 修复

---

## 2026-05-15 及更早：详细日志

详见 `docs/HISTORY_LOG.md`。主要里程碑包括：

- 2026-05-15：回顾性事实核查 + ARCHITECTURE_REVIEW 报告
- 2026-05-14：one-shot 意图注释语义升级 + H1/H2/H3/H4 维修 + 事实重核
- 2026-05-13：LLM 解析责任链重构 + 代码库健康度审计 + 测试体系契约化
- 2026-05-12：NS-4/NS-6/NS-7 语法清理 + PT-1.2/1.3/3.3 idbg + NS-3/PT-2.1/2.2 CPS 化
- 2026-05-11：lambda/snapshot 语义对齐 + NS-1 CPS 合流 + NS-2 intent OOP 化
- 2026-05-08：类型系统五件套 M1-M5 + VM CPS 全链路 + 语法系统重设计
- 2026-04-28~29：VM CPS 调度循环 + DDG 编译期分析 + 公理化通道

---

## 关联文档

- 类型系统正式设计：`docs/TYPE_SYSTEM_DESIGN.md`
- VM 与解释器正式设计：`docs/VM_AND_INTERPRETER_DESIGN.md`
- VM 公理化规范：`docs/VM_SPEC.md`
- 实现细节备份：`docs/ARCH_DETAILS.md`
- 意图系统：`docs/INTENT_SYSTEM_DESIGN.md`
- 架构原则：`docs/ARCHITECTURE_PRINCIPLES.md`
- 当前已知限制：`docs/KNOWN_LIMITS.md`
- 历史详细日志：`docs/HISTORY_LOG.md`
