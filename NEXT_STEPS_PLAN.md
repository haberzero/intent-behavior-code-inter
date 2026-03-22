# IBC-Inter 下一步工作计划

> 本文档记录 IBC-Inter 项目的已完成工作和后续计划。
>
> **生成日期**：2026-03-21
> **版本**：V4.0
> **状态**：Phase 0-5 全部完成，待单元测试验证

---

## 一、已完成工作汇总

### Phase 0：架构修复

| 任务 | 状态 | 说明 |
|------|------|------|
| A.0.1 HostInterface 位置 | ✅ | 维持在 runtime/host/ |
| A.0.2 MetadataRegistry 双轨制 | ✅ | discover_all() 正确传递 registry.get_metadata_registry() |
| A.0.3 HOST 插件 spec 命名 | ✅ | spec.py → _spec.py，run → run_isolated |
| A.0.4 builtin_initializer 清理 | ✅ | 移除孤立的 host_* 函数 |

### Phase 1：公理体系健壮性

| 任务 | 状态 | 说明 |
|------|------|------|
| 3.0 ListMetadata/DictMetadata fallback | ✅ | 移除妥协性 fallback |
| 3.1 StrAxiom 修复 | ✅ | resolve_item/get_element_type 正确实现 |
| 3.2 AxiomHydrator 修复 | ✅ | 移除静默返回 |
| 3.3 ExpressionAnalyzer 修复 | ✅ | 移除静默 fallback |

### Phase 2：风险消除

| 任务 | 状态 | 说明 |
|------|------|------|
| inherit_intents 默认值 | ✅ | 修改为 False |

### Phase 3：DynamicHost 最小实现

| 任务 | 状态 | 说明 |
|------|------|------|
| 3.1 基本内置类型返回值机制 | ✅ | TypeAxiom 添加 can_return_from_isolated() |
| 3.2 DynamicHost 异常处理 | ✅ | IsolatedRunResult 结构化返回 |
| 3.3 IssueTracker 序列化 | ✅ | to_dict() 方法 |

### Phase 4：核心语法完善

| 任务 | 状态 | 说明 |
|------|------|------|
| 4.1 HOST 插件 spec 更新 | ✅ | _spec.py + IES 2.2 协议 |
| 4.2 str 方法扩展 | ✅ | upper/lower/strip/split/is_empty |

### Phase 5：可选扩展

| 任务 | 状态 | 说明 |
|------|------|------|
| 5.1 AI 组件异步并发 | ✅ | 最小可行层 llm_tasks.py |
| 5.2 子解释器快照机制 | ✅ | SnapshotOptions 配置 |

### Phase 6：IES 2.2 插件系统重构

| 任务 | 状态 | 说明 |
|------|------|------|
| 6.1 AutoDiscoveryService | ✅ | 自动插件发现 |
| 6.2 固定命名方法协议 | ✅ | __ibcext_metadata__ / __ibcext_vtable__ |
| 6.3 向后兼容适配器 | ❌ | **已删除**，不需要兼容旧版 |
| 6.4 内置插件迁移 | ✅ | HOST/AI/IDBG 实现 IES 2.2 |
| 6.5 元数据序列化 | ✅ | to_dict() + export_metadata() |

### 额外完成工作

| 任务 | 状态 | 说明 |
|------|------|------|
| 装饰器体系删除 | ✅ | 移除 @method/@module 装饰器 |
| IES 2.2 vtable 绑定 | ✅ | _ibcext_vtable_func 机制 |
| DynamicHost IES 2.2 | ✅ | 迁移到模块级 vtable |
| 兼容性回退清理 | ✅ | 移除所有 fallback 代码 |
| legacy_plugin 删除 | ✅ | 删除旧插件目录 |

---

## 二、IES 2.2 架构

### 插件分类

| 类型 | 示例 | 核心绑定 | 说明 |
|------|------|---------|------|
| **零侵入插件** | math, json, time, net, schema, file*, sys* | ❌ | 不继承任何核心类 |
| **核心级插件** | host, ai, idbg | ✅ | 继承 IbPlugin/ILLMProvider |

*file/sys 在最小版本绕过 permission_manager

### IES 2.2 协议

```
_spec.py (模块级)
├── __ibcext_metadata__() → 返回元数据
└── __ibcext_vtable__() → 返回方法映射表

↓ loader 自动绑定

implementation (类实例)
└── _ibcext_vtable_func → 指向模块级函数
```

### 禁止事项

- ❌ 禁止在插件中使用 @method/@module 装饰器
- ❌ 禁止在 _spec.py 中 import SpecBuilder
- ❌ 禁止保留任何兼容性回退代码
- ❌ 禁止使用 fallback 逻辑

---

## 三、待执行工作

### 单元测试收敛

| 任务 | 优先级 | 说明 |
|------|--------|------|
| Phase 0-6 回归测试 | 高 | 验证所有修改未破坏现有功能 |

---

## 四、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| V4.0 | 2026-03-22 | Phase 0-6 全部完成，IES 2.2 架构确立 |
| V3.2 | 2026-03-21 | 初始版本 |
