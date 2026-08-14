# 设计分析：`fn[(...) -> ...]`（CALLABLE_SIG）签名模型的架构碎片化与根治

> 2026-08-14 编制。触发：KNOWN_LIMITS §10.4"fn 签名内嵌套泛型实参（潜伏边界）"深挖——
> 用户指出其与"泛型实现时间较晚"的类型系统问题相关，要求架构级分析与修复方案。
> 本文件为**设计阶段文档**（任务控制层）；修复落地并验证后收敛入 docs/。

## 〇、重新汇报 KNOWN_LIMITS §10.4（现状）

`fn[(list[int]) -> int]` / `fn[(Box[int]) -> int]` 等**签名内部**的嵌套泛型实参：
- 编译期构造按**名称保真**（`TypeRef.of(p.name)` → `TypeRef('Box[int]')`，head 含方括号、
  args 空——扁平形态）。
- 常规消费（`apply(get_len, [1,2,3])`、`apply(get_data, Box[int](7))`）经注册表**名称
  回绕**仍正确（q6/q9 实证）。
- 原记录"仅当对签名内实参执行结构化操作（TypeRef.substitute）时扁平形态无法穿透"。

**本次深挖实证：该边界不只是"结构化操作不可穿透"的潜伏问题，而是真实类型安全漏洞**
（见 §二）。

## 一、架构级根因（三层碎片化）

`fn[(...) -> ...]`（CALLABLE_SIG）是"精确签名约束"类型，但其构造/替换/重建/匹配
**四处不一致**——同一签名在三处有不同表示：

| 环节 | 实现 | 表示 |
|------|------|------|
| 构造 | `_type_checking_base:367` / `symbol_resolution_pass:371` `TypeRef.of(p.name)` | **扁平** `TypeRef('Box[int]')`（head 含括号、args 空） |
| 替换 | `TypeRef.substitute` | 扁平不可穿透 → 嵌套 `Box[T]` 内的 `T` **不替换** |
| 重建 | `resolve_typeref` fn 分支 `TypeRef.of(a.head)` | **再扁平化** |
| 序列化往返 | serializer canonical_name + rehydrator TypeRef.parse | **结构化**（唯一保真处） |

同一签名的"扁平 → 结构化 → 扁平"三态漂移，违反 design-philosophy §一（单一权威源）：
`fn` 签名类型身份没有单一权威构造/解析入口。这与"泛型地基后未同步升级"的断层模式
完全同源（fn/callable 早期字符串级设计，泛型 TypeRef 结构化落地后构造/匹配未跟随）。

## 二、实证的两个真实漏洞（超出 §10.4 原记录）

### 漏洞 1：CALLABLE_SIG 参数匹配双通道——逐参数类型不检查
- `_matches_callable_sig`（is_assignable 路径，`_assignability.py:133-168`）只查
  **参数数量 + 返回类型**，**不查逐参数类型**。
- `_check_callable_sig_match`（声明/赋值路径，`_statement_visitors.py:329-375`）
  查**数量 + 逐参数 + 返回**（全量）。
- 结果：`func apply(fn[(Box[int]) -> int] cb, ...)` 传 `get2(str)->int`（参数类型不符）
  **编译期放行**，运行期 `RUN_TYPE_MISMATCH`（实证）。这是**双通道/双实现**（同一
  决策两套匹配逻辑），且是类型安全洞。

### 漏洞 2：嵌套类型参数不替换 → "不可解析 → 检查静默跳过"
- `class Host[T]: func apply(self, fn[(Box[T]) -> int] cb, Box[T] b)` 特化 `Host[int]`
  后，`cb` 描述符签名内 `Box[T]` 因扁平（`TypeRef('Box[T]')` head 含括号、args 空）
  **不被 substitute 替换**。
- 调用点 `expected_names=["Box[T]"]` → `resolve("Box[T]")` 命中 None → **逐参数检查被
  静默跳过**（非"放行"，是"未检查"）。
