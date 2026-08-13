# REGISTER — 泛型修复回归试用结果寄存器

> 2026-08-12。重点检测最近泛型修复（G1 方法体 / G2 自引用 / BOUNDARY-G1 非法实参 /
> 双通道 descriptors）成果。每例一行：用例 / 期望 vs 实际 / 分类 / 级别 / 证据日志。
> 分类：PASS | KERNEL_ISSUE | BOUNDARY | GUARD（守卫生效）。
> 全部经死循环保护 harness（进程组 SIGKILL + --max-inst + timeout）；31 用例 + 1 冒烟，
> 唯一 TIMEOUT-KILLED 为死循环保护冒烟验证本身。
> **规范（2026-08-13 迁移）**：本套现位于 `trials/T04_generics_fix_regression/`；分类/级别/编号
> 规范见 `trials/_toolkit/CLASSIFICATION.md`。缺陷编号已映射为新格式（见文末"编号映射"节）。
> **用例修正（2026-08-13）**：R1-05/R5-01 适配 G3 修复后 chain-aware auto-init 语义
> （多参构造）；R5-04 适配（None 哨兵不可行 → 固定次数遍历 + Box 简化规避 GEN-5）。

## 结果总览

- **用例总数**：31 个用例 + 1 冒烟；32 次 harness 运行；全部经死循环保护。
- **修复成果验证（PASS）**：G1 方法体类型参数（R2 全组含嵌套/多参数/交替/生成器/深层）、
  BOUNDARY-G1 非法实参守卫（R3 全组含 None/void/auto/嵌套/正向/thread[void]）、
  双通道 descriptors（R4 全组含嵌套/多参数/继承）、G2 自引用基础（R1-01~04）。
- **发现缺陷（2 项，均非本次修复引入，试用暴露）**：
  - **KERNEL-ISSUE-G3（P1）**：继承特化 + 父类字段值丢失——`class Linked[T](Node[T])`
    → `Linked[int](5).get()` 返回 None（R1-05/R5-01）。**已用 git worktree 在修复前
    （35bb2de）复现**，确认是 PT-FEAT-3 落地既有缺陷，非本次修复引入。
  - **BOUNDARY-G2（P2）**：自引用链 while 遍历 `cur = cur.next` + `cur.get()` 运行时
    `cur` 类型退化 any → AttributeError（R5-04）。运行时类型跟踪问题（非本次修复）。

## 逐例明细

