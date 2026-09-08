# ihost 子环境整合设计（E1 配置继承 + R-2a run_file）

> 状态：设计完成 → 分批实施（E1 先行，run_file 随后）。
> 来源：round3 需求 R-2a（P0，与 E1 同域）+ round2 遗留 E1 重做（设计定案
> 保留于 HANDOFF §2.1）。试用方实证注记："子环境不继承 LLM 配置 + 需自身
> api_config" = E1 的语义需求。

## 一、现状与缺口

子 run 基建已有（`core/engine.py::request_spawn_isolated` 系统调用）：

- 独立 `IBCIEngine(root_dir=sub_root_dir)` + 后台线程 + 完成唤醒回调（无轮询）；
- `request_collect`（变量字典提取 + 异常透传 + collect_timeout 墙钟上限）；
- `HostAwaitable`（VM 协作式挂起/唤醒；run_isolated/collect 语言面）；
- `IsolationPolicy`（collect_timeout + fs 边界）；save_state/load_state。

缺口：

1. **E1（配置继承）**：子引擎的 AIPlugin = 干净态（url/key/model 全 None）——
   子脚本调 LLM 必失败，除非子项目自写 api_config.json（试用方实证摩擦）。
2. **R-2a（结果捕获消费面）**：collect 只回"导出变量字典"；缺"进程内运行另一
   .ibci 文件 + 捕获其执行结果（exit_status / stdout / exception）"的消费面。

## 二、E1：子环境 LLM 配置继承

### 2.1 快照源裁定（对 HANDOFF 原设计措辞的偏离，记录依据）

- **采用：父 LLM provider 的活状态快照**（经既有 `IbStatefulPlugin`
  save/restore 契约）：spawn 时父线程 `save_plugin_state()` → 子线程 on_ready
  钩子 `restore_plugin_state(snapshot)`。
- **弃用**：父 api_config.json 文件快照 + `to_llm_config` 归一（HANDOFF 原措辞）
  ——api_config.json 只是配置的**初始源之一**；活状态可经 `register_model` /
  `set_mock_mode` / `set_config` 漂移，文件快照漏掉全部运行时变更。单一权威源 =
  provider 活 `_config`（apply_config 是唯一写入者，所有读取经它）。
- mock 模式保真：`_config["mock"]` 在快照内 → 父 mock 态子继承 mock 态
  （set_mock_mode 置 `_config["mock"]` + client 哨兵；restore 按快照重建，
  mock 路径不触碰 client）。
- **补漏**：`save_plugin_state` 现含 `config` / `return_type_prompts`，**缺
  `_model_registry`（@NAME~ 命名模型注册表）**——命名模型是活配置状态的一部分，
  缺失是既有状态保真缺口（checkpoint/restore 同受益）= 纯增面补上。

### 2.2 机制（on_ready hook 形态 = 设计定案）

- `engine.execute(..., on_ready=None)`：`_prepare_interpreter`（解释器 + 插件
  就绪）之后、委派调度器之前触发；`run(..., on_ready=None)` 透传。
- `request_spawn_isolated`（父线程，spawn 时点）：
  1. 快照捕获：`self.capability_registry.get(CAP_LLM_PROVIDER)` →
     `isinstance(IbStatefulPlugin)` → `save_plugin_state()`；不满足 =
     无快照（诚实边界：replay provider / 自定义非 stateful provider → 不继承，
     子调 LLM 得清晰未配置错误）。
  2. 子线程 `_run_child`：`sub_engine.run(abs_path, silent=silent,
     on_ready=lambda e: _apply_llm_inheritance(e, snapshot))`。
- `_apply_llm_inheritance`（子线程，on_ready 钩子体）：子 `CAP_LLM_PROVIDER`
  （= 子 AIPlugin）`restore_plugin_state(snapshot)`；失败/不适用 →
  `kernel_diagnostic`（新码 `HOST_ISOLATE_LLM_INHERIT_FAILED`，**不阻断**——
  子照常执行，其 LLM 调用按自身状态得清晰错误）。**实施裁定**：失败面走
  `kernel_diagnostic` 既有运行时告警通道（投影 A = warnings.warn 开发者可见 +
  投影 B = 观测事件）——与同域 `KDIAG_RUNTIME_COLLECT_SKIP`（collect 路径）
  机制同构，非 issue_tracker（issue_tracker = 编译诊断收集器，运行时告警
  非其职责面）。
