# 内核原生模块边界

> 本文档描述 IBCI 内核原生模块的架构边界，包括模块分类、provenance/visibility 模型与覆盖保护机制。面向需要理解模块系统内部设计的开发者。
>
> 路径系统架构见 `docs/architecture/06_path_system.md`。

---

### 两轴正交模型

内核原生模块的"恒在"与"需 import"是两个正交维度：

| 轴 | `IbSpec` 字段 | 语义 |
|---|---|---|
| 可用性 | `provenance` | `KERNEL_NATIVE` = 随内核发行、构造期注册、不可被非 kernel-native 注册覆盖 |
| 可见性 | `visibility` | `IMPORT_GATED` = 名字须经 `import` 语句进入当前文件作用域 |

禁止用单一 bool（如 `is_user_defined`）将两轴焊死，否则会经 prelude 过滤器意外解除 import-gating。

### 内核原生模块清单

内置 13 个模块（内核原生 8 + `net` + 工具 4）在 Engine 构造期一次就绪，契约描述分两域
（注册机制与 provenance 模型详见 `docs/subsystems/04_plugin_system.md` §2 与
`docs/architecture/01_native_host_binding.md` §六）：

- 内核原生 8 + `net` 的 TypeDef 字面量集中于 `core/runtime/bootstrap/builtin_modules.py`，
  经 `register_builtin_modules` 注册（`net` 的 spec provenance = `USER_DEFINED`，
  注册域同内核原生）；
- 工具 4（`math`/`json`/`time`/`schema`）的契约单一权威源 = IBCI bind 声明契约源
  （`core/runtime/bootstrap/contracts/<module>.ibci`），经 `kernel_contracts`
  构造期自举处理（内核契约自举）。

其中内核原生 8 个模块（`KERNEL_NATIVE` provenance，含 `file`）为：

| 模块 | 功能 | 安全语义 |
|---|---|---|
| `ai` | LLM 调用 | 有状态（配置跨断点保存） |
| `file` | 文件 I/O + 类型注入 | 沙箱相关 |
| `ihost` | 宿主保存/恢复 + 隔离子运行 | `save_state` by design 绕沙箱 |
| `meta` | 代码作值（compile 编译门 + quote/eval 数据/命令二元） | 验证门零执行；eval 子进程隔离 |
| `selfref` | 自指性架构确定性原语（自描述/模板注册/验证门） | 零 LLM（SR-5 结构性保证） |
| `idbg` | 运行时信息输出 | 调试钩子 |
| `isys` | 外部访问请求 | `request_external_access` 全局关沙箱 |
| `iruntime` | 运行时内省（snapshot / subscribe / configure） | 观测全局，只读 |

### HostInterface 覆盖保护

`register_module` 在注册路径检查：`KERNEL_NATIVE` provenance 的元数据注册时把模块名加入
`_kernel_native_names`；此后同名非 kernel-native 注册被忽略并发射
`KDIAG_POLICY_MODULE_OVERRIDE` 诊断（可观测，不静默）。宿主绑定 / 外部注册无法覆盖内核原生实现。

### exported_types：import 时的类型注入

`fs` 模块声明 `exported_types=["file_handle", "audio", "image", "video"]`。`import fs` 时 scheduler 把这四个类型名注入当前作用域。仅 `KERNEL_NATIVE + IMPORT_GATED` 模块生效。

### 多媒体类型为普通类名

`audio`/`image`/`video` 经标准 axiom 路径注册为普通类名（与 `str`/`int`/`Enum` 同级），非词法关键字。`core_scanner.py` 的 `KEYWORDS` 表不含类型名；新增内置类型不触及 TokenType 或 parser 文法。

### 模块初始化：单一 setup 入口

全部内置模块统一经 `setup(capabilities)` 完成初始化。加载器遍历已注册模块调用 `setup`，`capabilities` 在构造时已装配能力注册表，模块据此向 `CapabilityRegistry` 注册自身能力（如 `ai` 注册 `llm_provider`）。不存在独立的二次水化钩子——生命周期收敛为单一初始化入口。

### 模块导出过滤（provenance 门控）

语义分析完成后，scheduler 将符号表写入模块 `members` 时按 provenance 过滤（`scheduler.py`）：

```python
final_mod_meta.members = {
    name: sym for name, sym in result.symbol_table.symbols.items()
    if sym.provenance != Provenance.KERNEL_NATIVE
}
```

`KERNEL_NATIVE` provenance 的符号（prelude 注入的 `int`/`str`/`print` 等语言内建、`import fs` 门控注入的 `file_handle`/`audio` 等类型）不进入模块导出面。每个模块通过自身的 prelude 注入获得这些符号，无需跨模块重导出。`USER_DEFINED` 和 `EXTERNAL_MODULE` provenance 的符号正常导出。
---

## 深入指引

- 内置模块系统与宿主绑定：docs/subsystems/04_plugin_system.md
- 模块 API 语法层：docs/syntax/11_modules.md
