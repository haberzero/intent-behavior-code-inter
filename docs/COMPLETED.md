# COMPLETED — 极简时间线归档

> 本文档以**极简时间线**记录主线工作的完成节点。
> 更早期的详细日志见 `docs/HISTORY_LOG.md`。
> 设计与实现细节见对应正式文档：`docs/TYPE_SYSTEM_DESIGN.md`、`docs/VM_AND_INTERPRETER_DESIGN.md`、`docs/VM_SPEC.md`、`docs/ARCH_DETAILS.md`。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；阻塞项见 `docs/PENDING_TASKS.md`。
>
> **最后更新**：2026-06-25（IbDict 错误类型统一 + PT-ARCH-7 Phase 4-5 完成）

---

## 2026-06-25：IbDict 错误类型统一 + PT-ARCH-7 静默吞异常治理

测试基线：**1057 passed, 5 skipped**（0 failures，无行为回归）。

### A. IbDict 错误类型统一（错误一致性修复）
- `IbDict.__getitem__` 缺键由原始 `KeyError` 统一为 `InterpreterError("KeyError: '{k}'")`，与 IbList/Tuple/String 越界行为一致（也匹配 IbDict.pop 既有风格）。
- **附带修复潜在 bug**：IbDict 存在**两个** `__getitem__` 定义（collections.py:278 与 :325），后者（无错误处理）覆盖前者。删除劣质重复版本，保留修复版。
- 风险核查：全代码库无任何处专门 catch IbDict 的 KeyError（`module_manager:146` 的 `except (InterpreterError, KeyError)` 是变量查找路径，与 dict 下标无关）。

### B. PT-ARCH-7 Phase 4-5：静默吞异常可观测化（11 处）
- 将 11 处 `except Exception: pass` 收窄为 `except Exception as e: core_debugger.trace(...)`，纯日志、无行为变更（core_debugger 默认 NONE 级，零开销）：
  - `_prompt.py` ×3（`__to_prompt__`/`to_native`/`__payload_prompt__` fallback 链）
  - `objects/kernel/base.py` ×2（cast via `__to_prompt__` / `__from_prompt__` 解析）
  - `vm/handlers/_shared.py` ×3（模块导入 / set_variable 回退 / unpack 提取）
  - `engine.py` ×1（collect 跳过不可转换值）、`interpreter.py` ×1（预评估允许失败）、`media.py` ×1（`_extract_media_storage` to_native 回退）
- `_scheduler.py __del__` 析构器**有意保持静默**（析构期日志是反模式，且可能在解释器关闭时自身失败）。

### 发现（非本轮范围）
- PT-ARCH-7 文档称"10 处"，实际 core/ 共 ~35 处 `except Exception:`。本轮处理了 11 处运行时有意图的吞异常；剩余 ~24 处多为编译层错误恢复（lexer/parser/resolver）或序列化可选路径，属另一类问题，建议作为独立审计项（见 PENDING_TASKS）。

---

## 2026-06-25：PT-TEST-4 全部完成（覆盖缺口填补 P0 收官）

测试基线：**1057 passed, 5 skipped**（0 failures，本会话累计 1011 → 1057，+46 测试）。

### area 4：`host/service.py` collect 委托
- 新增 `tests/runtime/test_runtime_host_collect.py`（4 个测试）：无 orchestrator→`RuntimeError` 守护、委托 `request_collect` 返回结果、handle 原样透传、orchestrator 异常向上传播。完整 spawn→collect 流程已由 e2e 覆盖，此处补齐薄包装自身分支。

### PT-TEST-4 收官汇总（5/5）
| 区域 | 测试 | 发现 bug |
|------|------|---------|
| `runtime/path` | 85 | 5（Windows 盘符） |
| `runtime/serialization` | 11 | 1（`define_variable` 协议混淆，反序列化此前完全不可用） |
| `engine.py` 生命周期 | 7 | 0 |
| `kernel/__getitem__` | 13 | 0（1 个不一致观察：dict 缺键 KeyError） |
| `host/service collect` | 4 | 0 |

> **方法学验证**：本会话证明"补覆盖缺口"的高价值在于暴露潜伏的回归级 bug——serialization 的反序列化此前从未可用（零测试是主因），Phase 3 注册三处断链亦由 e2e 暴露。

---

## 2026-06-25：PT-TEST-4 kernel/__getitem__ 契约覆盖

测试基线：**1053 passed, 5 skipped**（0 failures，较上轮 +13）。

