# REGISTER — 用户类泛型参数压力/恶意试用结果寄存器

> 2026-08-12。每例一行：用例 / 文档引用 / 期望 vs 实际 / 分类 / 严重级别 / 证据日志。
> 分类：PASS | KERNEL_ISSUE | BOUNDARY | GUARD（守卫生效）。
> 级别：P0（崩溃/死循环）/ P1（明确缺陷，重要语义错误）/ P2（缺陷，较轻）/ P3（文档/体验）。
> 全部经死循环保护 harness（进程组 SIGKILL + --max-inst + timeout）；30 次运行，唯一
> TIMEOUT-KILLED 为死循环保护冒烟验证本身。

## 结果总览

- **用例总数**：29 个用例 + 1 冒烟；30 次 harness 运行；全部经死循环保护。
- **PASS**：23 例（D1 全组 + D2 大部分 + D3 大部分 + 守卫生效）。
- **KERNEL_ISSUE（真实缺陷，2 项同根因）**：
  - **KERNEL-ISSUE-G1**：泛型类**方法体内自引用**（返回类型 `-> Box[T]` 或构造 `Box[T](v)`）
    特化替换缺失——编译期报 `Cannot assign 'Vec' to 'Vec[int]'`（D2-01），运行期报
    `Variable UID 'Box:T' is not defined`（隔离探针 t1）。根因：`_substitute_members`/
    特化替换未覆盖方法体 AST 内对自身泛型类的引用（仅替换成员表类型，未替换方法体内
    `Vec[T]` 表达式）。
  - **KERNEL-ISSUE-G2**：泛型类**自引用字段** `Node[T] next` 特化后不可赋值——报
    `Cannot assign 'Node[int]' to 'Node[T]'`（D3-04）。同根因：自引用字段 `next` 的
    `type_ref=Node[T]` 在特化时未替换为 `Node[int]`（`_substitute_members` 对字段
    `Node[T]`——head=Node 非 T，args=(T,)——替换应递归，但实际未生效）。
  - **影响**：链表/树/迭代器/工厂方法等"泛型类自引用"常见模式不可用。**P1**。
- **BOUNDARY（边界，1 项）**：
  - **BOUNDARY-G1**：非法特化实参（`Box[42]`/`Box[None]`）编译期**未拦截**，运行期抛裸
    `AttributeError`（非诊断码）（D3-02/D3-02b）。守卫应前置到编译期报 SEM。**P2**。
- **GUARD（守卫生效，确认是特性）**：D3-01（SEM_GENERIC_TYPE_ARG_COUNT）/ D3-03
  （shadows 内置）/ D3-05（继承特化 fail-fast）/ D3-06（类型隔离）。
- **零死循环**：唯一 TIMEOUT-KILLED 为冒烟验证本身。

## 逐例明细

