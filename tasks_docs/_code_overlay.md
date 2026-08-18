# 临时任务文档：P2-② 临时覆层机制（决策 2）

> **性质**：临时任务控制文档（code-workflow §五）。落地后删除（git 承载）。
> **承接**：`NEXT_STEPS.md` 候选 #1 P2-②；设计权威 `_five_foundation_P1_design.md` §四
> + `_five_foundation_redesign.md` §五 决策 2。

## 〇、目标与范围（本单元）

在 `exp/protocol-vtable` 分支落地**临时覆层机制**（决策 2）完整闭环，全量 pytest 零回归：

1. **覆层声明**：`impl overlay for <内置类型>:` 变体（`overlay` 关键字在 protocol 槽位，
   标记为覆层声明）→ AST/语义/水化登记影子条目（`ProtocolSlot.overlay`）。
2. **作用域化启用**：`with overlay(<类型>.<协议方法>):` 语句（P1 推荐作用域块形态）——
   VM 块执行窗口内启用覆层（save/restore，天然作用域化），块外默认不参与分派。
3. **分派接线**：`ProtocolSlot.active_handler` 已按 `overlay_enabled` 优先覆层（前增量已就绪），
   本单元接线启用 flag。
4. **告警**：覆层存在未启用提示（模块级语义告警）+ 启用生效行为告警（诊断）。
5. 判别性测试 + commit。

**不做**：D2 to_prompt 激活、D1 双注册表收敛（归 P5）；llm/llmend 删除（P4）。

## 一、设计定稿

### 1. 声明语法（P1 §四.2 形态草案，细化）

```text
impl overlay for int:
    func __to_prompt__(self) -> str: ...
```

- `overlay` 为**新关键字**（TokenType.OVERLAY），占用 impl 的 protocol 槽位 → 覆层声明。
- 与普通 `impl <P> for <T>` 区别：普通 impl 立即生效（注册 vtable + spec.members +
  implements）；覆层**仅登记影子条目**（`protocol_vtable[msg].overlay`），默认不参与分派。
- 方法名须为协议消息（`spec_reg.dunder_names()` 方法集），否则 SEM 错误（覆层只对协议
  消息有意义）。

### 2. 作用域启用（P1 §四.3 推荐形态：作用域块）

```text
with overlay(int.__to_prompt__):
    ...  # 块内 int.__to_prompt__ 分派优先覆层
```

- `with` 为**新关键字**（TokenType.WITH）。
- 目标 = 点分引用 `<类型>.<协议方法>`，语义期解析为 (class_name, method_name)，
  存于 AST 节点（声明式目标，不求值为表达式）。
- 语义校验：目标类型存在且为 KERNEL_NATIVE 具体值类型；该类型已声明对应覆层方法。
- VM 块处理器：save 原 `overlay_enabled` → 设 True → try/finally 执行 body → 恢复。
  （作用域 = 块执行窗口；嵌套 save/restore 正确。）

### 3. 数据/运行时

- `IbImplDef.is_overlay: bool = False`（新字段；serializer 经 `vars(node)` 自动携带）。
- 新 `IbWithOverlayStmt(target_type, target_method, body)`。
- 水化（`_hydrate_user_classes`）：overlay impl → `target.protocol_slot(m).overlay = IbUserFunction`
  （**不** register_method / 不进 members / 不 append implements）。
- `ProtocolSlot.active_handler`：`overlay_enabled and overlay` → overlay，否则 native。

### 4. 告警

- **存在未启用**：模块内声明了覆层但从未被 `with overlay` 引用 → 语义告警（SEM 码）。
- **启用生效**：`with overlay` 块进入时发射行为诊断（KDIAG 码，观测用，不阻断）。

## 二、文件清单

- `core/compiler/common/tokens.py`：+WITH / +OVERLAY
- `core/compiler/lexer/core_scanner.py`：关键字映射 + `overlay`/`with`
- `core/kernel/ast.py`：`IbImplDef.is_overlay` + `IbWithOverlayStmt`
- `core/compiler/parser/components/declaration.py`：impl_declaration overlay 分支
- `core/compiler/parser/components/statement.py`：with_overlay_statement + dispatch
- `core/compiler/semantic/passes/symbol_collection_pass.py`：overlay 收集（跳过 members/
  implements/原生冲突，仍进 owned_scope 供体检查）
- `core/compiler/semantic/passes/_declaration_visitors.py`：overlay 校验 + 登记 + 未启用告警
- `core/compiler/semantic/passes/_statement_visitors.py`：with-overlay 校验 + body
- `core/runtime/interpreter/interpreter.py`：overlay 水化分支
- `core/runtime/vm/handlers/control_flow.py`：vm_handle_IbWithOverlay
- `core/runtime/vm/handlers/dispatch.py`：注册 handler
- `core/base/diagnostics/codes.py`：+行为诊断码
- `tests/e2e/test_overlay_mechanism.py`：判别性测试

## 三、验证门

- 全量 `python -m pytest tests/` 零回归（当前 2985）。
- 判别性：覆层声明不参与默认分派；`with overlay` 块内生效/块外恢复；嵌套块；非协议方法
  声明报错；目标未声明覆层报错；未启用告警。
- 本地 commit（禁 push）。

## 四、决策记录（自主，工作模式定论 + design-philosophy）

- **`overlay`/`with` 新关键字**：覆层是"临时、作用域化、默认不生效"的新语义，与普通 impl
  （立即生效）本质不同，须语法区分——不是 compat shim，是真设计（工作模式定论 §1）。
- **影子条目默认不参与分派**：决策 2 核心；`ProtocolSlot.overlay_enabled` 默认 False，
  已由前增量支撑。
- **作用域块形态（with overlay）**：P1 推荐；save/restore 天然作用域化、不泄漏后续代码段。
- **声明式目标（`<类型>.<协议方法>`）而非表达式**：覆层目标是编译期声明引用，不求值为
  运行期值（避免 `int.__to_prompt__` 触发 getattr 分派的反身性问题）。
- **overlay 方法不进 spec.members / implements**：覆层不声明"类型满足协议"（那会改变
  编译期 satisfies_protocol 判定），仅运行时改写分派——职责分离（设计语言统一）。
