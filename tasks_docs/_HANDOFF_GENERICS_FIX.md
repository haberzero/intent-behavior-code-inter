# HANDOFF — 泛型缺陷 G3 / BOUNDARY-G2 修复交接

> 2026-08-12 编制。**本文件是给下一智能体（接手者）的修复任务交接**。
> 目标：修复泛型修复回归试用中新发现的 2 项缺陷（G3 / BOUNDARY-G2）。
> 交接内容：缺陷现象与证据、根因分析起点、修复方向建议、验证方法、约束。

---

## 一、背景与任务定位

- 前置已完成：用户类泛型（PT-FEAT-3）落地（35bb2de）+ 深度核验 + 四项缺陷修复
  （32484fe/3fe98d6/d100ee1，全量 2350 passed / 1 skipped）。
- 泛型修复回归试用（`_GENERICS_TRIAL_FIX_20260812/`，commit d57f490）**重点检测最近修复成果**，
  修复本身全 PASS，但**新发现 2 项既有缺陷**（git worktree 在修复前 35bb2de 复现，确认**非本次修复引入**）。
- **本任务**：修复这 2 项缺陷。均为 `class Box[T]` 泛型特性范畴，涉及编译/运行时。

---

## 二、缺陷 1 — KERNEL-ISSUE-G3（P1，严重）：继承特化 + 父类字段值丢失

### 现象
```ibci
class Node[T]:
    T data
    func get(self) -> T:
        return self.data

class Linked[T](Node[T]):
    str tag

Linked[int] l1 = Linked[int](5)
l1.tag = "A"
print(l1.get())    # 期望 5，实际 None（静默值丢失，非崩溃）
print(l1.data)     # None
```

### 证据
- 用例：`_GENERICS_TRIAL_FIX_20260812/cases/R1-05-selfref-inherit.ibci`（`d1=A:None d2=None`）
- 用例：`R5-01-core-regression.ibci`（`sub=NoneL`）
- 日志：`_GENERICS_TRIAL_FIX_20260812/logs/R1-05-selfref-inherit.log`、`R5-01-core-regression.log`
- **git worktree 在 35bb2de（修复前）复现**——PT-FEAT-3 既有缺陷，非本次修复引入。

### 特征
- **静默错误**（不报错、值丢失）——比崩溃更隐蔽。
- 触发条件：**继承 + 泛型特化**。非继承的自引用字段（R1-01~04）与无继承特化（D2-02 多级继承曾 PASS）正常。

### 根因分析起点（已探查的方向）
- `Linked[int]` 是特化 IbClass（name="Linked[int]"）。`instantiate` 沿继承链收集
  `default_fields`（`ib_class.py` `_eval_field_defaults` 遍历 `cls.parent` 链）。
- 疑似点 A：**`Linked[int]` 特化类的 parent 是 `Node[int]`（特化父类）**——特化父类
  `Node[int]` 的 `default_fields` 可能未含 `data`（父类字段未正确绑定到特化父类）。
- 疑似点 B：`_hydrate_user_classes` 对特化类从基类 AST 绑定字段，但 `Linked[int]` 绑定的是
  Linked 节点（含 tag），`data`（Node 的字段）经继承链的 `default_fields` 收集是否缺失。
- 对照：普通继承（非泛型）`class Sub(Base)` 字段值正常（既有测试）。**差异在特化父类
  `Node[int]` 的字段绑定**。

### 建议修复路径
1. 先用探针确认 `Linked[int]` 运行时 `default_fields` 内容与继承链（`Linked[int].parent` 是否为
   `Node[int]`，`Node[int].default_fields` 是否含 `data`，`Node[int]` 的字段是否 hydration 绑定）。
2. 对比 `class Sub(Base)`（普通继承，字段正常）与 `class Sub[T](Base[T])` 的 `default_fields` 差异。
3. 修复点在 `_hydrate_user_classes`（interpreter.py）特化类字段绑定 或 `instantiate` 继承链收集
   （ib_class.py），消除"特化父类字段未绑定"缺口。

---

## 三、缺陷 2 — BOUNDARY-G2（P2）：自引用链 while 遍历类型退化

### 现象
```ibci
class Node[T]:
    T data
    Node[T] next = any
    func get(self) -> T:
        return self.data

list[Node[int]] nodes = [Node[int](1), Node[int](2), Node[int](3)]
nodes[0].next = nodes[1]
nodes[1].next = nodes[2]
Node[int] cur = nodes[0]
while cur is not None:
    total = total + cur.get()   # 第二次迭代：cur 类型退化 any → AttributeError
    cur = cur.next
```

### 证据
- 用例：`R5-04-combo-bomb.ibci`
- 日志：`_GENERICS_TRIAL_FIX_20260812/logs/R5-04-combo-bomb.log`
- 错误：`AttributeError: Class 'any' has no attribute 'get'`

