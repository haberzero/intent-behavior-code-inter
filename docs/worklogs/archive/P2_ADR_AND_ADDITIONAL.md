# 工作日志：P2 ADR 制度 + 额外改善（BUG #A 回归 + 死代码清理 + snapshot 修复）

> **里程碑**：P2-A/B 完成 + 额外改善项
> **日期**：2026-06-24
> **分支**：unsafe-vibe-dev
> **基线**：889 passed, 5 skipped, 0 failed
>
> **⚠️ 归档状态（2026-07-17）**：本文档记录 2026-06-24 的工作日志。其中 ADR-009 提议的 `_call_llm_multimodal` 分叉路径**已被 ADR-013 否决**，当前 IBCI 采用单一 LLM 调用入口 + 协议驱动分发。ADR-007 的二阶段 snapshot 划分**已被 ADR-014 / ADR-016 推翻**（所有 media 一律 disk-backed handle）。本文档仅作历史追溯，当前设计请以 `docs/decisions/` 中的最新 ADR 为准。

---

## 一、完成项

### P2-A 建立 `docs/decisions/` ADR 目录 ✅
- 创建 ADR 模板和索引（README.md）

### P2-B 写 5 份紧急 ADR ✅
- ADR-007: 多模态 snapshot 策略（DEC-5/6 裁决：Phase 3 用 deep-copy，修复 isinstance 分发）
- ADR-008: register_model API 形态（D4 裁决：扩展 kwargs，保持 4 位置参数向后兼容）
- ADR-009: _call_llm_raw 引入（D6/DEC-4 裁决：Phase 3 不引入，Phase 4 加 _call_llm_multimodal）
- ADR-010: per-model 能力探测（R5 裁决：endpoint 字段决定是否注入 reasoning prompt）
- ADR-011: runtime/shared/ 叶子包（记录 P1-A 的循环打破决策）

### PT-TEST-5 BUG #A if/while 回归测试 ✅
- 3 个测试验证 if/while 条件不确定时抛出错误（正交性验证）

### PT-ARCH-6 死代码清理 ✅
- 删除 IbStatelessPlugin（零使用死抽象）
- 删除 _check_type 死代码分支（`if val_spec: pass`）
- 修复 IbInteger.__hash__ 隐式 None
- 收窄 SymbolViewImpl.has 裸 except

### ADR-007 代码实施：snapshot 分发 isinstance 修复 ✅
- `llm_except_frame.py:199`: `type(val) is IbObject` → `isinstance(val, IbObject) + ib_class 检查`
- 解除 Phase 3 多模态 snapshot 阻塞（IbAudio 等子类不再被静默跳过）

### 文档清理 ✅
- SEMANTIC_COVERAGE_MATRIX.md 刷新（612→889 测试计数）
- VM_SPEC.md 幽灵引用修复（PENDING_TASKS §七 PT-5.1）
- AUDIT_REPORT_20260527.md 已解决标注
- TEST_PHILOSOPHY.md 测试计数更新
- ARCH_DETAILS.md §1.2 BUG #A 后语义更新
- FUNC_DESIGN_NOTES.md 旧编号修复

---

## 二、Phase 3 阻塞解除状态

| 原阻塞 | 状态 | 解决方式 |
|--------|------|---------|
| DEC-5 vs DEC-6 矛盾 | ✅ 已解决 | ADR-007: Phase 3 用 deep-copy |
| DEC-5 `type() is` 分发 bug | ✅ 已解决 | 代码修复：isinstance + ib_class |
| D4 register_model 示例不可编译 | ✅ 决策已定 | ADR-008: 保持 4 位置参数 + kwargs |
| D6 vs DEC-4 对立 | ✅ 已解决 | ADR-009: Phase 3 不引入 _call_llm_raw |
| R5 非 chat 端点注入 | ✅ 决策已定 | ADR-010: endpoint 字段控制 |
| DEC-1 关键字 vs 类名 | ⚠️ **待决策** | 需用户决断（见汇报） |

---

## 三、搁置项汇总

### 需要用户决策
1. **DEC-1**：audio/image/video 作为关键字还是普通类名？
2. **PT-ARCH-4 优先级**：是否继续拆分剩余 6 个 god modules？

### 技术性搁置（可自主推进但工作量大/风险高）
3. PT-ARCH-4：拆分 6 个 god modules（每个 1000-1500 行）
4. PT-ARCH-5：折叠重复分支（4 LLM-error axioms + 8 accessors + 5 CPS pairs）
5. PT-ARCH-7：修复剩余 ~15 处静默吞异常
6. PT-DOC-3：IBCI_SYNTAX_REFERENCE.md 补充 @NAME~ + __payload_prompt__
7. PT-TEST-4：填补覆盖缺口（serialization/host/path/engine）
8. PT-TEST-9：修复 IbString.to_bool 越层访问
