# IBC-Inter 下一步工作计划

> 本文档是 IBC-Inter 项目的下一步工作计划，包含详细的现状分析、任务分解和实施细则。
> 优先级高于 PENDING_TASKS.md，可独立使用。
>
> **生成日期**：2026-03-21
> **版本**：V2.0

---

## 一、现状分析

### 1.1 代码架构当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| **base 层** | ✅ 健康 (92%) | 原子概念完整 |
| **kernel 层** | ✅ 基本健康 (88%) | 符号/类型/公理基本完整 |
| **compiler 层** | ✅ 健康 (90%) | 词法/语法/语义分析完整 |
| **runtime 层** | ⚠️ 有缺陷 (85%) | 解释器基本可用，但隔离机制有缺陷 |
| **插件系统** | ⚠️ 部分 (60%) | AI/IDBG基本完整，HOST需更新 |
| **综合** | ✅ 基本可用 | 核心架构健康，可推进最小DynamicHost |

### 1.2 已确认的缺陷（已被搁置）

| 缺陷 | 严重程度 | 搁置原因 | 触发条件 |
|------|----------|----------|----------|
| **Intent Stack 引用赋值** | 🔴 高 | 当前阶段不继承意图栈 | `inherit_intents=True` |
| **ImmutableArtifact 缺少 `__deepcopy__`** | 🟡 中 | 当前深拷贝行为可接受 | 使用深拷贝时 |
| **AxiomRegistry 共享引用** | 🟡 中 | 子解释器不修改公理 | 子环境注册新公理 |
| **DynamicHost 吞掉异常** | 🟡 中 | 暂时不需要诊断信息 | 子解释器抛出异常 |
| **run_isolated 返回 bool** | 🟡 中 | 当前只需知道成功/失败 | 需要返回实际值 |

### 1.3 已明确排除的功能

| 排除项 | 理由 |
|--------|------|
| generate_and_run | 动态生成IBCI由显式IBCI生成器进行 |
| GDB 式断点 | DynamicHost 断点是现场保存/恢复/回溯 |
| 进程级隔离 | 实例级隔离已足够 |
| hot_reload_pools | 违反解释器不修改代码原则 |

### 1.4 计划制定原则

1. **消除风险**：立即修复与设计决策不一致的问题
2. **最小目标**：DynamicHost 先实现最小可用功能
3. **渐进完善**：先确保核心可用，再完善周边功能
4. **架构对齐**：每个步骤都要与 ARCHITECTURE_PRINCIPLES.md 对齐

---

## 二、立即执行任务（Phase 1）

### 🔴 2.1 inherit_intents 默认值修改

**任务**：修改 `IsolationPolicy` 中 `inherit_intents` 的默认值为 `False`

**当前状态**：
- 架构决策：不继承任何意图栈
- 代码现状：`inherit_intents=True`（不一致）
- 问题：与设计决策不一致，可能触发 Intent Stack 引用赋值问题

**文件**：`core/runtime/host/isolation_policy.py`

**修改内容**：
```python
# 第19行
inherit_intents: bool = False  # 从 True 改为 False
```

**实施细则**：
1. 找到 `isolation_policy.py` 第19行
2. 将 `inherit_intents: bool = True` 改为 `inherit_intents: bool = False`
3. 确认以下工厂方法显式设置（可选，保持现状即可）：
   - `IsolationPolicy.full()` → `inherit_intents=True`
   - `IsolationPolicy.partial()` → `inherit_intents=True`
   - `IsolationPolicy.plugin_only()` → `inherit_intents=False`
   - `IsolationPolicy.minimal()` → `inherit_intents=False`

**验证清单**：
- [ ] `inherit_intents` 默认值为 `False`
- [ ] 运行测试确认子解释器不继承意图栈

---

## 三、DynamicHost 最小实现（Phase 2）

### 🟡 3.1 基本内置类型返回值机制

**任务**：实现子解释器返回基本内置类型（int/str/bool/float/none），禁止容器和插件类

**当前状态**：
- `run_isolated()` 返回固定 `bool`
- 子解释器 `run()` 返回 `bool`
- 无法传递实际计算结果

**目标**：
- `run_isolated()` 返回 IbObject
- 只允许基本内置类型返回
- 容器类型（list/dict）禁止返回
- 插件类禁止返回

