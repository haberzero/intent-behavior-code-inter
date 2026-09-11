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

## 增量序列（草案）

1. **增量 1：quoted + meta 模块原生面**（小垂直切片）：
   - `IbValue::Quoted { source: String }` 新变体 + clone/debug/比较/真值/类型名。
   - intrinsic 分发：`quote(s) → Quoted`；`eval(q) → parse(source) + exec`
     （Rust 原生闭环）；模块属性调用 meta.quote/meta.eval 经 intrinsic 面
     （called_module_functions 已追踪——解释器同规则）。
   - `q.source` 属性访问原生（Attribute 分支 Quoted 特判）。
   - 差分门：quoted_source / quoted_eval_value / quoted_eval_expr 语料数据面
     全级等价（3 语料 = eval 语义面完整探针）。
2. **增量 2：KB Rust 原生数据模型**（大面——世界模型核心，可能拆分
   2a facts/2b worlds/2c embeddings+vector 运算）：
   - Rust KB 结构体（事实三元组 / 词 / 世界 / 关系 / 向量）+ 41 成员方法面
     （向量运算 = 纯数学原生；embedding 端点 = Host IO 边界）。
   - 差分门：kb_world_vocab / kb_fact_lookup / kb_contradicts 语料数据面等价
     + KB 方法返回值跨内核比对。
   - vec intrinsic 顺带实现（vector 原生形态 = Vec<f64> 包装）。
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
