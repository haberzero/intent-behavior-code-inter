# 第四批设计：值对象去 Host 化（IbValue 值域封闭）

> 设计阶段临时任务控制文档（落地后按治理纪律收敛/删除）。
> 状态：设计完成，待增量 1 开工。日期：2026-09-11。

## 目标

Rust 执行面值域（`ibci-ext/src/interpreter.rs` 的 `IbValue`）消除 `Host(Py<PyAny>)`
变体——核心执行逻辑的值域封闭于 Rust 原生变体；Python 接口仅保留于
**LLM/意图 IO 边界**（HostService 桥接：embedding 端点 / LLM 调用 / 宿主资源）。
与 P9 终点裁定一致：保留关键部分 Python 接口（灵活性），证明绝大部分关键核心
逻辑可 Rust 化后全量转向 Rust。

## 现状盘点（2026-09-11 实勘）

**IbValue 8 变体**：7 原生（Int/Float/Str/Bool/None_/List/Dict）+ 1 Host。
值域已 ~75% 原生；`from_py` 边界转换器（bridge 结果 → 原生值）已就位
（bool 先于 int / list / dict 递归）。

**Host 残差面（15 处引用，4 类）**：
1. **KB 对象**（`knowledge()` intrinsic → bridge create_knowledge）——世界模型
   核心，41 成员（facts/worlds/words/relations/embeddings/vector 运算）。
2. **模块对象**（`import X` / `from X import Y` → get_host_module /
   host_getattr）——语料面仅 meta（quote/eval/compile 3 成员）。
3. **quoted**（q.source 经 host_getattr）——meta.quote 返回的宿主值。
4. **宿主方法/属性/比较/真值/类型名**（call_host_method / get_host_attribute /
   PartialOrd / is_truthy / type_name 的 Host 分支）。

**覆盖缺口（顺带登记）**：`vec([...])` intrinsic 未在 Rust 解释器实现
（值域无 vector 原生变体——vector 值当前经 from_py 以 List/Float 形态到达）；
34 语料无 vec 用例，非阻塞。

## 面分解与原生形态

| 面 | 原生形态 | 语义来源（单一权威源） |
| --- | --- | --- |
| quoted | `Quoted { source: String }`（+ source 字段访问原生） | meta.quote 声明：str → quoted；q.source → str |
| meta 模块 | 无独立值——quote/eval/compile 作为 intrinsic 直接分发（模块对象退役） | 函数签名表（eval[quoted]→any / quote[str]→quoted） |
| **eval 语义** | `meta.eval(q)` = 解析 q.source + Rust 解释执行（**parser + interpreter 原生闭环**——与 3b-2b-2 完整 artifact 闭环同构：source → artifact → 执行，全 Rust） | selfref R-A 地基（C3 起 selfref.verify 走 meta.quote 单点化） |
| KB | Rust 原生 KB 数据模型（facts 三元组 / worlds / words / relations / embeddings 向量 / 向量运算纯数学） | IBCI 公理层 KB 声明（41 成员表）+ Python KB 参照（差分门） |
| embedding IO | **保留 Host 边界**（Qwen3-Embedding 端点 = LLM IO——HostService 桥接） | 用户裁定：LLM/意图 IO 面保留 Python 接口 |

## 增量 3：Host 面收敛 + CPS 覆盖差收缩（进行中）

1. **增量 3a Host 面收敛**：meta/KB/quoted 全部去 Host 化后，宿主桥接（bridge.py /
   get_host_module / call_host_method / call_host_function / get_host_attribute）
   仅余 LLM/意图 IO 边界面（语料面零依赖）。`import meta` 的 Host 模块绑定经
   Call/FromImport 分发拦截后不再被值域消费（meta 模块对象退役为分发面标记）。