### PT-TEST-4 area 3：容器/字符串 `__getitem__` 契约测试
- 新增 `tests/runtime/test_runtime_getitem_contract.py`（13 个测试）：
  - IbList：正/负索引、切片类型保持（list→list）、越界抛 `InterpreterError`
  - IbTuple：索引、切片类型保持（tuple→tuple）
  - IbDict：键访问、缺键行为、IbObject 键拆箱
  - IbString：字符索引（返回 str）、切片（返回 str）、负索引、越界 `InterpreterError`
  - IbObject 键路径（VM 实际传递 IbInteger/IbString，经 `to_native()` 拆箱）

### 观察项（非本轮改动）
- IbDict 缺键抛原始 `KeyError`，而 IbList/Tuple/String 越界抛 `InterpreterError` —— 错误类型不一致，属潜在改进项（已用测试锁定当前实际行为）。

---

## 2026-06-25：PT-TEST-4 engine.py 生命周期覆盖

测试基线：**1040 passed, 5 skipped**（0 failures，较上轮 +8）。

### PT-TEST-4 area 2：`engine.py` 生命周期测试
- 新增 `tests/e2e/test_e2e_engine_lifecycle.py`（7 个测试）：
  - 新引擎未封印/无解释器（惰性初始化）
  - `compile_string` 不封印（编译无 seal 副作用）
  - `execute` 封印注册表（单次执行语义）
  - **封印后重入 `execute` 抛 `PermissionError`**（NEXT_STEPS 指定的核心安全契约）
  - `compile_string` → `execute` 分步流程产出输出
  - `run_string` 单次运行后封印
  - 多引擎实例隔离（A 封印不阻塞 B）
- 此前该模块零覆盖（引擎的单次执行/封印契约无回归守护）

---

## 2026-06-25：PT-TEST-4 serialization round-trip 覆盖 + 反序列化 bug 修复

测试基线：**1032 passed, 5 skipped**（0 failures，较上轮 +11）。

### PT-TEST-4 area 1：`runtime/serialization/` round-trip 覆盖
- 新增 `tests/runtime/test_runtime_serialization.py`（11 个测试）：
  - 值保真 round-trip：primitive（int/float/str/bool）/ list / tuple / dict / 嵌套容器 / None / 空容器 / 混合多变量
  - 结构契约：版本化 payload、factory 必需性、恢复上下文为独立深拷贝
- 此前该模块**零覆盖**（消费者 HostService save/load_state、rt_scheduler isolation snapshot 无任何回归守护）

### 反序列化 bug 修复（round-trip 测试暴露）
- `RuntimeDeserializer._get_scope` 误用 `scope.define_variable(...)`（那是 `RuntimeContextImpl` 的方法），而 `ScopeImpl` 只有 `scope.define(...)` —— 协议混淆。
- **影响**：`deserialize_context` 对任何含变量的上下文都抛 `AttributeError`，即反序列化**从未真正可用**。零测试是它能潜伏的原因。
- 修复：`core/runtime/serialization/runtime_serializer.py` 改为 `scope.define(...)`（签名匹配）。

---

## 2026-06-25：Phase 3 多模态文件 I/O 完成 + 注册缺口修复

测试基线：**1021 passed, 5 skipped**（0 failures）。

### Phase 3 P0：file.read_audio/image/video
- `ibci_file` 插件扩展：`read_audio`/`read_image`/`read_video`（读字节 → `MediaStorage` → 经 `kernel_registry.get_class()` 装箱为 `IbAudio`/`IbImage`/`IbVideo`）
- `_spec.py` vtable 注册三函数（`return_type`: audio/image/video）；版本 2.3.0 → 2.4.0
- 4 个 e2e 测试（`tests/e2e/test_e2e_multimodal_file_io.py`）：MOCK 模式下 `audio x = file.read_audio(...)` + `@~ ... $x ... ~` 端到端跑通

### Phase 3 注册缺口修复（关键 bug，由 e2e 测试暴露）

> 此前 `COMPLETED.md` 声称"完整注册路径 + builtin_initializer 方法绑定"已完成，实际存在三处断链，导致 `audio`/`image`/`video` 类型从未真正进入类型系统。

1. **IbSpec 缺口**：axiom 已注册但对应 IbSpec 从未创建 → `metadata_registry.resolve("audio")=None` → `builtin_initializer` 静默跳过 IbClass 创建。
   - 修复：`core/kernel/spec/specs.py` 新增 `AUDIO_SPEC`/`IMAGE_SPEC`/`VIDEO_SPEC`（CLASS kind，parent Object）；`_runtime.py` 注册元组 + `__init__.py` 导出。