- **优先级语义**：on_ready 钩子在子代码执行前触发——子代码显式
  `ai.load_project_config()` / `set_config` 覆盖继承快照（时间序优先，自然
  语义，不加机制）。
- **快照语义**：spawn 时点值（快照 = 深拷贝 dict，不可变）——spawn 后父变异
  不影响已 spawn 子。

### 2.3 验证面（mock 模式，零真实 LLM）

- 继承：父 set_mock_mode + 父 LLM 调用成功 → `ihost.run_isolated` 子 LLM 调用
  同 mock 输出（子无自身 api_config）；
- 快照语义：spawn 后父切模型/关 mock → 已 spawn 子不受影响；
- 继承失败 WARNING：白箱（子 provider 非 stateful / 快照损坏）→ 码显形不阻断。

## 三、R-2a：ihost.run_file（进程内子 run + 结果捕获）

### 3.1 语言面

```
dict r = ihost.run_file(path: str, policy: dict) -> dict
```
TypeDef 声明与 run_isolated 同构（builtin_modules ihost 节）。

### 3.2 结果记录契约

```
{
  "exit_status": "ok" | "error",   # 子 run 判定（异常=error，含编译失败）
  "stdout":      str,              # 子 print 输出（捕获，不经父 stdout）
  "exception":   str,              # 错误消息；exit_status=ok 时 = ""
}
```

- stdout 捕获 = 子 `run(output_callback=collector)`（engine 既有参数——机制
  同构；chunk 按序拼接）；
- exit_status/exception = `request_collect` 既有异常透传面（子异常 →
  RuntimeError 携带子消息；run_file 捕获为值——**错误作值**是本消费面的
  语义，与 run_isolated 的**错误作异常**语义互补，非双通道：同一 spawn 机制，
  两个消费面各负责子 run 结果的一个面[变量交换 vs 执行结果捕获]）。

### 3.3 机制

- `request_spawn_isolated` 增 `output_callback=None` 参数（透传子 run）；
- 实现（host service）：
  ```
  chunks = []
  handle = orchestrator.request_spawn_isolated(abs_path, policy, silent=True,
                                               output_callback=chunks.append)
  error = None
  try: orchestrator.request_collect(handle)
  except RuntimeError as e: error = str(e)
  return {"exit_status": "ok" if error is None else "error",
          "stdout": "\n".join(chunks), "exception": error or ""}
  ```
  （silent=True：子输出被捕获不经父 stdout——run_file 的语义 = 捕获而非透传；
  run_isolated silent=False 语义不变。）
- **防卡死**：collect_timeout 经 policy 传递（IsolationPolicy 既有面）；
  默认 None = 无界（与 run_isolated 一致，文档化）；判别测试必传有限
  collect_timeout。

## 四、新增诊断码（纯增面）

| 码 | 严重级别 | 触发 |
|----|----------|------|
| `HOST_ISOLATE_LLM_INHERIT_FAILED` | WARNING | 子环境 LLM 配置继承应用失败（不阻断子执行） |

（codes.py + catalog.py + 15_diagnostics 同步 + parity 门。）

## 五、实施顺序与批次

1. **批 1（E1）**：save_plugin_state 补 `_model_registry` + engine run/execute
   on_ready 参数 + request_spawn_isolated 快照捕获/透传 + 子侧应用 +
   HOST_ISOLATE_LLM_INHERIT_FAILED 码 + 判别（继承/快照语义/失败 WARNING）。
2. **批 2（run_file）**：request_spawn_isolated output_callback 参数 +
   host service run_file + TypeDef 声明 + 文档（05/13 按 ihost 面所在）+
   判别（ok/error/stdout 捕获/防卡死超时）。
3. 每批：全量 pytest 零回归 + WORKLOG + 本地提交。

## 六、边界与诚实记录

- 继承 = LLM 配置面（ibci_ai provider 活状态）；自定义 provider 绑定
  （ai.set_provider / 宿主绑定）不在继承范围（子引擎独立插件发现——
  边界文档化）。
- replay 父 spawn 子：replay provider 非 stateful → 不继承（边界 2.2 记录）。
- run_file 子 run 的 LLM journal/预算：子引擎独立 run（子侧默认开 journal——
  子项目根下 llm_journal/）；父 journal 只记父调用（run 级边界，不跨引擎）。