2. **增量 3b CPS 覆盖差收缩（31→36，2026-09-11）**：移植 5 节点（lexer
   switch/case/default token + parser[Global/Nonlocal/Raise/Switch + Case 节点] +
   deserializer[IbGlobalStmt/IbNonlocalStmt/IbRaise/IbSwitch/IbCase 节点数据] +
   node_serializer[节点内容——IbCase 位置 = switch 关键字位置[Python 序列化器
   约定，语料实证] + end 位置 = 0] + interpreter[global/nonlocal = 运行时 no-op
   [编译期语义]；raise = 异常对象求值[错误面：无异常传播机制，跨切面后续]；
   switch = 匹配后自动跳出[无 fall-through] + case 内 break no-op +
   Return/Continue 透传]）。差分门：test_data_plane_switch_global_snippets
   （3 探针：匹配/break/无 fall-through + continue 透传外层循环 +
   global/nonlocal no-op 读取面）+ switch 源 full_artifact 五池全等价实证。
   **声明面移植 ✅[2026-09-11 落地，3b 同批]**：`TYPE x = v` / `auto x = v` /
   泛型 `list[int] xs = v` / `TYPE x: TYPE2 = v` 显式覆盖——parser（声明面前瞻
   is_var_declaration + parse_declaration_identifier/auto + parse_type_annotation
   [泛型多参 = IbTuple]）+ AST（Expr::TypeAnnotatedExpr）+ node_serializer
   [IbTypeAnnotatedExpr 节点 + 声明 Assign 位置 end=0 + 绑定面：注解仅顶层节点
   node_to_type[泛型内层名字不单独绑定，ser_annotation 内层 None 记录] /
   annotated + 值节点 node_to_type = 声明类型[auto = 推导] / target name +
   annotated + Assign 节点 node_to_symbol → 定义符号] + symbol_resolver
   [声明类型优先，auto = 符号通道推导] + interpreter[声明 target = 运行时纯
   赋值，注解不消费] + deserializer。差分门：
   test_data_plane_declaration_snippets（数据面 + 5 池 + 2 侧表内容归一全等价；
   顶层 + 函数内 scope 双探针）。
   **登记缺口（非本增量范围）**：① 声明面剩余形态——`fn f = ...` 可调用声明 /
   元组解包 `(int x, int y) = t` / 点分类型 `mod.Type` / chan/slot 类型[LLM
   运行时面]；② LLM 面 15 节点覆盖差（IbCastExpr/IbRetry/
   IbIntentAnnotation/IbImplDef/IbProtocolDef/IbHostImport/IbBehaviorExpr/
   IbChannelExpr/IbAwaitExpr/IbYieldExpr/IbYieldFromExpr/IbFilteredExpr/
   IbSlotExpr/IbIntentStackOperation/IbWithOverlay——其中 IbCastExpr 语法复杂
   [类型注解消歧]，LLM/意图/宿主运行时面 = 协程/通道/行为深度语义，归 LLM 运行时
   移植批次；③ raise 错误面（异常传播机制 = 跨切面增量——try/except 捕获语义）。
   node_types = 36（handler 覆盖差 50-35 = 15——IbCase 为节点无独立 handler）。

## 增量序列（历史）

1. **增量 1：quoted + meta 模块原生面**（小垂直切片）✅[2026-09-11 落地]：
   - 实施 = `IbValue::Quoted { source }` + `IbValue::MetaFn(&'static str)` 变体
     （clone/debug/逐字节相等/repr[= source，同 __to_prompt__]/真值）+ Call 分发
     拦截（meta.quote/meta.eval 属性调用 + from-import 绑定名 → call_meta_fn 原生
     分发）+ q.source 原生属性 + FromImport meta 绑定 = MetaFn（非宿主属性）。
   - quote 验证门转录（HostService.quote_expression 契约）：非空 str + parse 语法 +
     单表达式[ExprStmt] + 自包含性[collect_refs_expr 自由名 ⊆ intrinsic 63——fresh
     scope 无用户绑定]。
   - eval 隔离执行（HostService.eval_quoted 契约转录）：fresh Environment（无用户
     全局）+ 值通道取回 + silent stdout 面丢弃。**进程级隔离 = 资源治理面，数据面
     语义等价 fresh scope 隔离**（裁定：语料零 LLM / 零跨进程状态依赖——记录于
     WORKLOG）。
   - 差分门：test_data_plane_quoted_native（quoted 4 语料**无桥接**原生闭环等价——
     bridge=None 证明 meta 函数面去 Host 化完成）+ 全 harness / smoke / 全量零回归。
   - 登记限制（非本增量范围）：验证门失败 / eval 运行错误面 = None_ 静默（Rust
     解释器无错误传播面——InterpreterError 值语义 = 跨切面后续增量；语料无错误
     探针，数据面无偏离）。
