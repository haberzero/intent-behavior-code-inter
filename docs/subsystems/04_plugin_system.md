# IBCI 插件与模块系统

> 本文档描述 IBCI 的模块系统、插件发现机制与用户插件开发流程。面向需要开发或维护插件的开发者。
> 内置模块（ai/file/ihost/idbg/isys/json）的 API 属语法参考层，见 `docs/syntax/11_modules.md`；
> 模块与插件基础语法见 `docs/SYNTAX_REFERENCE.md` §11。

---

## 1. 模块分类

### 1.1 内核原生模块（kernel-native）

随内核发行，构造期预注册，`IMPORT_GATED`，不可被用户插件覆盖。

| 模块 | 功能 |
|------|------|
| `ai` | LLM provider 配置（API key、model、retry 等） |
| `file` | 受限文件系统操作 |
| `ihost` | 动态宿主（隔离子环境运行） |
| `idbg` | 调试探查工具 |
| `isys` | 运行时状态与路径查询 |
| `iruntime` | 运行时内省（snapshot / subscribe / configure） |

### 1.2 内置用户插件（随仓库发行）

位于 `ibci_modules/` 目录，通过插件发现机制自动加载：

| 插件 | 功能 |
|------|------|
| `ibci_json` | JSON 解析与序列化 |
| `ibci_math` | 数学运算 |
| `ibci_time` | 时间查询 |
| `ibci_schema` | 数据验证 |
| `ibci_net` | 网络请求 |

### 1.3 用户自定义插件

用户可在工程中放置 Python 编写的插件。

---

## 2. 插件发现路径

插件发现按以下优先级搜索：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1（最高） | 内核安装路径 | kernel-native 模块 |
| 2 | `ibci.json` 中 `global_plugin` | 全局插件路径 |
| 3 | `ibci.json` 中 `plugin_paths` | 显式插件路径列表 |
| 4 | 嗅探 | 当 `plugin_paths` 未配置时，自动嗅探以下目录：`./plugins`、`./ibci_modules`、`./.ibci/plugins` |
| 5 | 全局配置（预留） | 尚未实现 |
| 6（最低） | 继承父环境 | 隔离子环境继承父环境的插件路径 |

> 当 `ibci.json` 显式配置了 `plugin_paths` 时，嗅探（优先级 4）不会触发。

---

## 3. 内置模块

内置模块（`ai`/`file`/`ihost`/`idbg`/`isys`/`json`）的完整 API 见 `docs/syntax/11_modules.md` §11.3-§11.8。

---

## 4. 用户插件开发

插件的目录结构、`_spec.py` / `__init__.py` 模板与开发阶段校验的**操作指南**见 `docs/howto/write_user_plugin.md`（单点真理）。此处仅保留实现侧关注的 **vtable 参数声明细则**：

`__ibcext_vtable__()` 中 `params` 每个参数可声明字段：`name`（必填）、`type`（IBCI 类型名）、`default`（默认字面值，声明后参数可选）、`kind`（`POSITIONAL_OR_KEYWORD` 默认 / `VAR_POSITIONAL` / `VAR_KEYWORD` / `KEYWORD_ONLY`）。声明了 `name` 后，IBCI 侧即可对该模块函数进行具名调用与默认值填充；声明的参数名必须被实现函数按名接受（或实现接受 `**kwargs`），否则加载失败。声明 `VAR_KEYWORD`（`**kwargs`）时，实现必须接受 `**kwargs`，未声明的具名实参会在 IBCI 侧归集为 dict 并分传给它。

插件检查（`ibci_sdk.check`）的检查项包括：`_spec.py` 存在性、`__ibcext_metadata__`/`__ibcext_vtable__` 函数合法性、`create_implementation()` 工厂函数存在性、vtable 声明的方法在实现类上存在、参数数量匹配、`IbStatefulPlugin` 协议完整性等。

---

## 5. import 语法

`import X` / `from X import Y`（含相对导入、别名、星号导入）的语法约束见 `docs/syntax/11_modules.md` §11.1。
---

## 深入指引

- 模块系统语法层：docs/syntax/11_modules.md
- 插件可见性隔离：docs/KNOWN_LIMITS.md §十九