**文件列表**：
| 文件 | 操作 | 修改内容 |
|------|------|----------|
| `core/kernel/axioms/protocols.py` | 修改 | 添加 `can_return_from_isolated()` 到 TypeAxiom Protocol |
| `core/kernel/axioms/primitives.py` | 修改 | 在 BaseAxiom 添加默认实现，在 IntAxiom/StrAxiom/BoolAxiom/FloatAxiom 覆盖返回 True |
| `core/runtime/interpreter/interpreter.py` | 修改 | `run()` 返回类型从 `bool` 改为 `IbObject` |
| `core/runtime/host/service.py` | 修改 | 添加 `_validate_return_value()` 类型检查 |
| `core/runtime/host/dynamic_host.py` | 修改 | 返回类型改为 `IbObject` |

**实施细则**：

**Step 1**：修改 `core/kernel/axioms/protocols.py`
```python
class TypeAxiom(Protocol):
    # ... 现有内容 ...

    def can_return_from_isolated(self) -> bool:
        """
        [IES 2.1 Security] 判断该类型的实例是否允许从隔离子环境返回。
        """
        ...
```

**Step 2**：修改 `core/kernel/axioms/primitives.py`
```python
class BaseAxiom(TypeAxiom):
    # ... 现有内容 ...

    def can_return_from_isolated(self) -> bool:
        return False  # 默认不允许

class IntAxiom(BaseAxiom, ...):
    def can_return_from_isolated(self) -> bool:
        return True

class StrAxiom(BaseAxiom, ...):
    def can_return_from_isolated(self) -> bool:
        return True

class BoolAxiom(BaseAxiom, ...):
    def can_return_from_isolated(self) -> bool:
        return True

# ListAxiom/DictAxiom 保持 False（继承自 BaseAxiom）
```

**Step 3**：修改 `core/runtime/interpreter/interpreter.py` 的 `run()` 方法
```python
def run(self) -> IbObject:  # 从 bool 改为 IbObject
    try:
        if not self.entry_module:
            return self.registry.get_none()
        module_data = self.artifact_dict.get("modules", {}).get(self.entry_module)
        if not module_data:
            return self.registry.get_none()
        result = self.execute_module(module_data["root_node_uid"], module_name=self.entry_module)
        return result  # 返回实际 IbObject
    except Exception as e:
        raise e
```

**Step 4**：在 `core/runtime/host/service.py` 添加验证方法
```python
def _validate_return_value(self, value: IbObject) -> IbObject:
    """验证返回值是否允许从隔离环境返回"""
    if value is None:
        return self.registry.get_none()

    desc = value.descriptor
    axiom = getattr(desc, '_axiom', None)

    if axiom and hasattr(axiom, 'can_return_from_isolated'):
        if axiom.can_return_from_isolated():
            return value

    # Fallback：白名单判断
    allowed = {"int", "str", "bool", "float", "None"}
    type_name = desc.get_base_axiom_name() if hasattr(desc, 'get_base_axiom_name') else desc.name
    if type_name in allowed:
        return value

    return self.registry.get_none()  # 类型不允许返回，降级为 None
```

**验证清单**：
- [ ] `IntAxiom.can_return_from_isolated()` 返回 `True`
- [ ] `StrAxiom.can_return_from_isolated()` 返回 `True`
- [ ] `ListAxiom.can_return_from_isolated()` 返回 `False`
- [ ] `run()` 返回 IbObject 而非 bool
- [ ] 容器类型返回时降级为 None

---

### 🟡 3.2 DynamicHost 异常传播修复

**任务**：修复 DynamicHost 吞掉异常的问题，让异常正确传播或返回结构化信息

**当前状态**：
```python
# dynamic_host.py:54-58
except Exception:
    return False  # 错误信息完全丢失
```

**目标**：
- 异常不被吞掉
- 错误信息可传递
- 与现有调用代码兼容

**文件列表**：
| 文件 | 操作 | 修改内容 |
|------|------|----------|
| `core/runtime/host/dynamic_host.py` | 修改 | 返回结构化结果或正确传播异常 |
| `core/runtime/host/service.py` | 修改 | 收集子解释器诊断信息 |

**实施细则**：

