# 文件容器与磁盘型存储子系统

> 本文档描述 IBCI 磁盘型文件容器的完整设计：协议族、类型继承、生命周期管理、与快照/序列化/LLM 调用的交互。
> 读者对象：需要理解或扩展文件/媒体类型系统的开发者。

---

## 一、设计原则

### 协议驱动分发

变量如何参与快照、序列化，由分发到该类型公理实现的协议方法决定。禁止在 executor / strategy / deep_clone / 序列化器里查询能力标志位做 `if/else`：

| 调用方 | 分发入口 | 协议方法 |
|---|---|---|
| `deep_clone` | `receive("__clone_ref__")` | 磁盘型返回路径引用拷贝（浅、廉价），内存型深拷贝字节 |
| 序列化器 | `receive("__to_descriptor__")` | 输出路径引用描述符 |
| 反序列化器 | `receive("__from_descriptor__")` | 从描述符重建 handle |

调用方代码存储模型无关；新增磁盘型类型不需要改动 executor / strategy / deep_clone / 序列化器一行代码。

### 只读容器语义

`file_handle` 实例没有 `write()` 方法。所有写入必须通过 `file` 模块的自由函数显式完成。这保证了容器身份的不可变性——持有同一 handle 的多处引用始终指向同一路径。

### 零 I/O 公理层

公理层（`FileHandleAxiom`）不导入 `os`、`base64`、`open`。所有 I/O 在运行时值类中实现。公理层仅声明类型契约与方法签名。

---

## 二、类型继承体系

```
IbValue (core/runtime/objects/kernel/)
  └── IbFileHandle (core/runtime/objects/file_handle.py)
        ├── IbAudio (core/runtime/objects/media_types.py)
        ├── IbImage
        └── IbVideo
```

- `IbFileHandle`：磁盘型基类，持有一个 `MediaBacking` 实例（通过 `payload` 字段）和 `fields["path"]`（装箱的路径字符串）。
- `IbAudio` / `IbImage` / `IbVideo`：继承 `IbFileHandle`，各自覆写 `__path_payload_prompt__()` 以生成对应模态的 LLM content block。

公理层继承关系：`AudioAxiom` / `ImageAxiom` / `VideoAxiom` 均声明 `get_parent_axiom_name() -> "file_handle"`。

`IbMedia` 不是现有类型（全模态聚合容器为未来设计），当前 `IbFileHandle` 持有单一 `MediaBacking`。

### 类型注册与门控

`file_handle` / `audio` / `image` / `video` 为普通类名（非 lexer 关键字），通过 `file` 模块的 `exported_types` 机制注入：`import file` 时 scheduler 把这四个类型名作为符号同时注入当前作用域。

---

## 三、Backing 模型

所有磁盘型变量通过 `MediaBacking` 抽象基类持有路径引用。`MediaBacking` 仅持有一个 `IbPath`，不持有字节，不持有 OS 文件描述符。

| Backing 类型 | 语义 | 来源 |
|---|---|---|
| `FileBacking(path, sandboxed)` | 指向已存在的源文件 | `file.open()`、`audio.from_file()` 等 |
| `GeneratedBacking(path)` | 指向 LLM 生成时溢写的工件，恒在 project_root 内 | LLM 响应解析溢写 |

不存在 `MemoryBacking`——所有媒体类型一律磁盘型。

---

## 四、磁盘型协议族

磁盘型类型实现一组与 `__prompt__` 协议族平行的协议方法：

| 协议方法 | 职责 |
|---|---|
| `__materialize__` | 惰性物化（按需从路径读字节） |
| `__path_payload_prompt__` | 基于路径的 LLM payload 构建（返回 content block dict） |
| `__clone_ref__` | 路径引用的快照（浅、廉价，不物化字节） |
| `__to_descriptor__` | 路径引用的序列化（输出 `{"path": ..., "backing_type": ...}`） |
| `__from_descriptor__` | 路径引用的反序列化（从描述符重建 handle） |

`__prompt__` 协议族（`__to_prompt__` / `__from_prompt__` / `__outputhint_prompt__` / `__payload_prompt__`）继续作为内存型类型的 I/O 协议；两族不互相混合。

### 各媒体类型的 payload 输出

| 类型 | `__path_payload_prompt__` 返回 |
|---|---|
| `file_handle` | `{"type": "text", "text": "[file_handle: <path>]"}` |
| `audio` | `{"type": "input_audio", "input_audio": {"data": <base64>, "format": <fmt>}}` |
| `image` | `{"type": "image_url", "image_url": {"url": "data:<mime>;base64,..."}}` |
| `video` | `{"type": "video", "video": {"data": <base64>, "format": <fmt>}}` |

---

