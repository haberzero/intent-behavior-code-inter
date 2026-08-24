# 如何运行隔离子环境（ihost 动态宿主）

> 面向已能运行单脚本 IBCI 程序的开发者。解决"如何让一段 IBCI 代码在独立环境中运行、
> 如何取回其结果、如何保存与恢复运行状态"的具体问题。
> 前置知识：`docs/syntax/11_modules.md` §11.6（ihost 模块）、`docs/syntax/14_concurrency.md`（协作挂起）。

## 何时需要隔离

一段代码需要**完全独立的执行环境**时使用。子环境拥有独立的 Engine 实例，
内置模块独立注册，且**默认不继承父环境变量**。父环境里的任何变量、LLM
provider 配置都不会泄漏进子环境。典型场景：

- 运行不可信的第三方脚本，隔离其副作用。
- 用独立配置运行同一逻辑（如不同 `api_config.json`）。
- 在独立状态中执行长任务，与主流程互不干扰。

## 阻塞式：run_isolated

需要子脚本**跑完再继续**时用 `run_isolated`，它返回子环境的用户变量字典：

```ibci
import ihost

dict policy = {"isolated": True}
dict result = ihost.run_isolated("./sub/child.ibci", policy)
print((str)result["greeting"])     # 读取子环境变量
```

- `run_isolated` 阻塞当前任务，直到子脚本执行完毕。
- 返回字典只含子环境的**用户变量**（`str`/`int`/`bool`/`list`/`dict`），
  内置符号（`print`、`len`、`range`）不包含在内。
- `policy` 的 `"isolated": True` 表示子环境独立注册、不继承父变量。

## 非阻塞式：spawn_isolated + collect

需要**启动即返回**、稍后再取结果时用 `spawn_isolated` 获得句柄，之后 `collect` 收集：

```ibci
import ihost

str handle = ihost.spawn_isolated("./sub/child.ibci", {"isolated": True})
# 立即返回，主流程可继续做其它事……
dict result = ihost.collect(handle)   # 等待子环境完成，返回变量字典
```

- `spawn_isolated` 立即返回字符串句柄，不等待子脚本完成。
- `collect(handle)` 等待子环境完成并返回其变量字典；子环境编译失败时，
  `collect` 抛出运行时错误。
- 同一句柄**只能 collect 一次**；重复 collect 抛幂等性错误。
- `collect` 是协作挂起：等待期间调度器运行其它任务，不阻塞线程。

## 并发启动多个子环境

多个子环境互不影响，可同时启动：

```ibci
import ihost

str ha = ihost.spawn_isolated("./sub/a.ibci", {"isolated": True})
str hb = ihost.spawn_isolated("./sub/b.ibci", {"isolated": True})
dict ra = ihost.collect(ha)
dict rb = ihost.collect(hb)
```

## 设置收集超时

子脚本可能挂起不返回。用 `policy` 的 `collect_timeout`（秒）限制等待：

```ibci
import ihost

str handle = ihost.spawn_isolated("./sub/child.ibci", {"collect_timeout": 5.0})
dict result = ihost.collect(handle)   # 超过 5 秒未完成 → 抛超时错误
```

- 不指定 `collect_timeout` 时保持无界等待。
- 超时后 `collect` 抛运行时错误；子线程作为后台孤儿继续运行。

## 保存与恢复运行状态

当前运行状态（变量、作用域、意图上下文）可保存到文件，之后恢复：

```ibci
import ihost

ihost.save_state("./state.json")   # 保存当前状态
# …… 其它工作或另一个脚本 ……
ihost.load_state("./state.json")   # 恢复此前保存的状态
```

- `save_state` 遇到活跃的 `file_handle`/`audio`/`image`/`video` 变量时直接报错。
- `ihost.get_source()` 返回当前入口源码。

## 常见陷阱

- **子脚本必须在父 project_root 内**：现阶段子入口路径不得超出父项目根目录，
  否则隔离执行被拒绝。
- **LLM provider 配置不继承**：子环境需真实 LLM 时，须在子项目目录放置自己的
  `api_config.json` 并调用 `ai.load_project_config()`。
- **子环境变量隔离是单向的**：父环境变量不进入子环境；子环境变量只经 `collect`
  的返回值传回。
- **`run_isolated` 与 `spawn_isolated` 的取舍**：只需顺序执行用 `run_isolated`；
  需要并发或主流程继续工作用 `spawn_isolated` + `collect`。

## 深入指引

- 动态宿主完整语法：`docs/syntax/11_modules.md` §11.6
- 并发与协作挂起：`docs/syntax/14_concurrency.md`
- `await ihost.collect(...)` 显式等待：`docs/syntax/14_concurrency.md`
- 隔离的工程示例：`examples/03_advanced_features/isolation_demo/`