**方案 A（推荐）**：返回结构化结果
```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class IsolatedRunResult:
    success: bool
    diagnostics: List['Diagnostic']
    exception: Optional[Exception]
    return_value: Optional['IbObject']

@method("run_isolated")
def run_isolated(self, path: str, policy: Dict[str, Any]) -> IsolatedRunResult:
    sc = self._capabilities.service_context
    if sc and sc.host_service:
        try:
            isolation_policy = IsolationPolicy.from_dict(policy) if isinstance(policy, dict) else policy
            result = sc.host_service.run_isolated(path, isolation_policy.to_dict())
            return IsolatedRunResult(
                success=True,
                diagnostics=result.get("diagnostics", []),
                exception=None,
                return_value=result.get("return_value")
            )
        except Exception as e:
            diagnostics = []
            if sc.host_service and hasattr(sc.host_service, '_last_diagnostics'):
                diagnostics = sc.host_service._last_diagnostics
            return IsolatedRunResult(
                success=False,
                diagnostics=diagnostics,
                exception=e,
                return_value=None
            )
    return IsolatedRunResult(success=False, diagnostics=[], exception=None, return_value=None)
```

**验证清单**：
- [ ] DynamicHost 不再返回固定 False
- [ ] 异常信息可访问
- [ ] 诊断信息可访问

---

### 🟡 3.3 IssueTracker 序列化支持

**任务**：为 IssueTracker 添加 `to_dict()` / `from_dict()` 方法，支持诊断信息序列化

**当前状态**：
- IssueTracker 只有内存收集能力
- 无序列化方法
- 子解释器的诊断信息无法传递到主解释器

**目标**：
- 诊断信息可序列化为 dict
- 可反序列化恢复
- 为未来快照机制提供基础

**文件**：`core/compiler/diagnostics/issue_tracker.py`

**实施细则**：
```python
def to_dict(self) -> Dict[str, Any]:
    """将诊断信息序列化为字典"""
    return {
        "file_path": self.file_path,
        "diagnostics": [
            {
                "severity": d.severity.name,
                "code": d.code,
                "message": d.message,
                "location": {
                    "file_path": d.location.file_path if d.location else None,
                    "line": d.location.line if d.location else None,
                    "column": d.location.column if d.location else None,
                } if d.location else None,
                "hint": d.hint,
            }
            for d in self._diagnostics
        ],
        "error_count": self._error_count,
        "warning_count": self.warning_count,
    }

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> 'IssueTracker':
    """从字典反序列化"""
    tracker = cls(file_path=data.get("file_path", "<unknown>"))
    for d in data.get("diagnostics", []):
        # ... 重建 Diagnostic 对象
    return tracker
```

**验证清单**：
- [ ] IssueTracker 可序列化为 dict
- [ ] 可从 dict 反序列化
- [ ] 序列化内容包含所有诊断信息

---

## 四、核心语法完善（Phase 3）

### 🟡 4.1 HOST 插件 spec 更新

**任务**：更新 HOST 插件的 spec.py 使其与实现一致

**当前状态**：
- spec 定义 `run`，实现使用 `run_isolated`
- 方法名不一致

**文件**：
| 文件 | 操作 | 内容 |
|------|------|------|
| `ibc_modules/host/spec.py` | 修改 | 将 `run` 改为 `run_isolated` |
| `ibc_modules/host/__init__.py` | 不变 | 实现已是 `run_isolated` |

**实施细则**：
```python
# ibc_modules/host/spec.py
spec = (
    SpecBuilder("host")
    .func("save_state", params=["str"])
    .func("load_state", params=["str"])
    .func("run_isolated", params=["str", "dict"], returns="bool")  # 改名
    .func("get_source", returns="str")
    .build())
```

**验证清单**：
- [ ] spec.py 与实现一致
- [ ] 方法名正确

---

### 🟡 4.2 str/list/dict 方法扩展

**任务**：在公理体系中扩展 str 常用方法

**当前状态**：
- StrAxiom 只有 `len/to_bool/cast_to`
- 缺少 `upper/lower/split/join` 等常用方法

**文件**：
| 文件 | 操作 | 内容 |
|------|------|------|
| `core/kernel/axioms/primitives.py` | 修改 | StrAxiom.get_methods() 添加方法 |
| `core/runtime/objects/builtins.py` | 修改 | IbString 类添加对应 Python 方法 |

**实施细则**：

