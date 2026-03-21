# IBC-Inter 下一步工作计划

> 本文档是 IBC-Inter 项目的下一步工作计划，包含详细的现状分析、任务分解和实施细则。
> 优先级高于 PENDING_TASKS.md，可独立使用。
>
> **生成日期**：2026-03-21
> **版本**：V3.2

---

## 一、现状分析

### 1.1 关键架构澄清

**重要**：DynamicHost 是**插件接口层**，Engine 是**解释器管理层**。

| 组件 | 职责 | 说明 |
|------|------|------|
| **DynamicHost** | 接口层 | 暴露 @method 给 IBCI 脚本，不持有解释器实例，纯委托 |
| **HostService** | 服务实现层 | 协调子解释器创建，委托 Engine 执行 |
| **Engine** | 解释器管理层 | 唯一持有 Interpreter 实例，负责 spawn_interpreter() |
| **Interpreter** | 执行层 | 单个解释器的执行上下文 |

**调用链**：
```
IBCI脚本 → DynamicHost → HostService → Engine.spawn_interpreter() → Interpreter
```

### 1.2 代码架构当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| **base 层** | ✅ 健康 (95%) | 原子概念完整，HostInterface已迁移 |
| **kernel 层** | ✅ 基本健康 (88%) | 符号/类型/公理基本完整 |
| **compiler 层** | ✅ 健康 (90%) | 词法/语法/语义分析完整 |
| **runtime 层** | ⚠️ 有缺陷 (85%) | 解释器基本可用，但存在MetadataRegistry双轨问题 |
| **插件系统** | ⚠️ 部分 (60%) | AI/IDBG基本完整，HOST spec命名错误需修复 |
| **综合** | ⚠️ 待修复 | 存在架构问题需先修复 |

### 1.3 已确认的缺陷（已被搁置）

| 缺陷 | 严重程度 | 搁置原因 | 触发条件 |
|------|----------|----------|----------|
| **Intent Stack 引用赋值** | 🔴 高 | 当前阶段不继承意图栈 | `inherit_intents=True` |
| **ImmutableArtifact 缺少 `__deepcopy__`** | 🟡 中 | 当前深拷贝行为可接受 | 使用深拷贝时 |
| **AxiomRegistry 共享引用** | 🟡 中 | 子解释器不修改公理 | 子环境注册新公理 |
| **DynamicHost 吞掉异常** | 🟡 中 | 接口层暂时不暴露异常 | 需要诊断信息时 |
| **run_isolated 返回 bool** | 🟡 中 | 当前只需知道成功/失败 | 需要返回实际值 |

### 1.4 已明确排除的功能

| 排除项 | 理由 |
|--------|------|
| generate_and_run | 动态生成IBCI由显式IBCI生成器进行 |
| GDB 式断点 | DynamicHost 断点是现场保存/恢复/回溯 |
| 进程级隔离 | 实例级隔离已足够 |
| hot_reload_pools | 违反解释器不修改代码原则 |

### 1.5 计划制定原则

1. **架构对齐**：区分接口层( DynamicHost )和管理层( Engine/HostService )的职责
2. **消除风险**：立即修复与设计决策不一致的问题
3. **最小目标**：DynamicHost 先实现最小可用功能
4. **渐进完善**：先确保核心可用，再完善周边功能

---

## 二、立即执行任务（Phase 0）

> **重要**：在执行 Phase 1 之前，必须先修复以下架构问题。

### 🔴 A.0.1 恢复 HostInterface 位置

**问题**：之前将 `HostInterface` 从 `base/` 迁移到 `runtime/host/`，但这没有解决根本问题。

**分析结论**：
- `HostInterface` 本质上是**接口契约定义**，包含 metadata 和 runtime registry
- 真正的问题是 MetadataRegistry **双轨制**（轨A：builtin初始化，轨B：discover_all）
- 将 HostInterface 放在哪一层都不是正确答案

**文件**：`core/runtime/host/host_interface.py`

**状态**：保持当前位置（runtime/host/），因为它需要被 runtime 层和 compiler 层共同访问。

---

### 🔴 A.0.2 修复 MetadataRegistry 双轨制

**问题描述**：
- `KernelRegistry.get_metadata_registry()` 在 builtin 初始化时创建（轨A）
- `HostInterface.metadata` 在 discover_all 时创建（轨B）
- `discover_all()` 第24行创建新的 `HostInterface()`，完全忽略传入的 registry 参数

