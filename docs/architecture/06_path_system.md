## 路径系统架构

### 1. 三层路径模块

路径模块按抽象级别分布为三层，依赖严格自底向上：

- `core/base/path/`：原子路径原语（`IbPath`, `safe_relpath`），任何层可用。
- `core/kernel/path/`：IBCI 路径模型（`PathResolver`, `PathValidator`, `PathContext`, `SnapshotLayout`, `ModuleNameSpace`）。
- `core/runtime/path/`：运行时安装发现（`InstallPaths`）。

**设计原则**：compiler 层零 `from core.runtime` 导入（compiler 与 runtime 为兄弟层）；全仓唯一的 `os.path.realpath` 调用点位于 `core/kernel/path/validator.py`。

### 2. 五概念路径模型

路径上下文由五个相互分离的概念组成：

| 概念 | 定义 | 确立时机 |
|------|------|----------|
| `entry_file` / `entry_dir` | 入口脚本及其目录 | run / compile 时 |
| `project_root` | 沙箱边界，= 显式 OR `entry_dir` | run / compile 时延迟确立 |
| `plugin_paths` | 插件搜索路径（可在 project_root 之外） | project_root 确立后 |
| `CWD` | OS 启动上下文，仅保存不校验 | 构造期 |
| `builtin` | 内核安装路径，恒在 | 恒在 |

`project_root` 引擎级延迟初始化：`IBCIEngine(root_dir=None)` 允许；在 `run()` / `compile()` 时确立。`run_string` 合成 entry `<project_root>/__string_exec__.ibci`，使 `entry_dir == project_root`。

### 3. 插件发现优先级

`plugin_paths` 按如下优先级合并（高优先级不可被低优先级同名插件覆盖）：

1. **builtin**：恒在，最高优先级，不可覆盖。
2. **global_plugin**：`ibci.json` 的 `global_plugin` 字段。
3. **plugin_paths**：`ibci.json` 的 `plugin_paths` 字段，显式，可多个。
4. **嗅探**：`ProjectDetector`，仅当 `plugin_paths` 未配置时触发。
5. **全局 config**：预留，不实现。

显式 `plugin_paths` 抑制嗅探。`plugin_path` 可位于 `project_root` 之外（特权只读越界），但写入权限集中于 `project_root`。

### 4. 隔离语义

子引擎的路径上下文通过 `PathContext.derive_isolated(child_entry)` 派生：

- 子 entry 必须在父 `project_root` 内（`is_within` 校验，违反报错）。
- 子 `project_root` = 显式 OR 子 `entry_dir`。
- 子继承父全部 plugin search_paths（`inherited_plugin_paths` + `inherited_global_plugin`）。
- `derive_isolated` 为纯路径派生，策略与路径计算分离。

### 5. canonicalize_for_security

`PathValidator.canonicalize_for_security(path) -> IbPath` 是全仓唯一的 `os.path.realpath` 调用点。所有需要规范化的路径统一经此函数。防止 symlink 逃逸：realpath 解析符号链接至真实物理路径，使后续 `is_within` 沙箱校验无法被 symlink 伪造路径绕过。