**Step 1**：修改 `core/kernel/axioms/primitives.py` 的 `StrAxiom.get_methods()`
```python
def get_methods(self) -> Dict[str, FunctionMetadata]:
    return {
        # 现有方法
        "len": FunctionMetadata(name="len", param_types=[], return_type=INT_DESCRIPTOR),
        "to_bool": FunctionMetadata(name="to_bool", param_types=[], return_type=BOOL_DESCRIPTOR),
        "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
        # 新增方法
        "upper": FunctionMetadata(name="upper", param_types=[], return_type=STR_DESCRIPTOR),
        "lower": FunctionMetadata(name="lower", param_types=[], return_type=STR_DESCRIPTOR),
        "strip": FunctionMetadata(name="strip", param_types=[], return_type=STR_DESCRIPTOR),
        "lstrip": FunctionMetadata(name="lstrip", param_types=[], return_type=STR_DESCRIPTOR),
        "rstrip": FunctionMetadata(name="rstrip", param_types=[], return_type=STR_DESCRIPTOR),
        "split": FunctionMetadata(name="split", param_types=[], return_type=ListMetadata(element_type=STR_DESCRIPTOR)),
        "join": FunctionMetadata(name="join", param_types=[ListMetadata(element_type=STR_DESCRIPTOR)], return_type=STR_DESCRIPTOR),
        "replace": FunctionMetadata(name="replace", param_types=[STR_DESCRIPTOR, STR_DESCRIPTOR], return_type=STR_DESCRIPTOR),
        "startswith": FunctionMetadata(name="startswith", param_types=[STR_DESCRIPTOR], return_type=BOOL_DESCRIPTOR),
        "endswith": FunctionMetadata(name="endswith", param_types=[STR_DESCRIPTOR], return_type=BOOL_DESCRIPTOR),
        "is_empty": FunctionMetadata(name="is_empty", param_types=[], return_type=BOOL_DESCRIPTOR),
    }
```

**Step 2**：修改 `core/runtime/objects/builtins.py` 的 `IbString` 类
```python
@register_ib_type("str")
class IbString(IbObject):
    # ... existing code ...

    def upper(self) -> IbString:
        return self.ib_class.registry.box(self.value.upper())

    def lower(self) -> IbString:
        return self.ib_class.registry.box(self.value.lower())

    def strip(self) -> IbString:
        return self.ib_class.registry.box(self.value.strip())

    # ... etc
```

**验证清单**：
- [ ] `"hello".upper()` 返回 `"HELLO"`
- [ ] `"  hello  ".strip()` 返回 `"hello"`
- [ ] `"a,b".split(",")` 返回 `["a", "b"]`

---

## 五、可选扩展（Phase 4）

> 以下任务为可选扩展，按需执行

### 🟢 5.1 AI 组件异步并发

**任务**：实现基本的 LLM 非阻塞调用机制

**当前状态**：完全同步阻塞

**目标**：
- `call_async` 提交任务立即返回
- `sync` 语句等待所有异步任务完成
- 支持非依赖赋值并行执行

**新增文件**：`core/runtime/async/llm_tasks.py`

**修改文件**：
- `ibc_modules/ai/core.py`
- `ibc_modules/ai/_spec.py`
- `core/runtime/interpreter/llm_executor.py`
- `core/runtime/interpreter/handlers/expr_handler.py`
- `core/kernel/ast.py`
- `core/runtime/interpreter/interpreter.py`
- `core/runtime/objects/builtins.py`
- `core/runtime/factory.py`

---

### 🟢 5.2 子解释器快照机制

**任务**：实现子解释器运行信息序列化保存到硬盘

**当前状态**：无快照机制

**目标**：
- 通过 policy 参数控制快照内容
- 保存完整运行栈/诊断/变量到硬盘
- 临时调试机制，未来可禁用

**新增文件**：`core/runtime/serialization/snapshot_options.py`

**修改文件**：
- `core/runtime/serialization/runtime_serializer.py`
- `core/runtime/host/service.py`
- `core/runtime/host/dynamic_host.py`

---

## 六、执行顺序总览

```
Phase 1: 立即执行（消除风险）
└── 2.1 inherit_intents 默认值修改

Phase 2: DynamicHost 最小实现
├── 3.1 基本内置类型返回值机制
├── 3.2 DynamicHost 异常传播修复
└── 3.3 IssueTracker 序列化支持

Phase 3: 完善性工作
├── 4.1 HOST 插件 spec 更新
└── 4.2 str 方法扩展

Phase 4: 可选扩展
├── 5.1 AI 组件异步并发
└── 5.2 子解释器快照机制
```

---

## 七、验证清单

完成 Phase 1-3 后应验证：

- [ ] `inherit_intents` 默认值为 `False`
- [ ] `run_isolated()` 可返回 IbObject（int/str/bool/float/none）
- [ ] `run_isolated()` 拒绝容器类型返回
- [ ] DynamicHost 不再吞掉异常
- [ ] IssueTracker 可序列化为 dict
- [ ] HOST spec 与实现一致
- [ ] `"hello".upper()` 返回 `"HELLO"`

---

*本文档为 IBC-Inter 下一步工作计划，可独立使用。*