**根因**：`discovery.py:24` 的代码：
```python
host = HostInterface()  # 创建新实例，触发 MetadataRegistry() 实例化
```

**修复方案**：修改 `discover_all()` 使用传入的 registry 创建 HostInterface

**文件**：`core/runtime/module_system/discovery.py`

**修改内容**：
```python
# 第17-24行修改
def discover_all(self, registry: Optional[Any] = None) -> HostInterface:
    # 如果传入了 registry，让 HostInterface 使用它
    host = HostInterface(external_registry=registry) if registry else HostInterface()
    ...
```

**同时修改 HostInterface**：
```python
class HostInterface:
    def __init__(self, external_registry=None):
        from core.kernel.types.registry import MetadataRegistry
        # 优先使用外部传入的 registry，实现单一数据源
        self.metadata = external_registry if external_registry else MetadataRegistry()
        self.runtime = HostModuleRegistry()
        ...
```

**验证清单**：
- [ ] `discover_all(registry)` 正确使用传入的 registry
- [ ] Compiler 和 Runtime 使用同一个 MetadataRegistry 实例
- [ ] 元数据查询结果一致

---

### 🔴 A.0.3 修复 HOST 插件 spec 命名

**问题**：`ibc_modules/host/` 使用 `spec.py` 而非规范要求的 `_spec.py`

**文件**：`ibc_modules/host/`

**修改内容**：
1. 重命名 `spec.py` → `_spec.py`
2. 同时修正方法名：`run` → `run_isolated`

**实施细则**：
```bash
mv ibc_modules/host/spec.py ibc_modules/host/_spec.py
```

```python
# ibc_modules/host/_spec.py
spec = (
    SpecBuilder("host")
    .func("save_state", params=["str"])
    .func("load_state", params=["str"])
    .func("run_isolated", params=["str", "dict"], returns="bool")  # 改名
    .func("get_source", returns="str")
    .build())
```

**同时修改 HostImplementation**：
```python
# ibc_modules/host/__init__.py
@ibcext.method("run_isolated")  # 改名
def ib_run(self, path: str, policy: Dict[str, Any]) -> bool:
    ...
```

**验证清单**：
- [ ] `ModuleDiscoveryService.discover_all()` 能发现 host 插件
- [ ] `host.run_isolated()` 方法可被正确调用

---

### 🟡 A.0.4 清理 builtin_initializer 孤立 host_* 函数

**问题**：`builtin_initializer.py` 注册了 `host_save_state`、`host_load_state`、`host_run` 等函数元数据，但没有实际实现绑定。

**文件**：`core/runtime/bootstrap/builtin_initializer.py`

**分析**：
- 这些是早期设计遗留，当时希望将 HOST 能力作为内置函数
- 后改为插件实现，但遗留了元数据注册

**修改内容**：移除以下孤立元数据注册（约第155-177行）：
- `host_save_state`
- `host_load_state`
- `host_run`
- `host_get_source`

**验证清单**：
- [ ] builtin_initializer 不再注册孤立的 host_* 函数
- [ ] HOST 能力通过 ibc_modules/host 插件提供

---

## 三、Phase 1 任务（公理体系健壮性）

> **新增**：基于严格分析，将 fallback 分为"逻辑必须"和"妥协性"两类。
> **原则**：只有职责分离的 fallback（公理声明行为+描述符持有具体类型）是允许的，其他 fallback 必须修复。

### 🔴 3.0 ListMetadata/DictMetadata 的 fallback（妥协性，必须修复）

**问题分析**：
- `ListMetadata.get_element_type()` 和 `resolve_item()` 在 Axiom 失败时 fallback 到 `self.element_type`
- 这违反了"公理为唯一真源"原则，描述符不应同时充当数据存储
- 如果 Axiom 返回 `int` 但 `self.element_type` 是 `str`，系统会默默使用错误的值

**文件**：`core/kernel/types/descriptors.py`