### 特征
- 首次迭代正常（`cur` 为 `Node[int]`），`cur = cur.next`（自引用字段回写变量）后，第二次
  `cur.get()` 报 `cur` 类型为 any。
- 直接访问（无 while 回写）正常：`Node[int] first = nodes[0]; first.get()` PASS（probe_list）。
- 触发条件：**自引用字段 `cur = cur.next` 回写变量 + 循环**。

### 根因分析起点
- 运行时类型跟踪：`cur = cur.next` 赋值后，`cur` 的运行时类型未保持 `Node[int]`。
  `cur.next` 的运行时值类型推断或变量重赋值时类型信息丢失。
- 对比：普通字段回写（`cur = cur.value`，int）正常？需验证是否仅自引用泛型字段触发。
- 可能涉及：`vm_handle_IbAssign` / `_vm_assign_to_target` 对赋值目标运行时类型的处理，
  或 `IbAttribute` 访问 `cur.next` 返回值的类型标识。

### 建议修复路径
1. 用探针确认 `cur = cur.next` 赋值后 `cur` 符号的运行时类型来源。
2. 对比普通字段（`cur = cur.value`）与自引用泛型字段（`cur = cur.next`）差异。
3. 修复点在运行时变量赋值类型跟踪（避免退化 any），或语义层对自引用字段访问的类型保持。

---

## 四、验证方法

### 复现缺陷
```bash
conda activate ibci
# 用试用目录直接跑（无需 harness，先确认复现）
python main.py run tasks_docs/_GENERICS_TRIAL_FIX_20260812/cases/R1-05-selfref-inherit.ibci
python main.py run tasks_docs/_GENERICS_TRIAL_FIX_20260812/cases/R5-04-combo-bomb.ibci
```

### 修复后验证
1. 上述两用例输出正确（`Linked[int](5).get()==5`；while 遍历 total=6）。
2. 补回归测试：`tests/e2e/test_user_class_generics.py` 增
   `TestGenericInheritedFieldValue`（G3）+ `TestGenericSelfRefLoop`（BOUNDARY-G2）。
3. 全量 pytest 零回归：
   ```bash
   python -m pytest tests/
   ```
   （当前基线 **2350 passed / 1 skipped**）
4. 独立复核（general agent）+ 回归试用相关用例复跑。

---

## 五、约束

- 全程本地 commit；**禁 push**（硬原则，除非用户显式授权）。
- 破坏性重构授权：符合一般工程经验且经分析优于现有体系时默认已授权自主推进，详记决策。
- 分支政策：无法确认边界的破坏性重构 100% 授权独立分支实验；零风险改进可直接合并
  unsafe-vibe-dev；永远不触碰 main。
- 工作模式定论：禁 compat shim/胶水/tricky；根因修复，症状层补丁禁止。
- 修复后更新：`tasks_docs/PENDING_TASKS.md`（G3/BOUNDARY-G2 行标记已修复）、
  `NEXT_STEPS.md`、`HANDOFF.md`、`WORKLOG.md`。
- 本交接文件（`_HANDOFF_GENERICS_FIX.md`）修复完成后可归档删除。

---

## 六、相关文件索引

| 用途 | 路径 |
|------|------|
| 缺陷证据（G3） | `tasks_docs/_GENERICS_TRIAL_FIX_20260812/cases/R1-05-selfref-inherit.ibci` + `logs/R1-05-selfref-inherit.log` |
| 缺陷证据（G3 另一例） | `R5-01-core-regression.ibci` + 对应 log |
| 缺陷证据（BOUNDARY-G2） | `R5-04-combo-bomb.ibci` + `logs/R5-04-combo-bomb.log` |
| 正常对照（继承字段值正常） | `tests/runtime/test_serialization.py` / `tests/e2e/test_classes.py`（普通继承） |
| 正常对照（无继承特化字段正常） | `_GENERICS_TRIAL_FIX_20260812/cases/R1-01-selfref-basic.ibci` |
| 修复后应保持正常 | `_GENERICS_TRIAL_FIX_20260812/cases/R1-0{1,2,3,4}*.ibci`、`R2-*.ibci`、`R3-*.ibci`、`R4-*.ibci` |
| 泛型实现关键文件 | `core/runtime/objects/kernel/ib_class.py`（instantiate/字段收集） |
| | `core/runtime/interpreter/interpreter.py`（_hydrate_user_classes） |
| | `core/runtime/vm/handlers/leaf.py` + `_shared.py`（赋值/属性访问类型） |
| 设计记录 | `tasks_docs/PT_FEAT3_DESIGN.md`（泛型设计冻结 + 边界） |
