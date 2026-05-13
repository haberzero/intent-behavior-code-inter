# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-13（🎉 semantic_v2 已成为默认！V1→V2迁移Phase 1&2完成）

---

## 🎉 重大进展：V2已成为默认语义分析器！

**状态**: ✅ V2默认启用 → ✅ CompilationResult兼容性修复 → ✅ V1废弃标记完成 → ⏸️ 测试验证进行中

semantic_v2 **现在是 IBCI 的默认语义分析器**！所有新代码编译自动使用V2。V1已标记为DEPRECATED，仅作为紧急回退选项保留。

### 已完成的里程碑工作（2026-05-13）

**✅ Phase 1: 默认启用V2**
- ✅ 修改Engine默认 `use_semantic_v2=True`
- ✅ V2成为所有新代码的默认选择
- ✅ V1保留作为回退选项（`use_semantic_v2=False`）

**✅ Phase 2: 关键兼容性修复**
- ✅ 🔴 修复Critical Issue: CompilationResult结构不匹配
  - 重写adapter输出V1兼容的CompilationResult
  - 实现UID→Node映射（V2用UID，V1用object引用）
  - 添加side_table属性到adapter
- ✅ 标记V1为DEPRECATED
  - 在semantic_analyzer.py顶部添加废弃警告
  - 在scheduler.py标记V1为fallback only
  - 创建详细的V1→V2迁移指南

**详见**: `docs/V1_TO_V2_MIGRATION_GUIDE.md`