**修改内容**（约L391-412, L468-471）：
```python
# 修复前
def get_element_type(self) -> Optional[TypeDescriptor]:
    res = super().get_element_type()
    if res: return res
    return self.element_type  # <-- 妥协性 fallback

def resolve_item(self, key: TypeDescriptor) -> Optional[TypeDescriptor]:
    res = super().resolve_item(key)
    if res: return res
    return self.element_type  # <-- 妥协性 fallback

# 修复后
def get_element_type(self) -> Optional[TypeDescriptor]:
    res = super().get_element_type()
    return res  # 只从 Axiom 获取，不 fallback

def resolve_item(self, key: TypeDescriptor) -> Optional[TypeDescriptor]:
    res = super().resolve_item(key)
    return res  # 只从 Axiom 获取，不 fallback
```

**注意**：修复后，如果 `ListAxiom.get_element_type()` 返回 None，则整个 list 的元素类型将变为 None/Any，不再有隐藏的默认值。

**验证清单**：
- [ ] ListMetadata 不再 fallback 到 `self.element_type`
- [ ] DictMetadata 不再 fallback 到 `self.value_type`
- [ ] 列表下标访问类型完全由 Axiom 决定

---

### 🔴 3.1 StrAxiom.resolve_item/get_element_type 返回 None（妥协性，必须修复）

**问题分析**：
- `StrAxiom.get_element_type()` 和 `resolve_item()` 明确注释 "Should return STR_DESCRIPTOR" 但返回 None
- 这是公理实现错误，会导致字符串下标访问类型信息丢失

**文件**：`core/kernel/axioms/primitives.py`

**修改内容**（约L234-240）：
```python
# 修复前
def get_element_type(self) -> 'TypeDescriptor':
    return None # Should return STR_DESCRIPTOR (self)

def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
    if key.get_base_axiom_name() == "int":
        return None # Should return STR_DESCRIPTOR
    return None

# 修复后
def get_element_type(self) -> 'TypeDescriptor':
    return STR_DESCRIPTOR

def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
    if key.get_base_axiom_name() == "int":
        return STR_DESCRIPTOR
    return None  # 其他 key 类型不支持
```

**验证清单**：
- [ ] `StrAxiom.get_element_type()` 返回 `STR_DESCRIPTOR`
- [ ] `StrAxiom.resolve_item(int)` 返回 `STR_DESCRIPTOR`
- [ ] IBCI 脚本 `str[0]` 正确返回 `str` 类型

---

### 🔴 3.2 AxiomHydrator 静默返回（妥协性，必须修复）

**问题分析**：
- `AxiomHydrator.inject_axioms()` 在 `axiom_registry` 不存在时静默返回
- 这会导致描述符永远没有公理绑定，后续所有能力访问都降级到 None
- 如果 registry 不可用，应该是系统配置错误，不应该静默忽略

**文件**：`core/kernel/types/axiom_hydrator.py`

**修改内容**（约L18-22）：
```python
# 修复前
def inject_axioms(self, descriptor: TypeDescriptor):
    axiom_registry = self._registry.get_axiom_registry()
    if not axiom_registry:
        return  # <-- 静默返回

# 修复后
def inject_axioms(self, descriptor: TypeDescriptor):
    axiom_registry = self._registry.get_axiom_registry()
    if not axiom_registry:
        raise RuntimeError(
            f"Critical: AxiomRegistry not available for descriptor '{descriptor.name}'. "
            f"Cannot hydrate descriptor without axiom binding."
        )
```

**验证清单**：
- [ ] `axiom_registry` 不可用时抛出 RuntimeError
- [ ] 错误消息包含描述符名称
- [ ] 不再静默忽略配置错误

---

### 🟡 3.3 ExpressionAnalyzer 静默 fallback 到 Any（妥协性，应该修复）

**问题分析**：
- `visit_IbSubscript` 和 `visit_IbCall` 使用 `return res or self._any_desc` 模式
- 当类型推导失败时静默返回 Any，掩盖了真正的类型错误
- 正确的做法应该是给出精确的错误提示，但保留返回 Any 以允许编译继续

**文件**：`core/compiler/semantic/passes/expression_analyzer.py`

**修改内容**（约L85-93, L172-180）：
```python
# 修复前
res = value_type.resolve_item(key_type)
return res or self._any_desc

# 修复后
res = value_type.resolve_item(key_type)
if res is None:
    self.error(
        f"Type '{value_type.name}' does not support subscript access with key type '{key_type.name}'",
        node, code="SEM_003"
    )
    return self._any_desc
return res
```

**验证清单**：
- [ ] 下标访问类型错误时给出精确错误信息
- [ ] 函数调用类型错误时给出精确错误信息
- [ ] 错误信息包含具体的类型名称

