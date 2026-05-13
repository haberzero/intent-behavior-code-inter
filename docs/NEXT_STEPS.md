# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-13（🎉 V1→V2迁移完成！V1已完全移除）

---

## 🎉 重大成就：V1→V2迁移完成！

**状态**: ✅ 所有5个阶段完成 → ✅ V1完全移除 → ✅ semantic_v2重命名为semantic

V1语义分析器已完全移除，V2（现在的semantic）是唯一的实现！

### 已完成的所有迁移工作（2026-05-13）

**✅ Phase 1-3: 架构改进（消除兼容层）**
- ✅ 将CompilationResult从object-based改为UID-based
- ✅ 重写engine_integration.py（删除~80行转换代码）
- ✅ 简化serializer.py（删除~30行重映射代码）
- ✅ 消除了荒谬的circular conversion: V2 UID → V1 Object → UID

**✅ Phase 4: V1完全移除**
- ✅ 删除6个V1文件（共3,202行）:
  - semantic_analyzer.py (107KB, 2,192行)
  - behavior_dependency_analyzer.py
  - collector.py, resolver.py
  - scope_manager.py, side_table.py
- ✅ 更新scheduler.py移除V1导入和条件逻辑
- ✅ 更新engine.py移除use_semantic_v2参数
- ✅ 废弃resolve_semantics()方法

**✅ Phase 5: 重命名和规范化**
- ✅ semantic_v2/ → semantic/
- ✅ SemanticV2Adapter → SemanticAdapter
- ✅ run_semantic_v2() → run_semantic_analysis()
- ✅ 更新所有import语句
- ✅ 更新测试目录结构

**详见**: `docs/V1_TO_V2_MIGRATION_GUIDE.md`
