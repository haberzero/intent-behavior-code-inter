# 交接：泛型赋值检查缺失 + type() 内省不对称（下一 session 缺陷核实与处理）

> 2026-08-13 编制。本文件交接**本次 session 探索过程中发现的独立问题**（非主线修复范围），
> 供下一 session 核实与处置。两处均已做根因定位与实证，待进一步核实后决定修复。

---

## 一、缺陷一：内置泛型赋值类型检查系统性缺失泛型实参校验（P1，已实证）

### 1.1 现象

`X[int]` 类型的值可赋给 `X[str]` 类型变量，编译期全部通过（应报 SEM_TYPE_MISMATCH）：

```ibci
func compute() -> int:
    return 42
thread[int] t = thread(callable=compute, args=[])
thread[str] t3 = t        # 应报错，实际通过（输出 ok）
```

**实测影响面（is_assignable 直接调用）**：

| 泛型 | `X[int] → X[str]` | 结果 |
|------|-------------------|------|
| thread | thread[int]→thread[str] | ⚠️ 放行（缺陷） |
| thread_result | 同 | ⚠️ 放行 |
| chan | 同 | ⚠️ 放行 |
| slot | 同 | ⚠️ 放行 |
| generator | 同 | ⚠️ 放行 |
| fn_callable | 同 | ⚠️ 放行 |
| behavior | 同 | ⚠️ 放行 |
| list | list[int]→list[str] | ⚠️ 放行 |
| dict | dict[str,int]→dict[str,str] | ⚠️ 放行 |
| tuple | tuple[int,str]→tuple[str,int] | ⚠️ 放行 |
| Optional | Optional[int]→Optional[str] | ✅ 拦截（唯一正确） |
| **用户类 Box[int]** | Box[int]→Box[str] | ✅ 拦截（对照） |

**10/11 类内置泛型受影响**；Optional 与用户类泛型正确。

### 1.2 根因（代码实证）

`core/kernel/spec/registry/_assignability.py` `is_assignable`：

```python
# :62 — name 比较（会正确区分 thread[int]/thread[str]）
if src.name == target.name and src.module_path == target.module_path:
    return True
...
# :72 — axiom 兼容分支（先命中，绕过 name 比较）
src_axiom = self._axiom_registry.get_axiom(src.get_base_name())
if src_axiom and src_axiom.is_compatible(target.name):
    return True
```

- `src.name` 对特化 spec 是 `thread[int]`/`thread[str]`（**不同**，:62 本应拦截）
- 但 :72 axiom 分支**先执行**，而所有内置泛型 axiom 的 `is_compatible` 用**前缀匹配**：
  `core/kernel/axioms/primitives/comm.py:54` `other_name.startswith("thread[")`（无视实参）
- 12 处前缀匹配 is_compatible 见 §1.3；仅 Optional（sentinels.py:125 前缀）因 is_assignable :48-60 有专门 OPTIONAL 分支先于 :72 命中而正确拦截；用户类泛型无 axiom 故正确拦截。

**严重性**：编译期类型安全漏洞，错误类型静默流入（与 Finding C 同类但影响面更广）。

### 1.3 涉及位置清单

| 文件 | 行 | 前缀匹配 |
|------|----|---------|
| core/kernel/axioms/primitives/comm.py | 54 | `thread[` |
| core/kernel/axioms/primitives/comm.py | 88 | `thread_result[` |
| core/kernel/axioms/primitives/comm.py | 114 | `chan[` |
| core/kernel/axioms/primitives/comm.py | 156 | `slot[` |
| core/kernel/axioms/primitives/generator.py | 37 | `generator[` |
| core/kernel/axioms/primitives/callable.py | 95/131 | `fn_callable[` |
| core/kernel/axioms/primitives/callable.py | 132 | `behavior[` |
| core/kernel/axioms/primitives/sentinels.py | 125 | `Optional[` |
| core/kernel/axioms/primitives/sequences.py | 180 | `list[` |
| core/kernel/axioms/primitives/sequences.py | 249 | `dict[` |
| core/kernel/axioms/primitives/sequences.py | 323 | `tuple[` |

### 1.4 修复方向（供参考，未实施）

- **方案 A（推荐，机制同构）**：`is_assignable` 的 :72 axiom 分支改为**先检查泛型实参**——对 src/target 同为某泛型且实参不同的情况，在 axiom 兼容前按 `name`/实参比较拒绝；axiom `is_compatible` 保留（用于非泛型兼容如 bool isa int）。
- **方案 B**：各 axiom `is_compatible` 改为结构化实参比较（不再前缀匹配），需逐一改 12 处——工程量大且易漏。
- **方案 A 关键**：确认 Optional 的专门分支可推广为通用"同 kind 泛型实参不匹配即 False"。
- 修复须按 Phase D 收敛义务：判别性回归（`X[int]`→`X[str]` 报错）+ 触发用例。

---

## 二、缺陷二（疑似）：`type()` 对泛型值内省不对称（非缺陷，待文档精确化）

### 2.1 现象

```ibci
class Box[T]:
    T value
    func __init__(self, T value) -> void:
        self.value = value

Box[int] b = Box[int](42)
list[int] li = [1, 2]
Optional[int] oi = 5
print(type(b))    # Box[int]   ← 用户类泛型带实参
print(type(li))   # list       ← 内建泛型无实参
print(type(oi))   # Optional   ← 内建泛型无实参
```

### 2.2 根源（代码实证）

`core/runtime/interpreter/intrinsics/meta.py:17-30` `_type` 返回 `obj.ib_class.name`：
- **用户类泛型**：特化生成独立 IbClass（`ib_class.py:458` create_subclass），name=`Box[int]`，带实参
- **内建泛型**：值对象运行时用**单一基类**——`core/runtime/factory.py:50` `IbList(elements, ib_class=self._registry.get_class("list"))`；`@register_ib_type("list")` 注册单类。值层**不携带特化实参元数据**（类型擦除）

### 2.3 判定

- **非缺陷**：内建容器值层单类设计合理（对齐 Python `type([])`→`list`），`12_builtins.md:15` 文档化"返回规范类型名"
- **但两个问题**：
  1. **用户类泛型 vs 内建泛型 `type()` 行为不一致**（Box[int] 带实参 vs list 不带）——同是泛型，内省形态分裂，可能造成依赖 `type()` 分派的代码困惑
  2. **文档未注明此差异**（`12_builtins.md` 未说明内建泛型返回基名、用户类泛型返回特化名）

### 2.4 处置建议

- 若**维持现状**（内建值层擦除）：在 `12_builtins.md` 补充说明"内建泛型（list/thread/Optional 等）返回基名，用户类泛型返回特化名（Box[int]）"
- 若**改进内省完整性**（P2 远期）：为内建泛型值对象携带类型实参元数据（如 IbList 持有 element spec），`type()` 返回 `list[int]`——但改动面大（值层构造/序列化/round-trip），需独立设计窗口
- **推荐**：先做文档精确化（低风险），值层带实参留待独立设计评估

---

## 三、交接建议

1. **优先处理缺陷一**（P1 编译期类型安全）：核实 1.2 根因后按 1.4 方案 A 修复，判别性回归 + 触发用例
2. **缺陷二**：做文档精确化（2.4 第一项），值层内省改进留独立窗口
3. 两者均登记 PENDING_TASKS（建议 PT-DEBT-xx 域），修复按 Phase D 收敛义务双交付
4. 完整证据日志：本 session 探针脚本已存 `/tmp/opencode/`（type_probe/type_list/chan_check/th_same 等），WORKLOG 有过程记录