---

## 四、Phase 2 任务（消除风险）

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
3. 确认工厂方法已正确设置

**验证清单**：
- [ ] `inherit_intents` 默认值为 `False`
- [ ] 运行测试确认子解释器不继承意图栈

---

## 三、DynamicHost 最小实现（Phase 2）

> **架构说明**：Phase 2 任务分为两层：
> - **接口层（DynamicHost）**：负责返回值验证、异常处理、结果封装
> - **管理层（Engine/HostService）**：负责解释器创建、隔离执行

### 🟡 3.1 基本内置类型返回值机制

**任务**：实现子解释器返回基本内置类型（int/str/bool/float/none），禁止容器和插件类

**架构理解**：
- `Interpreter.run()` 返回 `IbObject`（Engine/HostService 层）
- `DynamicHost` 接口层负责验证返回类型并决定如何暴露（接口层）
- `HostService` 保持简单，只负责传递返回值

**当前状态**：
- `run()` 返回固定 `bool`
- `run_isolated()` 返回固定 `bool`
- 无法传递实际计算结果

**目标**：
- `Interpreter.run()` 返回 `IbObject`
- `DynamicHost` 验证返回类型
- 只允许基本内置类型返回

**文件列表**：
| 文件 | 层级 | 操作 | 修改内容 |
|------|------|------|----------|
| `core/kernel/axioms/protocols.py` | Kernel | 修改 | 添加 `can_return_from_isolated()` 到 TypeAxiom |
| `core/kernel/axioms/primitives.py` | Kernel | 修改 | 在具体公理中覆盖该属性 |
| `core/runtime/interpreter/interpreter.py` | Interpreter | 修改 | `run()` 返回类型从 `bool` 改为 `IbObject` |
| `core/runtime/host/service.py` | HostService | 修改 | `run_isolated()` 返回 `IbObject` 而非 `bool` |
| `core/runtime/host/dynamic_host.py` | 接口层 | 修改 | 添加 `_validate_return_value()` 验证返回类型 |

**实施细则**：

**Step 1**：修改 Kernel 层（`core/kernel/axioms/protocols.py`）
```python
class TypeAxiom(Protocol):
    # ... 现有内容 ...
    def can_return_from_isolated(self) -> bool:
        """[IES 2.1 Security] 判断该类型的实例是否允许从隔离子环境返回。"""
        ...
```

**Step 2**：修改 Kernel 层（`core/kernel/axioms/primitives.py`）
```python
class BaseAxiom(TypeAxiom):
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

**Step 3**：修改 Interpreter 层（`core/runtime/interpreter/interpreter.py`）
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

**Step 4**：修改接口层（`core/runtime/host/dynamic_host.py`）
```python
def _validate_return_value(self, value: IbObject) -> IbObject:
    """验证返回值是否允许从隔离环境返回（接口层职责）"""
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
- [ ] `Interpreter.run()` 返回 `IbObject`
- [ ] `DynamicHost._validate_return_value()` 正确验证类型
- [ ] 容器类型返回时降级为 None

---

### 🟡 3.2 DynamicHost 异常处理修复

**任务**：修复 DynamicHost 吞掉异常的问题，让异常或错误信息可通过接口访问

**架构理解**：
- DynamicHost 是**接口层**，负责决定如何暴露异常
- HostService 保持简单，让异常向上传播
- 异常信息通过接口返回，不穿透到 IBCI 脚本层

**当前状态**：
```python
# dynamic_host.py:54-58
except Exception:
    return False  # 错误信息完全丢失
```

**目标**：
- 异常不被吞掉
- 错误信息可通过接口访问
- 与现有调用代码兼容

**文件**：`core/runtime/host/dynamic_host.py`