- 实证：`Host[int].apply(get2(str)->int, ...)` 编译放行、运行期才报错——即使漏洞 1
  修复，嵌套 T 场景仍因"解析 miss → 跳过"而漏检（fail-fast 纪律违反：code-quality
  静默回退/能力探测红线）。

## 三、为什么与"泛型实现较晚"直接相关

- fn/callable/CALLABLE_SIG 是 IBCI 最早期的能力之一，建模于**字符串级 TypeRef** 时代。
- 泛型地基（TypeRef 结构化 + 特化 + substitute）落地后，**签名的构造/匹配路径未跟随
  升级**——与第一轮修复的 create_func/resolve_member 同一断层，只是落在
  `fn[(...)]` 签名构造与匹配路径上（第一轮修复聚焦函数/成员回填，未覆盖此处）。
- `_check_callable_sig_match` 用 `resolve(exp_name)`（按 head 名解析）匹配，天然假设
  "参数类型是简单名"——结构化实参（`Box[int]`）一旦以结构化形态出现（head="Box"），
  该假设即破坏。这是"设计假设未随泛型演进"的直接证据。

## 四、修复方案（架构级，单一权威源收敛）

### 目标
`fn[(...) -> ...]` 签名模型统一为**结构化单一权威**：构造结构化、替换可穿透、
重建保真、匹配单实现。

### 四项（依赖驱动）

1. **结构化构造**：`_type_checking_base` + `symbol_resolution_pass` 的 CALLABLE_SIG
   构造改用 `TypeRef.from_spec(p)` / `TypeRef.from_spec(ret_spec)`（from_spec 已覆盖
   CALLABLE_SIG 分支，产出 `fn[(args)->ret]` 结构化形态）——替代 `TypeRef.of(p.name)`
   扁平化。
2. **结构化重建**：`resolve_typeref` fn 分支保留嵌套实参（参数直接用 ref.args 原样，
   不 `TypeRef.of(a.head)` 再扁平）；返回类型同理。
3. **统一匹配（收敛双通道）**：`_matches_callable_sig` 补逐参数类型检查（与
   `_check_callable_sig_match` 对齐），或令 `_check_callable_sig_match` 委托
   `_matches_callable_sig`（单一实现）；两者参数/返回类型解析改 `resolve_typeref`
   （结构化）而非 `resolve(head)`。
4. **静默跳过 fail-fast**：签名参数类型解析 miss（如未特化占位）不再静默跳过——
   显式报错或按动态放行并记录（fail-fast 纪律）。

### 连带核验
- 序列化往返：serializer 已 canonical_name + rehydrator TypeRef.parse（嵌套保真），
  与结构化构造一致；核验 round-trip 后结构化保真。
- q6/q9（`fn[(list[int])->int]` / `fn[(Box[int])->int]` 常规消费）保持。
- 判别性回归新增：`apply(get2(str)->int, ...)` 编译期 SEM（漏洞 1）；`Host[int].
  apply(get2, ...)` 编译期 SEM（漏洞 2）；`fn[(T)->int]` / `fn[(Box[T])->int]` 泛型
  特化后替换正确、匹配正确。
- 现有测试中"签名不匹配放行"的宽松用例（若有）反转。

### 风险
- 行为变更：CALLABLE_SIG 参数/声明的逐参数类型检查从"跳过"变"强制"——对
  已接受的错误签名会改为编译期拒绝（正确性改进，方向与文档承诺"签名约束"一致）。
- 改动面：构造 2 处 + resolve_typeref 1 处 + 匹配 2 处（双通道收敛）+ 测试迁移。
  属架构级（CALLABLE_SIG 模型），独立分支 + 全量 pytest + 独立复核。

### 已知残留（本方案范围外，保持记录）
- `list[fn]` 容器元素级强制可调用未接线（独立于签名模型）。
