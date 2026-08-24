# 路径系统架构

> 本文档描述 IBCI 路径系统的架构设计，包含三层路径模型、四概念路径模型与沙箱隔离语义。面向需要理解和修改路径/模块系统的开发者。
>
> 内核原生模块边界见 `docs/architecture/07_kernel_native_modules.md`；变量存储模型见 `docs/architecture/08_storage_model.md`。

---

### 1. 三层路径模块

路径模块按抽象级别分布为三层，依赖严格自底向上：

- `core/base/path/`：原子路径原语（`IbPath`, `safe_relpath`），任何层可用。
- `core/kernel/path/`：IBCI 路径模型（`PathResolver`, `PathValidator`, `PathContext`, `SnapshotLayout`, `ModuleNameSpace`）。
- `core/runtime/path/`：运行时安装发现（`InstallPaths`）。

**设计原则**：compiler 层零 `from core.runtime` 导入（compiler 与 runtime 为兄弟层）；全仓唯一的 `os.path.realpath` 调用点位于 `core/kernel/path/validator.py`。

### 2. 四概念路径模型

路径上下文由四个相互分离的概念组成：

| 概念 | 定义 | 确立时机 |
|------|------|----------|
| `entry_file` / `entry_dir` | 入口脚本及其目录 | run / compile 时 |
| `project_root` | 沙箱边界，= 显式 OR `entry_dir` | run / compile 时延迟确立 |
| `CWD` | OS 启动上下文，仅保存不校验 | 构造期 |
| `builtin` | 内核安装路径，恒在 | 恒在 |

`project_root` 引擎级延迟初始化：`IBCIEngine(root_dir=None)` 允许；在 `run()` / `compile()` 时确立。`run_string` 合成 entry `<project_root>/__string_exec__.ibci`，使 `entry_dir == project_root`。

### 3. 模块加载（无插件搜索路径）

模块加载不经过任何插件搜索路径：全部内置模块（内核原生 6 + 工具 5）的
TypeDef 字面量集中于 `core/runtime/bootstrap/builtin_modules.py`，在 Engine 构造期
一次注册（详见 `docs/architecture/07_kernel_native_modules.md`）。用户扩展走宿主
绑定（`import python "..." as lib: bind ...`），不经路径发现。

### 4. 隔离语义

子引擎的路径上下文通过 `PathContext.derive_isolated(child_entry)` 派生：

- 子 entry 必须在父 `project_root` 内（`is_within` 校验，违反报错）。
- 子 `project_root` = 显式 OR 子 `entry_dir`。
- 子环境是独立 Engine 实例，构造期自行注册同一组内置模块；无插件路径继承。
- `derive_isolated` 为纯路径派生，策略与路径计算分离。

### 5. canonicalize_for_security

`PathValidator.canonicalize_for_security(path) -> IbPath` 是全仓唯一的 `os.path.realpath` 调用点。所有需要规范化的路径统一经此函数。防止 symlink 逃逸：realpath 解析符号链接至真实物理路径，使后续 `is_within` 沙箱校验无法被 symlink 伪造路径绕过。
---

## 深入指引

- 沙箱与路径实现：docs/architecture/07_kernel_native_modules.md
- 存储模型：docs/architecture/08_storage_model.md