## 五、与快照隔离的交互

### deep_clone 分发

`try_deep_clone`（`core/runtime/objects/deep_clone.py`）检查类型级 `storage_model`：

- 若 `spec.storage_model is StorageModel.DISK_BACKED` → 短路到 `val.receive("__clone_ref__", [])`，返回路径引用的浅拷贝
- 否则走内存型深克隆级联

磁盘型对象的快照/恢复不物化字节，仅复制路径引用。

### llmexcept 约束

`llmexcept` 快照保存的是路径引用的浅拷贝。retry body 中调用任何文件写/删都会污染黄金快照（写新文件若路径撞上已有 backing 同样污染；删除则令 handle 悬空）。因此 retry body 内**禁止全部写/删函数**，采用编译期 + 运行时双层防护：

- **编译期**（`SEM_LLMEXCEPT_FILE_WRITE`）：spec 驱动判定--retry body 内直接或经用户函数间接调用 `file.<写/删>` 即报错。判定读 module spec 成员的 `mutating` 标记，正确处理 `import file as f` 别名与局部变量 shadowing。间接调用经 `func_sym.owned_scope` 作用域感知递归传导（含调用图环路保护）。
- **运行时**（`_guard_no_file_write_in_retry`）：`llmexcept_body_depth > 0` 时执行任何写/删函数抛 `InterpreterError`。兜底编译期无法静态追踪的情形（如经 `fn` 动态分派）。

禁用集：`file.write` / `remove`。放行：`open` / `read` / `read_bytes` / `exists`（只读，不污染快照）。

**固有边界**：外部进程（非 IBCI 代码）触碰 backing 文件不受 IBCI 控制，无法在编译期或运行时拦截--磁盘态快照的零拷贝设计与进程外 I/O 的根本不可控性所致。详见 `docs/KNOWN_LIMITS.md`。

### save_state 约束

`HostService.save_state` 遇到活跃磁盘型变量时直接报错（磁盘型变量的跨环境状态保存需要显式的文件复制策略，不支持隐式快照）。

---

## 六、与序列化的交互

磁盘型变量通过 `__to_descriptor__` / `__from_descriptor__` 协议参与序列化：

- 序列化：输出 `{"path": "<相对路径>", "backing_type": "file"|"generated"}`
- 反序列化：根据 `backing_type` 重建对应的 `FileBacking` 或 `GeneratedBacking`，通过 `get_ib_implementation()` 分发到正确的运行时类

---

## 七、file 模块门控与 API

`file` 模块为内核原生模块（`KERNEL_NATIVE` + `IMPORT_GATED`），需显式 `import file` 方可使用。

### 函数清单

| 函数 | 签名 | 说明 |
|------|------|------|
| `open` | `(path, mode="r") -> file_handle` | 只读打开；mode 限 `""`/`"r"`/`"rb"`/`"rt"` |
| `read` | `(target) -> str` | 文本读取 |
| `read_bytes` | `(target) -> list[int]` | 字节读取 |
| `write` | `(target, data, overwrite_flag="new") -> file_handle` | 统一写入；`"new"` 创建新文件、`"overwrite"` 原地覆写；str/list[int] 自动判别（llmexcept body 内禁止） |
| `exists` | `(path) -> bool` | 沙箱约束下的存在性检查 |
| `remove` | `(target)` | 沙箱约束下的文件删除 |

所有路径操作经 `_resolve_path` 统一做沙箱验证。

---

## 八、与 LLM 调用的交互

### 输入路径（`__payload_prompt__`）

公理层声明 `has_payload_prompt_cap = True`。LLM 执行器在 `_evaluate_segments_cps` 中对 `$var` 插值调用 `receive('__payload_prompt__', [])`：

- 公理层 `__payload_prompt__` 委托到运行时值的 `__path_payload_prompt__`
- 运行时值从 backing 路径惰性物化字节，编码为 base64，组装为对应模态的 content block

纯文本路径（`__to_prompt__`）与多模态路径（`__payload_prompt__`）由返回值类型区分：`str` 走文本拼接，`dict` / `List[dict]` 走 content block 组装。

### 输出路径（`from_prompt`）

文本输出通过 `from_prompt` 协议解析。多模态输出（音频/图像生成）的 `from_response` 协议未实现，属未来设计。

---

## 九、`is_disk_backed` 辅助属性

`IbSpec` 提供 `is_disk_backed` 只读 property（`storage_model == StorageModel.DISK_BACKED`），仅用于诊断/断言。分发路径不得改读此 property 做 if/else——分发一律通过协议方法完成。
---

## 深入指引

- 存储模型架构摘要：docs/architecture/08_storage_model.md
- file 模块语法层：docs/syntax/11_modules.md §11.7