| case_id | 目标 | 期望 | 实际 | 分类 | 级别 |
|---------|------|------|------|------|------|
| R1-01 | G2 自引用字段基础 | 正确 | ✅ n1=1 next=2 | PASS | - |
| R1-02 | G2 自引用链遍历 | 正确 | ✅ h=1 m=2 t=3 | PASS | - |
| R1-03 | G2 递归特化 Node[Node[int]] | 正确 | ✅ inner=9 | PASS | - |
| R1-04 | G2 自引用+容器 | 正确 | ✅ a=1 b=2 len=2 | PASS | - |
| R1-05 | G2 自引用+继承 | 正确 | ❌ d1=A:None d2=None | KERNEL_ISSUE-G3 | P1 |
| R2-01 | G1 方法体构造 int/str | 正确 | ✅ v=2 s=b | PASS | - |
| R2-02 | G1 方法体返回+访问 | 正确 | ✅ r=2 | PASS | - |
| R2-03 | G1 Box[list[int]] 方法体 | 正确 | ✅ len=3 first=1 | PASS | - |
| R2-04 | G1 Box[dict[str,int]] 方法体 | 正确 | ✅ key=2 | PASS | - |
| R2-05 | G1 Box[Box[int]] 方法体 | 正确 | ✅ inner=8 | PASS | - |
| R2-06 | G1 Pair[A,B] 方法体 | 正确 | ✅ qk=2 qv=k | PASS | - |
| R2-07 | G1 T 局部变量/表达式 | 正确 | ✅ r1=9 r2=y | PASS | - |
| R2-08 | G1 生成器方法 Box[T] | 正确 | ✅ sum=15 | PASS | - |
| R2-09 | G1 深层嵌套实参 | 正确 | ✅ len=1 inner=2 | PASS | - |
| R2-10 | G1 交替特化调用 | 互不污染 | ✅ bi=2 bs=s2 blen=2 | PASS | - |
| R3-01 | 字面量 Box[42] 拦截 | 守卫 | ✅ SEM_GENERIC_TYPE_NEEDS_ARGS | GUARD | - |
| R3-02 | Box[None] 注解拦截 | 守卫 | ✅ SEM_GENERIC_TYPE_NEEDS_ARGS | GUARD | - |
| R3-03 | Box[void] 用户泛型拦截 | 守卫 | ✅ SEM_GENERIC_TYPE_NEEDS_ARGS | GUARD | - |
| R3-03b | thread[void] 放行 | 放行 | ✅ w DONE | PASS | - |
| R3-04 | Box[auto] 拦截 | 守卫 | ✅ SEM_GENERIC_TYPE_NEEDS_ARGS | GUARD | - |
| R3-05 | 嵌套非法 Box[list[None]] | 守卫 | ✅ SEM_GENERIC_TYPE_NEEDS_ARGS | GUARD | - |
| R3-06 | 合法实参正向 | 正确 | ✅ bi=1 len=2 pb=3 | PASS | - |
| R4-01 | Box[int].set("str") 负例 | 拦截 | ✅ SEM_TYPE_MISMATCH | GUARD | - |
| R4-02 | Box[list[int]].set("str") 负例 | 拦截 | ✅ SEM_TYPE_MISMATCH expected list[int] | GUARD | - |
| R4-03 | Box[dict[str,int]] 参数 | 正确 | ✅ key=2 | PASS | - |
| R4-04 | Pair[A,B] 参数检查 | 正确 | ✅ a=hi b=7 | PASS | - |
| R4-05 | 继承特化参数检查 | 正确 | ✅ v=5 | PASS | - |
| R5-01 | 核心回归 | 正确 | ❌ sub=NoneL（G3） | KERNEL_ISSUE-G3 | P1 |
| R5-02 | 序列化 round-trip | 保真 | ✅ before=11 | PASS | - |
| R5-03 | 并发/生成器/闭包 | 正确 | ✅ chan=5 gen_sum=3 closure=15 | PASS | - |
| R5-04 | 组合轰炸 | 不崩 | ❌ cur 退化 any → AttributeError | BOUNDARY-G2 | P2 |
| SMOKE | 死循环保护 | SIGKILL | ✅ 5s 被杀 | PASS | - |

## 缺陷登记（PENDING_TASKS，不修复）

- **KERNEL-ISSUE-G3（P1）**：继承特化 + 父类字段值丢失。`class Linked[T](Node[T])`
  → `Linked[int](5)` 构造后 `data` 字段为 None（`get()` 返回 None）。**已用 git worktree
  在修复前（35bb2de）复现**，确认 PT-FEAT-3 既有缺陷，非本次修复引入。根因方向：继承
  特化类（Linked[int]）的字段绑定/hydration——父类 Node 字段在特化继承链上未正确初始化。
  影响：继承特化的字段值全部丢失（严重）。
- **BOUNDARY-G2（P2）**：自引用链 while 遍历 `cur = cur.next` 后 `cur.get()` 运行时
  `cur` 类型退化 any → AttributeError。运行时类型跟踪问题（`cur.next` 自引用字段回写
  变量后类型信息丢失）。

## 编号映射（2026-08-13 规范化，见 `trials/_toolkit/CLASSIFICATION.md`）

| 旧编号 | 新编号 | 状态 |
|--------|--------|------|
| KERNEL-ISSUE-G3（继承特化父类字段丢失） | `KERNEL_ISSUE-GEN-4` | **已修复（2026-08-13 b0f4d74）**：交接诊断纠偏后根治（chain-aware auto-init），见 PENDING_TASKS |
| BOUNDARY-G2（自引用链 while"类型退化"） | `BOUNDARY-GEN-2` | **已修复（2026-08-13 b0f4d74）**：用例无效 + Finding C 根治，见 PENDING_TASKS |
| （2026-08-13 新发现，R5-04 Box 部分） | `KERNEL_ISSUE-GEN-5` | 待修复（嵌套内置泛型实参特化注册缺失，独立窗口） |

## 修复成果结论

- **G1 方法体类型参数修复完全验证**：标量/嵌套/多参数/交替/生成器/深层嵌套全 PASS，零死循环。
- **BOUNDARY-G1 守卫修复完全验证**：None/auto/void（按 base）/字面量/嵌套全拦截，
  thread[void] 与合法特化放行。
- **双通道 descriptors 修复完全验证**：标量/嵌套/多参数/继承参数类型检查精确。
- **G2 自引用字段修复基础验证**：字段特化替换正确（R1-01~04）；但继承组合暴露 G3
  （既有缺陷，非本次引入）。