| case_id | 目标 | 期望 | 实际 | 分类 | 级别 |
|---------|------|------|------|------|------|
| D1-01 | 基础特化 int/str/float/bool | 正确 | ✅ 全特化正确 | PASS | - |
| D1-02 | 多参数 Pair/Triple | 正确 | ✅ 按序映射 | PASS | - |
| D1-03 | 嵌套实参 Box[list[int]] 等 | 正确 | ✅ 嵌套身份保持 | PASS | - |
| D1-04 | 全使用面（字段/参数/返回/局部） | 正确 | ✅ 全位置替换 | PASS | - |
| D1-05 | 特化方法参数类型检查 | 通过 | ✅ int 匹配 | PASS | - |
| D1-06 | 运行时身份 type()/cast | 正确 | ✅ type=Box[int]、cast 恢复 | PASS | - |
| D1-07 | 序列化 round-trip | 保真 | ✅ before=77 | PASS | - |
| D2-01 | 泛型×运算符（__add__ 返回 Vec[T]） | 正确 | ❌ `Cannot assign 'Vec' to 'Vec[int]'` | KERNEL_ISSUE-G1 | P1 |
| D2-02 | 多级继承链 | 正确 | ✅ all=123 | PASS | - |
| D2-03 | 泛型×协议（__call__/__iter__） | 正确 | ✅ r1=5 r2=8 | PASS | - |
| D2-04 | 泛型×容器（dict/tuple/list 值） | 正确 | ✅ 全容器通过 | PASS | - |
| D2-05 | 泛型×控制流（for/switch/if） | 正确 | ✅ sum=6 case_on | PASS | - |
| D2-06 | 泛型×函数参数/返回 | 正确 | ✅ r=55 s=hello | PASS | - |
| D2-07 | 泛型×并发（chan/thread/slot） | 正确 | ✅ chan=5 thread=in_thread slot=9 | PASS | - |
| D2-08 | 泛型×生成器 | 正确 | ✅ sum=6 | PASS | - |
| D2-09 | 泛型×行为（mock LLM 赋值/异常） | 正确 | ✅ llm_val=42 异常捕获 | PASS | - |
| D2-10 | 泛型×闭包（lambda 捕获/调用） | 正确 | ✅ r1=15 r2=42 | PASS | - |
| D2-11 | 泛型×多文件 import | 正确 | ✅ pop=2,1 | PASS | - |
| D3-01 | 实参数不匹配 | 守卫 | ✅ SEM_GENERIC_TYPE_ARG_COUNT | GUARD | - |
| D3-02 | Box[42] 非法实参 | 应 SEM | ❌ 编译过+运行期裸 AttributeError | BOUNDARY-G1 | P2 |
| D3-02b | Box[None] 非法实参 | 应 SEM | ❌ 同上 | BOUNDARY-G1 | P2 |
| D3-03 | 类型参数遮蔽内置 | 守卫 | ✅ shadows 报错 | GUARD | - |
| D3-04 | 自引用字段 Node[T] next | 应可用/明确报错 | ❌ `Cannot assign 'Node[int]' to 'Node[T]'` | KERNEL_ISSUE-G2 | P1 |
| D3-05 | 非泛型子类继承特化 | 守卫 | ✅ fail-fast | GUARD | - |
| D3-06 | 特化类型隔离 | 守卫 | ✅ Cannot assign Box[int]→Box[str] | GUARD | - |
| D3-07 | 运行时特化表达式 | 正确 | ✅ r=5 | PASS | - |
| D3-08 | 组合轰炸（嵌套+容器+控制流） | 不崩 | ✅ total=3 m_len=2 | PASS | - |
| D3-09 | 退化形态（空/仅方法） | 可用 | ✅ empty_ok om=pong | PASS | - |
| D3-10 | 泛型×LLM 交叉（mock） | 正确 | ✅ c1=7 preserved=orig | PASS | - |
| SMOKE | 死循环保护冒烟 | SIGKILL | ✅ 5s 被杀 | PASS | - |

## 缺陷登记（PENDING_TASKS，不修复）

> 2026-08-12 深度核验后修正：G1/G2 原判"单根因"不准确，实为**两个独立缺陷**（不同层：
> G2 编译期类型系统扁平化、G1 运行期符号解析）。另补一项复核 H1 引入的双通道设计缺陷。

- **KERNEL-ISSUE-G2（编译期，P1）**：泛型类自引用字段 `Node[T] next` 特化替换失效。根因链：
  `_resolve_annotation` → `resolve_specialization(Node,[T])` 创建 `Node[T]` 特化 spec →
  `from_spec` CLASS fallback 扁平化为 `TypeRef('Node[T]')` → substitute 无法替换。`from_spec`
  扁平化是既有行为（type_ref.py 零改动），用户类泛型首次触发。修复方向已验证：结构化
  `TypeRef('Node',(TypeRef('T'),))` 可被 substitute 正确替换。
- **KERNEL-ISSUE-G1（运行期，P1）**：泛型方法体内 `Box[T]`（slice T 为类型参数）运行时
  `vm_handle_IbName` 查变量失败（`Box:T` UID 未注册）。编译期语义正确；纯运行期类型参数
  表达式求值缺失。修复方向：slice T 解析为类型标识（对齐 `Box[int]` slice int 求值为 IbClass）。
- **BOUNDARY-G1（P2）**：`Box[42]`/`Box[None]` 编译期未拦，运行期裸 AttributeError。
- **双通道设计缺陷（P2，深度核验新增）**：`_substitute_members`（真实 mapping）与
  `_sync_specialized_members`（字符串反推 mapping）两套 descriptors 替换实现，违反机制同构。