**实施方案**：返回结构化结果
```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class IsolatedRunResult:
    success: bool
    diagnostics: List['Diagnostic']
    exception_type: Optional[str]
    exception_message: Optional[str]
    return_value: Optional['IbObject']

@method("run_isolated")
def run_isolated(self, path: str, policy: Dict[str, Any]) -> 'IsolatedRunResult':
    """接口层职责：处理异常，决定如何暴露结果"""
    sc = self._capabilities.service_context
    if sc and sc.host_service:
        try:
            isolation_policy = IsolationPolicy.from_dict(policy) if isinstance(policy, dict) else policy
            result = sc.host_service.run_isolated(path, isolation_policy.to_dict())

            # 接口层：验证返回值
            validated_value = self._validate_return_value(result)

            return IsolatedRunResult(
                success=True,
                diagnostics=[],
                exception_type=None,
                exception_message=None,
                return_value=validated_value
            )
        except Exception as e:
            # 接口层：捕获并封装异常，不让异常穿透
            return IsolatedRunResult(
                success=False,
                diagnostics=[],
                exception_type=type(e).__name__,
                exception_message=str(e),
                return_value=None
            )
    return IsolatedRunResult(success=False, diagnostics=[], exception_type=None, exception_message=None, return_value=None)
```

**验证清单**：
- [ ] 成功时返回 `IsolatedRunResult`，success=True
- [ ] 失败时返回 `IsolatedRunResult`，success=False，包含异常信息
- [ ] 异常类型和消息可访问

---

### 🟡 3.3 IssueTracker 序列化支持

**任务**：为 IssueTracker 添加 `to_dict()` 方法，支持诊断信息序列化

**架构理解**：
- IssueTracker 是 compiler 层的诊断系统
- 序列化用于接口层返回诊断信息
- 不改变 Engine/HostService 的职责

**文件**：`core/compiler/diagnostics/issue_tracker.py`

**实施方案**：
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
                } if d.location else None,
                "hint": d.hint,
            }
            for d in self._diagnostics
        ],
        "error_count": self._error_count,
        "warning_count": self.warning_count,
    }
```

**验证清单**：
- [ ] IssueTracker 可序列化为 dict
- [ ] 序列化内容包含所有诊断信息

---

## 四、核心语法完善（Phase 3）

### 🟡 4.1 HOST 插件 spec 更新

**任务**：更新 HOST 插件的 spec.py 使其与实现一致

**文件**：
| 文件 | 操作 | 内容 |
|------|------|------|
| `ibc_modules/host/spec.py` | 修改 | 将 `run` 改为 `run_isolated` |

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

---

### 🟡 4.2 str/list/dict 方法扩展

**任务**：在公理体系中扩展 str 常用方法

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
        "split": FunctionMetadata(name="split", param_types=[], return_type=ListMetadata(element_type=STR_DESCRIPTOR)),
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

    def split(self) -> IbList:
        return self.ib_class.registry.box(self.value.split())
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

**新增文件**：`core/runtime/serialization/snapshot_options.py`

**修改文件**：
- `core/runtime/serialization/runtime_serializer.py`
- `core/runtime/host/service.py`
- `core/runtime/host/dynamic_host.py`

---

## 六、IES 2.2 插件系统重构（Phase 5）

> **愿景**：实现零侵入自动嗅探机制，插件不再需要 import 任何核心代码

### 🟡 5.1 AutoDiscoveryService 实现

**任务**：实现全自动插件发现服务，支持扫描 _spec.py 并发现 IES 2.2 插件

**新增文件**：`core/extension/auto_discovery.py`

**职责**：
- 扫描 `ibc_modules/` 和 `plugins/` 目录
- 通过 `importlib` 动态加载 _spec.py
- 检测 `__ibcext_metadata__()` 和 `__ibcext_vtable__()` 固定命名方法
- 构建 PluginSpec 对象返回

**核心逻辑**：
```python
class AutoDiscoveryService:
    def discover_plugins(self, plugin_dirs: List[str]) -> List[PluginSpec]:
        discovered = []
        for plugin_dir in plugin_dirs:
            for spec_file in Path(plugin_dir).glob("*/_spec.py"):
                spec = self._load_spec(spec_file)
                if self._is_valid_ies22_plugin(spec):
                    discovered.append(self._create_plugin_spec(spec))
        return discovered
    
    def _load_spec(self, spec_path: Path) -> Dict[str, Any]:
        spec_module = importlib.import_module(
            spec_path.stem, 
            f"{spec_path.parent.name}"
        )
        metadata = getattr(spec_module, '__ibcext_metadata__', lambda: {})()
        vtable_func = getattr(spec_module, '__ibcext_vtable__', None)
        return {"metadata": metadata, "vtable": vtable_func}
