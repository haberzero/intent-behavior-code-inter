# 内核原生模块与插件边界

> 本文档描述 IBCI 内核原生模块的架构边界，包括模块分类、provenance/visibility 模型与插件发现机制。面向需要理解模块系统内部设计的开发者。
>
> 路径系统架构见 `docs/architecture/06_path_system.md`。

---

### 两轴正交模型

内核原生模块的"恒在"与"需 import"是两个正交维度：

| 轴 | `IbSpec` 字段 | 语义 |
|---|---|---|
| 可用性 | `provenance` | `KERNEL_NATIVE` = 随内核发行、构造期预注册、不可被用户插件覆盖 |
| 可见性 | `visibility` | `IMPORT_GATED` = 名字须经 `import` 语句进入当前文件作用域 |

禁止用单一 bool（如 `is_user_defined`）将两轴焊死，否则会经 prelude 过滤器意外解除 import-gating。

### 内核原生模块清单

六个模块在 `Engine.__init__` 构造期预注册：其中 `ai`/`ihost`/`idbg`/`isys`/`iruntime` 经 `register_kernel_native_modules` 批量注册，`file` 由 engine 单独注册。

| 模块 | 功能 | 安全语义 |
|---|---|---|
| `ai` | LLM 调用 | 有状态（配置跨断点保存） |
| `file` | 文件 I/O + 类型注入 | 沙箱相关 |
| `ihost` | 宿主保存/恢复 | `save_state` by design 绕沙箱 |
| `idbg` | 运行时信息输出 | 调试钩子 |
| `isys` | 外部访问请求 | `request_external_access` 全局关沙箱 |
| `iruntime` | 运行时内省（snapshot / subscribe / configure） | 观测全局，只读 |

### HostInterface 覆盖保护

`reserve_kernel_native_name(name)` 在 bootstrap 预注册时调用；`is_kernel_native(name)` 在插件发现路径调用，命中则拒绝用户实现接入。用户插件目录下的同名模块不会覆盖内核原生实现。

### exported_types：import 时的类型注入

`file` 模块声明 `exported_types=["file_handle", "audio", "image", "video"]`。`import file` 时 scheduler 把这四个类型名注入当前作用域。仅 `KERNEL_NATIVE + IMPORT_GATED` 模块生效。

### 多媒体类型为普通类名

`audio`/`image`/`video` 经标准 axiom 路径注册为普通类名（与 `str`/`int`/`Enum` 同级），非词法关键字。`core_scanner.py` 的 `KEYWORDS` 表不含类型名；新增内置类型不触及 TokenType 或 parser 文法。

### 模块初始化：单一 setup 入口

内核原生模块与用户插件统一经 `setup(capabilities)` 完成初始化。加载器遍历已注册模块调用 `setup`，`capabilities` 在构造时已装配能力注册表，模块据此向 `CapabilityRegistry` 注册自身能力（如 `ai` 注册 `llm_provider`）。不存在独立的二次水化钩子——生命周期收敛为单一初始化入口。

### 模块导出过滤（provenance 门控）

语义分析完成后，scheduler 将符号表写入模块 `members` 时按 provenance 过滤（`scheduler.py`）：

```python
final_mod_meta.members = {
    name: sym for name, sym in result.symbol_table.symbols.items()
    if sym.provenance != Provenance.KERNEL_NATIVE
}
```

`KERNEL_NATIVE` provenance 的符号（prelude 注入的 `int`/`str`/`print` 等语言内建、`import file` 门控注入的 `file_handle`/`audio` 等类型）不进入模块导出面。每个模块通过自身的 prelude 注入获得这些符号，无需跨模块重导出。`USER_DEFINED` 和 `EXTERNAL_MODULE` provenance 的符号正常导出。
---

## 深入指引

- 插件子系统实现：docs/subsystems/04_plugin_system.md
- 模块 API 语法层：docs/syntax/11_modules.md
