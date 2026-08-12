# _code_enum_completion — enum 补全实现记录

> 2026-08-12 编制（无人值守 session）。按 `_ENUM_SWITCH_COMPLETION_HANDOFF.md` §4.1 + PENDING_TASKS PT-FEAT-2。
> 交接文档与实测核对后定案：本批次实现值模型下的 ①③④；②（自定义方法）根因为值模型，
> 记录为设计边界，实例化方案留独立设计窗口（详见下"决策"节）。

## 现状（2026-08-12 全实测）

| 能力 | 状态 |
|---|---|
| 任意类型成员（int/float/bool/str）语法 | ✅ 已放开（KNOWN_LIMITS §二 过时） |
| 成员访问 `Color.RED` → **返回 static_val（装箱原始值，非实例）** | ✅（值模型，文档化） |
| `==`/`!=` | ✅ |
| switch/case | ✅ |
| **非 str 枚举 LLM 集成** | ❌ `EnumAxiom.from_prompt` 返回成员名非值 → switch 失配 |
| 迭代 `for v in Color:` | ❌ `VM: Object is not iterable` |
| `len(Color)` | ❌ `no method 'len'` |
| **枚举自定义方法** | ❌ 值模型下成员是原始值，方法不可达 |

## 根因与关键代码事实（全部实测确认）

1. **非 str LLM 集成**：`_get_enum_index_map`（enum.py:74-78）建 `{name:name}` 无值；
   `from_prompt`（enum.py:110-111）返回成员名。str 因值==名碰巧工作。
   - 修复通道：`MemberSpec.metadata`（member.py:45）为纯数据，序列化经 `_collect_symbol`
     （serializer.py:142）带出；engine 编译/运行时共享 metadata registry（engine.py:147/266），
     `registry.register` 同名返回既有 spec（_base.py:81-86）→ **编译期写入的 metadata 运行时可达**
     （实测 runtime spec.members 含编译器 MemberSpec）。
   - 编译期取字面值：`symbol_collection_pass.visit_IbAssign` 有 `node.value`（IbConstant.value
     即原生值）；`_define` 建 field MemberSpec。
   - 运行时值旁证：`default_fields[name].static_val`（interpreter.py:668-672）。
   - 返回值 → `registry.box(result)`（llm_parsing_strategy.py:126-129）→ 与成员 static_val 比对。

2. **迭代/数量**：`for v in Color` 走 `resolve_iterable`（shared/iterable.py:20-46）——类对象
   （`Color.ib_class`=Color 自身，IbClass.__init__ self-referential）无 `__iter__`/`to_list`；
   `len(Color)` 走 `Color.receive('len')`（collection.py:16）。运行时 `lookup_method` 沿父链
   （ib_class.py:172-178）→ **在运行时 Enum 基类绑定 to_list/len 即全体枚举生效**（Color.parent=Enum）。
   编译期类型面：`EnumAxiom.has_iter_cap=True` + `get_method_specs`（GeneratorAxiom 先例；
   `resolve_iter_element` _inference.py:271 消费 has_iter_cap，`get_element_type_name` 默认
   "any" → 元素类型 any，与值模型一致）。

3. **自定义方法根因**：`Color.RED` 经 `IbClass.__getattr__`（ib_class.py:411-412）返回 static_val
   （**IbString/IbInt 原始值**，实测 static_val.ib_class="str"）；`c=Color.RED` 后 `c.is_done()`
   分派到 String 方法表 → None。用户 `func is_done` 也未被注册到运行时 Color.methods（枚举子类
   方法注册缺口）。**即使注册，成员值是原始值，方法仍不可达**——根因是值模型非注册路径。

## 决策（self-grill + design-philosophy 对照）

- **①③④ 在本周期实现**（值模型，破坏面小，高 UX 价值）。
- **② 自定义方法**：值模型下成员值是原始值（文档化 KNOWN_LIMITS §二 2.2"访问与比较"），
  实例化改造需动 成员访问/`cast_to`/LLM 解析路径（from_prompt 在 kernel 层无法构造运行时实例，
  解析策略 box 后无类型协调）/序列化——**爆炸半径不确定，属"无法确认边界"**。按分支政策应独立
  分支实验；本周期不做，改为：KNOWN_LIMITS §二 精确记录边界 + 任务文档记录实例化设计候选。
  （`Enum.__init__/_value/__eq__` 半成品暗示原设计意图实例化，属 IBCI 自身设计缺陷候选，
  已记录待独立窗口。）

## 改动清单

| 文件 | 改动 |
|---|---|
| `core/compiler/semantic/passes/symbol_collection_pass.py` | visit_IbClassDef 跟踪枚举标志；visit_IbAssign 对枚举常量成员写 `metadata["value"]` |
| `core/kernel/axioms/primitives/enum.py` | `_get_enum_index_map` 建 `{name:value}`（metadata 取值，回退名）；`from_prompt` 大小写不敏感匹配返回值；`has_iter_cap=True` + `get_method_specs`（to_list/len） |
| `core/runtime/bootstrap/primitive_initializer.py` | 运行时 Enum 基类绑定 `to_list`/`len` 原生方法 |
| `docs/KNOWN_LIMITS.md` | §二 更新（删过时；补迭代/数量/LLM 集成状态/自定义方法边界） |
| `tests/kernel/test_enum_axiom.py` | 补值映射契约测试 |
| `tests/e2e/`（新 test_enum_completion.py） | int 枚举 LLM 集成+switch / for v in Color / len(Color) / 值模型边界 |

## 验证

- 全量 `python -m pytest tests/` 零回归（基线 2270/1）。
- 探针：`int OK=200` LLM 集成 `(str)c`="200"、switch 命中；`for v in Color` 输出成员值；
  `len(Color)`=N；str 枚举零回归（值==名）。