```

**验证清单**：
- [ ] AutoDiscoveryService 可扫描 ibc_modules/
- [ ] 可发现实现了 `__ibcext_metadata__()` 的插件
- [ ] 可调用 `__ibcext_vtable__()` 获取虚表

---

### 🟡 5.2 固定命名方法协议定义

**任务**：在插件开发者手册中明确固定命名方法协议

**文件**：`docs/plugin_developer_guide.md`（新增）

**协议内容**：
| 方法名 | 必须实现 | 返回值 | 说明 |
|--------|----------|--------|------|
| `__ibcext_metadata__()` | ✅ | Dict[str, Any] | 返回插件元数据 |
| `__ibcext_vtable__()` | ✅ | Dict[str, Callable] | 返回方法映射表 |
| `create_factory()` | ❌ | Callable | 可选工厂函数 |
| `create_implementation()` | ❌ | Any | 可选实现创建函数 |

**元数据格式**：
```python
def __ibcext_metadata__():
    return {
        "name": "plugin_name",
        "version": "1.0.0",
        "description": "...",
        "dependencies": [],  # 可选
    }
```

---

### 🟡 5.3 向后兼容适配器

**任务**：实现适配器支持 IES 2.0/2.1 插件（可选，后期执行）

**新增文件**：`core/extension/plugin_adapter.py`

**职责**：
- 检测插件是否使用旧版 `@ibcext.method` 装饰器
- 自动转换为 IES 2.2 格式
- 支持混合使用场景

```python
class LegacyPluginAdapter:
    """将 IES 2.0/2.1 插件适配到 IES 2.2"""
    
    def adapt(self, plugin: IbPlugin) -> PluginSpec:
        vtable = plugin.get_vtable()  # 调用 IbPlugin 的 get_vtable()
        metadata = {"name": plugin.plugin_id, "version": "legacy"}
        return PluginSpec(metadata=metadata, vtable=vtable)
```

**验证清单**：
- [ ] 可检测旧版 `@ibcext.method` 装饰器
- [ ] 可转换为 PluginSpec 格式

---

### 🟡 5.4 内置插件 IES 2.2 迁移（可选）

**任务**：逐步将内置插件（AI/IDBG/HOST）迁移到 IES 2.2

**修改文件**：
- `ibc_modules/ai/_spec.py`
- `ibc_modules/idbg/_spec.py`
- `ibc_modules/host/_spec.py`

**迁移示例**：
```python
# ibc_modules/ai/_spec.py - IES 2.2 格式
def __ibcext_metadata__():
    return {
        "name": "ai",
        "version": "1.0.0",
        "description": "LLM provider plugin",
    }

def __ibcext_vtable__():
    return {
        "complete": _ai_complete,
        "embed": _ai_embed,
    }

def create_implementation():
    from .core import AIPlugin
    return AIPlugin()  # 可继承 IbPlugin，但 _spec.py 不需要 import
```

---

### 🟡 5.3 元数据序列化（.ibc_meta 文件生成）

**任务**：实现构建时元数据快照生成，使编译器能在编译前获取插件类型签名

**架构理解**：
- 编译器在 STAGE_3 (PLUGIN_METADATA) 之后进行静态类型检查
- 只要在编译前完成 `discover_all()` 并将元数据注册到 `MetadataRegistry`，静态类型检查完全保留
- IES 2.2 通过 `.ibc_meta` 文件实现构建时元数据共享

**核心流程**：
```
构建阶段（ibcc --pre-scan-specs）：
    AutoDiscoveryService.discover_all() → 生成 .ibc_meta (JSON)
    ↓
编译阶段（ibcc）：
    Scheduler.load_metadata_from_file() → 写入 MetadataRegistry
    ↓
静态类型检查通过 → FlatSerializer 生成扁平JSON
```

**实施步骤**：

**Step 1**：修改 `AutoDiscoveryService`（`core/runtime/module_system/discovery.py`）
```python
def export_metadata(self, output_path: str) -> None:
    """将发现的元数据导出为 .ibc_meta 文件"""
    metadata_snapshot = {
        "version": "1.0",
        "modules": {}
    }
    
    for module_name, module_metadata in self._host_interface.metadata.get_all_modules().items():
        metadata_snapshot["modules"][module_name] = self._serialize_descriptor(module_metadata)
    
    import json
    with open(output_path, 'w') as f:
        json.dump(metadata_snapshot, f, indent=2)