2. **`get_axiom` 调用错误**（`builtin_initializer.py` 媒体块）：直接把 IbSpec 传给 `AxiomRegistry.get_axiom`（期望字符串名）→ 永远返回 None → `__payload_prompt__` 从未注册。
   - 修复：改用 `SpecRegistry.get_axiom(spec)`（内部经 `spec.get_base_name()` 取名）。
3. **lambda 闭包晚绑定**（`builtin_initializer.py` 媒体块）：循环变量 `_media_type_name`/`_axiom_ref` 晚绑定到最后值 `"video"`，导致三种类型的 `__to_prompt__` 全显示 "video"、`__payload_prompt__` 全用 VideoAxiom。
   - 修复：用默认参数 `tn=_type_name` / `ax=_axiom_ref` 在定义时绑定。

### 测试
- 5 个 runtime 层测试（`tests/runtime/test_runtime_multimodal_dispatch.py`）：真实媒体对象 `_obj_to_payload` 分发 + base64 round-trip + `__to_prompt__` 类型名回归（守护缺口 3）

---

## 2026-06-24：全量分析体检 + 架构改善 + Phase 3 多模态基础

测试基线：**1011 passed, 5 skipped**（0 failures）。工作日志见 `docs/worklogs/`。

### P0 基线修复（commit 72f59e6）
- 修复 11 个测试失败（6 个编码 + 5 个 Windows 路径转义）
- 跨盘硬化：`safe_relpath()` + `pytest_configure` basetemp
- 修复 `interpreter.py:128` `symbol.spec` → `declared_type`（Critical）
- 修复 `kernel.py` 裸 `except:` → 正确错误传播（Critical）
- 修复 `llm_executor.py` `_pending_futures` 无锁并发竞争

### P1 架构健康修复（commits 55288e8~fa4c28d）
- 提取 `core/runtime/shared/` 打破 3 个 runtime 内循环
- 移动 `HostInterface` → `core/kernel/`（修复 compiler→runtime 反转）
- 移动 `fuzzy_json.py` → `core/base/support/`（恢复 kernel 永不导入 runtime）
- 拆分 `handlers.py`（2022 行 → 8 个子模块）
- `pytest.ini` + GitHub Actions CI 矩阵
- 层级元测试（31 个静态检查）+ 迁移 4 个违规文件
- MOCK 指令独立测试（20 个）
- 审计报告已解决标注 + Hub 文档锚点修复

### 6 个 God Module 拆分（commits 87e9ffb~9be0984）
- `type_checking_pass.py`（1490 行 → shell + 4 mixin）
- `primitives.py`（1350 行 → 8 子模块 package）
- `spec/registry.py`（1146 行 → 7 mixin package）
- `llm_executor.py`（1132 行 → 5 mixin package）
- `builtins.py`（1054 行 → 5 子模块 package）
- `objects/kernel.py`（1196 行 → 7 子模块 package）

### 代码质量改善（commits 78e5214~7fd085f）
- LLM-error axiom 工厂折叠（4 类 → 共享基类 + 配置子类）
- capability accessor 统一（6 getter → `_get_cap` 助手）
- `IbString.to_bool/cast_to` 越层访问修复（LLM-aware 逻辑迁移到 interpreter/VM 层）
- 裸 `except:` 全部收窄（core/ 中零裸 except:）
- `from e` traceback 链恢复（4 处）
- 关键日志添加（3 处：字段初始化/axiom 注册/模块导入）
- 死代码清理：`IbStatelessPlugin` 删除 + `__hash__` 修复 + 死分支删除

### Phase 3 多模态基础（commit 363fcd7）
- `AudioAxiom`/`ImageAxiom`/`VideoAxiom`（`has_payload_prompt_cap`）
- `MediaStorage`（Phase 3 纯内存，ADR-007）
- `IbAudio`/`IbImage`/`IbVideo`（`@register_ib_type`，IbValue 子类）
- 完整注册路径 + `builtin_initializer` 方法绑定
- 36 个新测试

### 路径测试 + bug 修复（commit 4cb4ef7）
- 85 个路径单元测试覆盖 IbPath/PathResolver/PathValidator
- 发现并修复 5 个 Windows 盘符处理 bug

### ADR 制度（commits d6890d2~a219878）
- `docs/decisions/` 目录 + ADR-007~012（6 份决策记录）
- 解除 Phase 3 全部 6 个阻塞条件

### 文档更新
- `IBCI_SYNTAX_REFERENCE.md` 新增 `@NAME~` 路由（§7.5）+ `__payload_prompt__`（§7.6）
- `AUDIT_REPORT_20260527.md` 已解决标注
- `SEMANTIC_COVERAGE_MATRIX.md` + `VM_SPEC.md` 刷新

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
