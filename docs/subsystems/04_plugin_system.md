# IBCI 内置模块系统与宿主绑定

> 本文档描述 IBCI 的模块系统：内置模块的构造期注册、内核原生覆盖保护，以及用户
> 扩展的唯一通道——宿主绑定。面向需要开发或维护模块系统的开发者。
> 内置模块的 API 属语法参考层，见 `docs/syntax/11_modules.md`；
> 模块与 import 基础语法见 `docs/SYNTAX_REFERENCE.md` §11。

---

## 1. 模块分类

### 1.1 内核原生模块（kernel-native）

随内核发行，构造期注册，`IMPORT_GATED`，受 HostInterface 覆盖保护（同名非
kernel-native 注册被忽略并告警）。

| 模块 | 功能 |
|------|------|
| `ai` | LLM provider 配置（API key、model、retry 等） |
| `file` | 受限文件系统操作 |
| `ihost` | 动态宿主（隔离子环境运行） |
| `idbg` | 调试探查工具 |
| `isys` | 运行时状态与路径查询 |
| `iruntime` | 运行时内省（snapshot / subscribe / configure） |

### 1.2 内置工具模块

| 模块 | 功能 | 契约源 |
|------|------|--------|
| `json` | JSON 解析与序列化 | IBCI 契约源（`contracts/json.ibci`） |
| `math` | 数学运算 | IBCI 契约源（`contracts/math.ibci`） |
| `time` | 时间查询 | IBCI 契约源（`contracts/time.ibci`） |
| `schema` | 数据验证 | IBCI 契约源（`contracts/schema.ibci`） |
| `net` | 网络请求 | 宿主侧字面量（默认参数 + per-engine 状态面，见 §2） |

---

## 2. 构造期注册（无插件搜索路径）

全部 11 个内置模块在 Engine 构造期一次就绪。**不存在插件搜索路径**：无
`plugin_paths` / `global_plugin` 配置，无目录嗅探，无继承父环境插件路径——
每个 Engine 构造期即获得同一组内置模块。

契约描述有两个源（按契约面性质分域，各域单一权威源）：

- **宿主侧字面量**（内核原生 6 + `net`，共 7 个）：TypeDef 字面量集中于
  `core/runtime/bootstrap/builtin_modules.py`，由 `register_builtin_modules(host_interface)`
  注册。这些契约面含构造期 lifecycle / LLM 通道 / 引擎内部服务 / 内核值类型导出
  （`file`），或带默认参数与 per-engine 可变状态（`net`）——bind 声明无对应表达面。
- **IBCI 契约源**（工具 4：`math` / `json` / `time` / `schema`）：契约单一权威源 =
  IBCI bind 声明文件 `core/runtime/bootstrap/contracts/<module>.ibci`（与用户侧宿主
  绑定同一声明形态），由 `kernel_contracts.load_tool_contracts(host_interface)` 于构造期
  处理：parse → 成员 spec 合成（与用户侧宿主绑定共用同一合成逻辑）→ 注册。设计理由见
  `docs/architecture/01_native_host_binding.md` §六（内核契约自举）。

其余事实：

- 除 `file` 外均有物理包，位于 `ibci_modules/` 目录：内核原生 6 + `net` 经
  `create_implementation()` 工厂（per-engine 实例）；工具 4 为模块级函数面
  （per-engine 实现容器由构造期按契约声明的成员面构造）。`file` 无物理包，实现为
  内核模块 `core/runtime/modules/fs_impl.py`。
- 内核原生 6 + `file` 为 `KERNEL_NATIVE` provenance；`net` 为 `USER_DEFINED`
  provenance；工具 4 为 `EXTERNAL_MODULE` provenance（契约源自 bind 声明合成，与用户侧
  宿主绑定派生同构）。仅 `KERNEL_NATIVE` 受覆盖保护。全部内置模块
  `visibility=IMPORT_GATED`（须显式 import）。
- 模块函数的描述符（参数名 / 种类 / 默认值存在性）是具名调用与默认值填充的权威：
  字面量模块来自 `builtin_modules.py` 的 `param_descriptors` 声明；工具 4 来自契约源
  的 bind 声明（无默认值语法——工具 4 契约面无默认参数）。

---

## 3. 内置模块

内置模块（`ai`/`file`/`ihost`/`idbg`/`isys`/`iruntime`/`json`/`math`/`time`/`net`/`schema`）
的完整 API 见 `docs/syntax/11_modules.md` §11.3-§11.8。

---

## 4. 用户扩展：宿主绑定（唯一通道）

用户侧扩展 IBCI 的唯一通道是**宿主绑定**：在 `.ibci` 文件内用
`import python "..." as lib: bind ...` 声明要绑定的宿主成员（模块函数 / 属性 /
类）。绑定声明即契约——编译期按声明做类型检查，运行期成员访问强制经
vtable/whitelist 门控，契约外成员 fail-fast。

```ibci
import python "math" as m:
    bind sqrt(x: float) -> float

float r = m.sqrt(16.0)   # 4.0
```

操作指南见 `docs/howto/extend_with_host_binding.md`；语法层见
`docs/syntax/11_modules.md` §11.10；架构设计（含 bind class 与 impl 目标）见
`docs/architecture/01_native_host_binding.md`。

---

## 5. import 语法

`import X` / `from X import Y`（含相对导入、别名、星号导入）与宿主绑定
`import python "..." as lib: bind ...` 的语法约束见 `docs/syntax/11_modules.md`。

---

## 深入指引

- 模块系统语法层：docs/syntax/11_modules.md
- 模块可见性隔离：docs/KNOWN_LIMITS.md §十九
- 内核原生模块边界：docs/architecture/07_kernel_native_modules.md