2. **增量 2：KB Rust 原生数据模型**（大面——世界模型核心）：
   - **2a 语料面 KB 值 ✅[2026-09-11 落地]**：ibci-ext/src/kb.rs（KbState 治理
     词表 + append-only 事实日志 + active 倒排索引 by_pair/by_triple——语义转录自
     Python knowledge.py 单一权威源；10 方法面 register_world/relation/word +
     worlds/words 枚举 + add_fact[治理门 allowlist + 去重] + exists + lookup_pair
     + contradicts）+ IbValue::Knowledge(Rc<RefCell<KbState>>) 共享可变容器
     （同 List/Dict 机制）+ knowledge() intrinsic 去桥接 + call_method 原生分发。
     差分门：test_data_plane_kb_native（KB 3 语料**无桥接**数据面等价）+
     full_corpus 全原生无桥接化。事实记录数据面形态对齐（键序 + 事件链 + None）。
     登记限制：错误面 None_ 静默（跨切面后续）/ 41 成员面未齐（2b/2c）/
     embedding 端点保留 Host IO 边界。
   - **2b 词表/事实查询面 + 审计/对比/展开/传递面 ✅[2026-09-11 落地]**：word/
     relation/world 查询[未注册 = None 合法态] + get_fact/facts[全日志 seq 序]/
     fact_len/all_in_world[active 视图]/source/history_fact[事件链] + amend_fact
     [o 版本化 + 事件链 + by_triple 切换] + retract[墓碑 + 事件链 + active 索引
     移除] + same_word/compare[确定性 4 层]/expand[纯派生：事实 + 词记录 + 关系
     语义 + 世界上下文 + 跨世界词形] + transitive[BFS 传递闭包 防环 + 确定性
     发现序 + via 中间链；非传递关系 = 空 list]。差分门：
     test_data_plane_kb_surface_snippets（25 行合成探针全对齐——语料集 3 条只
     覆盖基础面，合成探针 = 自包含脚本纪律）。
   - **2c embedding + vector 运算面 ✅[2026-09-11 落地]**：IbValue::Vector(Vec<f64>)
     不可变值[值语义相等；显示面 = 截断摘要 vector[<dim>](前 8 维 %.6g, ...，
     format_g6 = Python %.6g 等价助手[C %g 语义：6 位有效数字 + 科学/定点 +
     尾零截断]] + vec intrinsic[元素面数值校验] + 方法面[dim/dot/norm/cosine[
     零范数 fail-fast 面]/scale/add/sub 不可变返回新值/下标] + KB 嵌入面
     [set_embedding[维度全一致治理门：首个嵌入定维度] / embedding /
     has_embedding / embedding_dim / embed_search[暴力 cosine + (−score, word)
     确定性排序 + top-k 截断 + 维度不符跳过]]。差分门：
     test_data_plane_vector_surface_snippets（22 行合成探针全对齐——%.6g 全形态
     [科学/定点/负指/尾零] + 浮点最短往返 repr + 排序 tie-break）。
     **裁定**：vector.cast_to 目标 = 类对象（`v.cast_to(str)` 的 str 经 VM 类型
     名解析为 class——值域无类对象面，执行面不可达 = 类型面职责；用户调用
     cast_to("str") = 非法 IBCI[Python 参考 fail-fast 实证]）→ 执行面 dispatch
     不含 cast_to（死代码红线）。embedding 文本端点（ai.embed）= LLM IO 边界
     保留（HostService；语料面零依赖）。
   - 差分门：kb_world_vocab / kb_fact_lookup / kb_contradicts 语料数据面等价
     + KB 方法返回值跨内核比对。
3. **增量 3：Host 变体退役**：
   - 执行面 Host 分支全删（比较/真值/类型名/方法/属性——仅 LLM/意图 IO 边界
     保留 bridge 委托，值不进入 IbValue 值域[边界值即过即转]）。
   - import 面：语料面仅 meta（已 intrinsic 化）——用户模块面 = 后续
     （宿主模块 = LLM/意图 IO 资源，边界保留）。
   - 全量 pytest + 34 语料数据面全级差分零回归（放行门）。

## 红线与裁定（self-grill 消解）

1. **KB 语义单一权威源**：Rust KB 数据模型转录自 IBCI 公理层 KB 声明（与
   第三批 66 类型表 / 223 方法签名表同模式）；Python KB = 差分参照（安全网），
   非真相源。
2. **eval 原生闭环 = 机制同构**：source → Rust parser → Rust artifact →
   Rust interpreter（与 Python 前端产物执行同语义）——不发明新求值器；
   quoted 源码 = 任意合法 IBCI 源（语义面 = 主解释器同面，无子集裁剪）。
3. **embedding = LLM IO 边界保留**：端点调用（网络 + 模型）经 HostService
   桥接——用户裁定面，不进值域去 Python 化范围。
4. **迁移期差分门**：每增量 = 受影响语料数据面全级差分（token/AST/反序列化/
   数据面 + artifact 五池）零差异放行。
5. **bound_method last-wins**（第三批再发现的 Python 非 canonical 行为）不属
   本批次范围（artifact 面已对齐）；KB 面的同类问题（KB 对象状态跨调用
   可变性）在增量 2 设计时核查。

## 验证面

- 数据面差分：tests/diff_harness（34 语料全级——quoted 3 语料 + kb 3 语料
  为本批次重点探针）。
- smoke：tests/contracts + tests/compiler。
- 全量 pytest：增量放行门 + 第三/四批边界门。
