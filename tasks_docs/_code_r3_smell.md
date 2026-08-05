# R3 code-odor 全面异味扫描 — 执行记录

> 临时任务文档（Phase 5 汇报后删除）。范围：core/、ibci_modules/、ibci_sdk/。
> 方法：4 个 general agent 独立扫描（Zone A/B/C/D）+ 主会话实证核验。
> 处置：真缺陷按"不删也不修"两档（根本修复/彻底删除）；设计限制文档化；纯良性保留。
> **状态：✅ 完成（2026-08-05）。全部批次落地 unsafe-vibe-dev（本地 commit，未 push）。
> 每批全量 pytest 零回归（1506 passed / 6 skipped，以实跑为准）。**

## 发现汇总（2026-08-05）

- **疑似真缺陷**：Zone A 6 / Zone B 11 / Zone C 5 / Zone D 4 = 26 项。
- **需讨论**：Zone A 13 / Zone B 15 / Zone C 10 / Zone D 8 = 46 项。
- 主会话实证核验后分类：约 17 项定案为死代码/恒真守卫（机械清除）、6 项定案为
  except 窄化/fail-fast、2 项为真缺陷重构（B1 复杂目标 dispatch、C2 behavior 序列化双轨）。

## 处置批次

### 批次 A — 死代码/不可达清除（低风险纯删除）
| # | 位置 | 内容 |
|---|------|------|
| A-1 | `core/compiler/lexer/lexer.py:61-64` | 删除无作用 try/except re-raise 包装 |
| A-2 | `core/kernel/axioms/intent.py:91-93` + `intent_context.py:91-94` | 删除重复不可达 `return False` |
| A-3 | `core/runtime/interpreter/llm_parsing_strategy.py:355-360` | 删除不可达 fallback（Default 策略恒 True） |
| A-4 | `core/runtime/observability/snapshot.py:35-45` | 删除恒假 scheduler 探测死分支（`_scheduler`/`_task_scheduler` 不存在） |
| A-5 | `ibci_modules/ibci_idbg/core.py:253` | 删除 `is_in_fallback` 键（LLMExceptFrame 无此字段 → AttributeError） |
| A-6 | `ibci_sdk/check.py:216-231` | 删除死常量 `is_stateful`/`is_stateless_marker`（dir() 误用恒假）与无谓 try |
| A-7 | `core/engine.py:384-391` | 删除 try/except（AxiomRegistry.register 不抛；remove fail-fast） |
| A-8 | `core/runtime/vm/handlers/llm_behavior.py:131-284` + `dispatch.py:116` | 删除不可达 `vm_handle_IbBehaviorInstance`（解析器不再生成） |

### 批次 B — 恒真 hasattr/getattr 守卫移除（机械）
| # | 位置 | 内容 |
|---|------|------|
| B-1 | `_statement_visitors.py:141/170/212/218` | 删除 `hasattr(self.registry, ...)` 恒真守卫 |
| B-2 | `_inference.py:252` | 删除 `hasattr(method_member, 'return_type')` |
| B-3 | `_members.py:85` | 删除 `hasattr(src_axiom, "get_diff_hint")`（全 axiom 均有） |
| B-4 | `llm_except_frame.py:138` | 删除 `hasattr(runtime_context, "get_active_intent_ibobj")` |
| B-5 | `interpreter.py:99-103` | 直调 `ci.get_active_intents()`，删除不可达防御分支 |
| B-6 | `_behavior.py:253/377` | `getattr(behavior,"capture_mode",None)` → 直访 |
| B-7 | `declarations.py:143-148` | 删除两层 hasattr（保留 spec None 检查） |
| B-8 | `native_module.py:76-78` | 删除冗余 hasattr（白名单绑定期已校验） |
| B-9 | `service.py:67/103` | 接口保证成员直访（fail-open 守卫转契约） |
| B-10 | `assignment.py:207-213` | `_parallel_enabled` 简化（直访 + 去死 try） |

### 批次 C — except 窄化 / fail-fast
| # | 位置 | 内容 |
|---|------|------|
| C-1 | `module_manager.py:138-153` | try 仅包 `getattr` 一行，`define_variable` 移出 |
| C-2 | `events.py:109` | 宽 `except Exception` → `CommClosedError` |
| C-3 | `iruntime/core.py:151-154/167-170` | 删除静默 try/except（与 comm.py fail-fast 惯例一致） |
| C-4 | `ibci_net/core.py` 9 处 | `except Exception` → `requests.RequestException`（保留 RuntimeError 包装） |
| C-5 | `type_def.py:116` | `except Exception` → `ParseControlFlowError` |
| C-6 | `coordinator.py:339-345` | 删除死 try/except（add_done_callback 不抛） |
| C-7 | `scheduler.py:275-277` | `except Exception` → `CompilerError`（lexer bug fail-fast） |

### 批次 D — 真缺陷重构
| # | 位置 | 内容 |
|---|------|------|
| D-1 | `assignment.py:97-108` | 复杂目标不 dispatch（把 future_assignable 判断前移），删除兜底双通道 |
| D-2 | `runtime_serializer.py:302-319/662-666` | behavior 序列化 round-trip 修复：captured_intents 存 IbIntentContext uid + 补 capture_mode/params_uids/closure |

## 保留+文档化（设计决策/需讨论，非真缺陷）
- Axiom 家族分裂（IntentAxiom/IntentContextAxiom 不继承 BaseAxiom）：设计观察，暂不重构。
- **permissive any 语义（用户重审，2026-08-05）**：按类型系统实际可达面重审——LAZY→any 分支
  实证死代码（无 LAZY 创建点）→ **已删除**；resolve_call_return 的 any 兜底三分：动态类型语义
  （`any`/裸赋值/容器读，KNOWN_LIMITS §七）保留、auto 推断兜底保留、**未标注可调用静默变 any
  属掩盖缺口**（建议强制标注 → SEM 错误，待用户拍板语言变更）。
- **llm_except best-effort**：`_values_equal` 已收窄（显式保守 False + 降级链路注释）；
  快照/恢复协议兜底为文档化设计保留。
- **ibci_ai 宽 except**（用户裁定修复）：已收窄至 `_PROVIDER_ERRORS`
  （openai.OpenAIError + RuntimeError + ValueError），内部缺陷 fail-fast 传播。
- **behavior closure 序列化**（用户裁定为明确设计缺陷）：记录为未来改进 → PT-ARCH-31。
- `deep_clone.py:109` `type() is`：裸 IbObject 精确判别，语义正确。
- `media.py:46` hasattr(receive) 探测：media Phase 4 已封存，零改动。

## 验证
每批改完：全量 `python -m pytest tests/` 零回归 + commit（仅本地，禁 push）。
- 批次 A commit f5d3f94 / 批次 B cb2edbd / 批次 C c73914d / 批次 D a1ffbbe /
  残留清理 bffe195 —— 每批均 1506 passed / 6 skipped 零回归。
- D-2 behavior 序列化 round-trip 已用真实 engine 验证：captured_intents
  None/uid 双向还原 + capture_mode/params_uids 保留 + 二次序列化不再 TypeError。

## 批次 D-2 补充决策
- **closure 未序列化**：与 fn_callable 既有行为一致（lambda 闭包 cell 为活引用，
  恢复后无法重链到新作用域）；已文档化为已知限制，非本批范围。