def _serialize_descriptor(self, desc: TypeDescriptor) -> Dict[str, Any]:
    """将 TypeDescriptor 序列化为可JSON化的字典"""
    result = {
        "name": desc.name,
        "kind": desc.kind,
        "module_path": desc.module_path,
        "is_nullable": desc.is_nullable,
        "is_user_defined": desc.is_user_defined,
    }
    
    if hasattr(desc, 'members') and desc.members:
        result["members"] = {
            name: self._serialize_symbol(sym) 
            for name, sym in desc.members.items()
        }
    
    return result
```

**Step 2**：修改 `Scheduler`（`core/compiler/scheduler.py`）
```python
def load_metadata_from_file(self, meta_path: str) -> None:
    """从 .ibc_meta 文件加载元数据到 MetadataRegistry"""
    import json
    with open(meta_path, 'r') as f:
        metadata_snapshot = json.load(f)
    
    for module_name, module_data in metadata_snapshot.get("modules", {}).items():
        desc = self._deserialize_descriptor(module_data)
        self.registry.register(desc)

def _deserialize_descriptor(self, data: Dict[str, Any]) -> TypeDescriptor:
    """从字典反序列化为 TypeDescriptor"""
    from core.kernel.types import TypeFactory
    kind = data.get("kind")
    
    if kind == "FunctionMetadata":
        param_types = [self._deserialize_descriptor(p) for p in data.get("param_types", [])]
        return_type = self._deserialize_descriptor(data.get("return_type")) if data.get("return_type") else None
        return self.registry.factory.create_function(param_types, return_type)
    
    # ... 其他类型处理
```

**Step 3**：修改 ibcc 构建命令
```python
# 添加 --pre-scan-specs 参数
parser.add_argument('--pre-scan-specs', action='store_true', 
                    help='扫描 _spec.py 并生成 .ibc_meta 元数据文件')

# 在编译前执行
if args.pre_scan_specs:
    discovery = ModuleDiscoveryService([builtin_path, plugins_path])
    discovery.discover_all(registry)
    discovery.export_metadata('.ibc_meta')
    return  # 仅生成元数据，不执行编译
```

**验证清单**：
- [ ] `ibcc --pre-scan-specs` 能生成 .ibc_meta 文件
- [ ] .ibc_meta 包含所有插件模块的类型签名
- [ ] `ibcc` 编译时能读取 .ibc_meta 并注册到 MetadataRegistry
- [ ] 静态类型检查正常工作

---

## 七、执行顺序总览

```
Phase 0: 架构修复（阻断性问题，必须先执行）
├── A.0.1 确认 HostInterface 位置（已完成，维持现状）
├── A.0.2 修复 MetadataRegistry 双轨制
│   ├── 修改 discovery.py 使用传入的 registry
│   └── 修改 HostInterface 接受外部 registry
├── A.0.3 修复 HOST 插件 spec 命名
│   ├── 重命名 spec.py → _spec.py
│   └── 统一方法名 run → run_isolated
└── A.0.4 清理 builtin_initializer 孤立 host_* 函数

Phase 1: 公理体系健壮性（必须修复的妥协性回退）
├── 3.0 ListMetadata/DictMetadata fallback 修复
├── 3.1 StrAxiom.resolve_item/get_element_type 修复
├── 3.2 AxiomHydrator 静默返回修复
└── 3.3 ExpressionAnalyzer 静默 fallback 修复

Phase 2: 消除风险
└── 2.1 inherit_intents 默认值修改

Phase 3: DynamicHost 最小实现
├── 3.3 IssueTracker 序列化支持
├── 4.1 基本内置类型返回值机制
│   ├── Step 1: 修改 TypeAxiom Protocol
│   ├── Step 2: 修改具体公理类
│   ├── Step 3: 修改 Interpreter.run()
│   ├── Step 4: 修改 HostService.run_isolated() 返回 IbObject
│   └── Step 5: 修改 DynamicHost 添加验证逻辑
└── 4.2 DynamicHost 异常处理修复
    ├── 定义 IsolatedRunResult dataclass
    └── 修改 run_isolated() 返回结构化结果

Phase 4: 核心语法完善
├── 4.1 HOST 插件 spec 更新
└── 4.2 str 方法扩展

Phase 5: 可选扩展
├── 5.1 AI 组件异步并发
└── 5.2 子解释器快照机制

