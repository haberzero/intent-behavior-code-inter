# 17. 一等环境对象（environment）

> `environment` 是 IBCI 的一等内置值类型：可快照、可嵌套的作用域化键值
> 环境。面向需要跨调用携带执行上下文（模式/世界/话语状态等）的灰盒自动机
> 场景。与 `intent_context`（意图上下文——提示词注入专用）平行：
> `intent_context` 承载 LLM 意图栈，`environment` 承载一般键值环境状态。

## 17.1 语义不变量

- **frames 栈**：环境由帧序列构成（最内层帧在尾部）。读（`get`）**自内向外
  查找**——内帧遮蔽外帧（shadowing）；写（`set`/`pop`）作用于最内层帧。
- **值隔离**：`set` 入的值深拷贝存储、`get`/`pop` 出时深拷贝返回——读写
  双向隔离，外部容器变异不污染环境内值，环境内值变异不污染外部容器
  （与 knowledge 条目冻结快照同一纪律）。
- **快照**：`fork()` = 深拷贝（帧 + 值双向隔离）。快照与原件互不影响——
  定义时快照/序列化水化的状态语义基础。
- **use 替换**：`environment.use(env)` 以 `env` 的 **fork 副本**替换当前
  帧环境（非引用绑定——与 `intent_context.use` 同构；原实参不受后续变异
  影响）。
- **当前环境**：经帧级持有（RuntimeContext）。`environment.get_current()`
  返回当前环境的 fork 快照（新实例——可检查、可保存，不影响当前帧）。

## 17.2 方法面

```ibci
environment e = environment()      # 构造：空环境（单空帧）

# 静态面（类型名调用）
environment cur = environment.get_current()   # 当前环境快照（fork）
environment.use(e)                            # 以 e 的 fork 副本替换当前环境

# 实例面
any    v   = e.get(key)      # 内→外查找（遮蔽）；缺失 = None
void   r   = e.set(key, val) # 最内层帧写入（值深拷贝隔离）
any    p   = e.pop(key)      # 自内向外移除并返回；缺失 = None
void   c   = e.clear()       # 清空全部帧
environment f = e.fork()     # 深拷贝快照
int    n   = e.len()         # 键数（遮蔽去重后）
bool   has = e.contains(key) # 任一帧含键
list   ks  = e.keys()        # 全部帧键并集（内→外序，去重）
```

## 17.3 边界与限制

- **值类型**：帧值以原生形态存储（`any`）。用户类实例值经 `to_native`
  结构降级存储（读回为原生容器结构，非原类实例）——需要用户类身份保真的
  场景应直接持有类实例变量，而非存入环境。
- **序列化**：`save_state`/`load_state` 保真 environment 实例（frames 键值
  + 嵌套容器值）；水化后实例身份共享（池引用），与 intent_context 序列化
  同构。
- **无隐式路由**：environment 是普通值——引擎不提供任何"环境命中则跳过
  LLM"的隐式语义（`@~...~` 语义不变量，同 knowledge 铁律）。

## 17.4 与 intent_context 的关系

| 面 | intent_context | environment |
|---|---|---|
| 定位 | LLM 意图栈（提示词注入专用） | 一般键值环境（执行上下文） |
| 值 | 意图（string，带 mode/role 元数据） | 任意原生值（any） |
| 帧语义 | 意图栈（push/pop 栈顶） | frames 栈（内帧遮蔽外帧） |
| 快照 | `fork()` | `fork()`（同构） |
| 替换 | `intent_context.use(ctx)` | `environment.use(env)`（同构） |
| 序列化 | save/load 保真 | save/load 保真（同构） |

二者平行、不互相替代：意图注入路径（`@+`/`@-` 语法 + LLM 调用意图层）
保持 intent_context 单一权威；一般执行上下文用 environment。