Phase 6: IES 2.2 插件系统重构
├── 6.1 AutoDiscoveryService 实现
├── 6.2 固定命名方法协议定义
├── 6.3 元数据序列化（.ibc_meta 文件生成）
├── 6.4 向后兼容适配器
└── 6.5 内置插件迁移
```

Phase 4: 核心语法完善
├── 4.1 HOST 插件 spec 更新
└── 4.2 str 方法扩展

Phase 5: 可选扩展
├── 5.1 AI 组件异步并发
└── 5.2 子解释器快照机制

Phase 6: IES 2.2 插件系统重构
├── 6.1 AutoDiscoveryService 实现
├── 6.2 固定命名方法协议定义
├── 6.3 元数据序列化（.ibc_meta 文件生成）
├── 6.4 向后兼容适配器
└── 6.5 内置插件迁移
```

---

## 八、最终验证检查清单

### Phase 0 完成后验证
- [ ] discovery.py 正确使用传入的 registry
- [ ] HOST 插件可被 ModuleDiscoveryService 发现
- [ ] builtin_initializer 无孤立 host_* 函数

### Phase 1 完成后验证
- [ ] StrAxiom.get_element_type() 返回 STR_DESCRIPTOR
- [ ] StrAxiom.resolve_item(int) 返回 STR_DESCRIPTOR
- [ ] ExpressionAnalyzer 给出精确类型错误信息

### Phase 2 完成后验证
- [ ] inherit_intents 默认值为 False

### Phase 3 完成后验证
- [ ] Interpreter.run() 返回 IbObject
- [ ] DynamicHost._validate_return_value() 正确验证类型
- [ ] DynamicHost.run_isolated() 返回 IsolatedRunResult
- [ ] IssueTracker 可序列化为 dict

### Phase 4 完成后验证
- [ ] HOST spec 与实现一致
- [ ] "hello".upper() 返回 "HELLO"

---

## 九、BoundMethodAxiom 边界问题结论

**判断**：不需要修复

**理由**：
1. `BoundMethodAxiom.get_methods()` 返回空是**正确的架构决策**
2. Bound method 是"函数调用"而非"类型"，方法已委托给原始 function_type
3. 正常调用链（obj.method()）完全正常，不依赖 members
4. 如果有人尝试在 bound method 上继续查找方法，那是调用方语义错误

**建议**：保持现状，无需修改。

Phase 3: 完善性工作
├── 4.1 HOST 插件 spec 更新
└── 4.2 str 方法扩展

Phase 4: 可选扩展
├── 5.1 AI 组件异步并发
└── 5.2 子解释器快照机制

Phase 5: IES 2.2 插件系统重构
├── 5.1 AutoDiscoveryService 实现
├── 5.2 固定命名方法协议定义
├── 5.3 元数据序列化（.ibc_meta 文件生成）
│   ├── AutoDiscoveryService 增加 export_metadata() 方法
│   ├── ibcc 命令增加 --pre-scan-specs 参数
│   └── Scheduler 增加 load_metadata_from_file() 方法
├── 5.4 向后兼容适配器（可选）
└── 5.5 内置插件迁移（可选，渐进执行）
```

---

## 八、验证清单

完成 Phase 1-3 后应验证：

- [ ] `inherit_intents` 默认值为 `False`
- [ ] `Interpreter.run()` 返回 `IbObject`
- [ ] `DynamicHost._validate_return_value()` 正确验证类型
- [ ] `DynamicHost.run_isolated()` 返回 `IsolatedRunResult`
- [ ] 成功/失败情况都返回结构化结果
- [ ] IssueTracker 可序列化为 dict
- [ ] HOST spec 与实现一致
- [ ] `"hello".upper()` 返回 `"HELLO"`

---

## 九、架构理解检查

执行任务前，请确认理解以下架构关系：

| 层级 | 组件 | 职责 |
|------|------|------|
| **接口层** | DynamicHost | 暴露 @method，验证返回值，处理异常暴露 |
| **服务层** | HostService | 协调子解释器创建，保持简单 |
| **管理层** | Engine | 持有解释器实例，spawn_interpreter() |
| **执行层** | Interpreter | 单个解释器的执行上下文 |

**重要**：不要在 HostService 层添加复杂的验证逻辑，这些应该在 DynamicHost（接口层）或 Engine（管理层）处理。

---

*本文档为 IBC-Inter 下一步工作计划，可独立使用。*
