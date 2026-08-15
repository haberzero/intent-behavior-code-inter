# 设计决策：死循环防护的作用域（内核不设上限，试用套件负责超时与彻底清理）

> 2026-08-14 编制。触发：试用套件残留死循环进程（smoke_deadloop 孤儿进程存活 1h43m），
> 深挖 `--max-inst` 失效指令上限机制的遗留来源。
> **用户 2026-08-14 定案**：内核**不**设 ibci 用户代码死循环上限（允许死循环是正常的）；
> 应被限制/具备相关设计的**只有试用套件**——智能体使用试用套件时适配超时配置，
> 超时后**彻底杀死**相关进程。

## 〇、失效指令上限机制的遗留来源（git 考古实证）

三层死代码，全部指向**旧内核的"运行长度限制"概念**：

| 层 | 现状 | 遗留来源 |
|----|------|----------|
| `main.py --max-inst` | 解析但**从不传给 engine**（`main.py:144 engine.run(args.file,...)` 无 max_inst） | `029e4ea4`（2026-04-04，`chore: 添加--max-inst参数`）——半途加的 CLI 参数，从未接线 |
| `interpreter.max_instructions` / `instruction_count` | 定义/重置/序列化，但**全仓无 `+=` 增量、无比较**（恒 0、永不检查） | 旧内核真实防护（历史 `interpreter.py:721-722` 有 `instruction_count += 1` + `max_instructions` 检查）→ `273f7e5c`（2026-04-09，`修改默认运行长度限制`）改为 `max_instructions=0`（0=无限）并门控 `> 0` → 内核重写（M3a CPS）时**增量+检查代码丢失**，仅留残留字段 |
| `vm_executor.max_steps` / `step_count` | `max_steps=0`（0=unlimited）定义，**全仓无任何地方设置它** | `ff1e828f`（M3a CPS scheduling loop）引入步数上限骨架，从未激活 |

**结论**：失效的"指令格式/计数限制"是**旧内核"运行长度限制"的遗骸**——原本是真实的
内核死循环防护（指令计数 + 上限检查），2026-04-09 被默认改为无限（0），CPS 架构重写时
增量/检查代码被丢弃，只留下三层未接线的死字段；`--max-inst` 是同期半途添加、从未接线
的 CLI 残留。内核当前实际无任何死循环上限（与用户定案方向一致）。

## 一、设计定案

1. **内核不设用户代码死循环上限**（用户 2026-08-14）：`while true` 等无限循环是合法
   用户语义，内核不为此设置指令计数/步数上限。
2. **死代码清理**（防复发）：上述三层死机制应**彻底移除**（`--max-inst` CLI 参数、
   `interpreter.max_instructions`/`instruction_count`、`vm_executor.max_steps`/`step_count`），
   不留"半死"状态（code-quality 红线：死代码/残留须干净彻底清理）。
   **注意**：本机有并发智能体在修改内核代码，清理须与之协调或由内核侧 session 执行，
   避免冲突；本轮只记录不实施。
3. **试用套件负责超时与彻底清理**：智能体使用试用套件时适配超时配置，超时后**彻底
   杀死**相关进程（含孤儿/衍生进程组）。VM 内不设死循环上限。

## 二、试用套件超时清理改进（设计建议）

### 现状（`tasks_docs/trials/_toolkit/run_one.py`）
- `start_new_session=True` 启动 main.py（独立 session/进程组）。
- 超时：`os.killpg(proc.pid, 9)` → `proc.communicate(5)` → 仍挂则 `proc.kill()` + 放弃。
- **缺口**：① 当**调用链（bash/run_batch/run_one）被外部终止**（如 shell 工具超时杀 bash）
  时，main.py 的进程组不在被杀组内 → 孤儿化到 init、无人 killpg；② 若 main.py 衍生
  子进程到独立组，killpg 覆盖不到。

### 建议改进（试用套件，非内核）
1. **run_one.py 超时清理加固**：
   - 超时后除 `killpg(proc.pid, 9)` 外，追加"按命令行/根目录模式扫描并杀死残留"
     （如 `pkill -9 -f "main.py run <trial_root>"`），兜底孤儿。
   - 写 `logs/<case>.pid` / 进程组标记，便于事后清理扫描。
2. **run_batch.py 批次前后清扫**：批次开始前/结束后，扫描并清理孤儿 `main.py run
   <当前试用地基>` 进程（避免历史中断遗留污染）。
3. **智能体适配超时配置**：试用套件超时参数显式化（现有 `--timeout` 必填），文档化
   "超时后彻底杀死"的保障契约（死循环保护硬约束，用户强制）。
4. **明确职责边界**：试用套件文档注明"死循环防护在套件层（OS 超时 + 彻底清理），
   内核不设用户代码上限"。

## 三、判别性验证建议

- 死循环用例（smoke_deadloop）：超时后**无残留进程**（`pgrep -f "smoke_deadloop"` 为空）。
- 调用链被中断场景（模拟 kill run_one/run_batch）：孤儿 main.py 能被清扫机制回收。
- 内核清理后：`--max-inst` 参数移除、`max_instructions`/`max_steps` 字段移除，
  全量 pytest 零回归（死代码移除，无行为变化）。

## 四、交接纪律

- 内核死代码清理须与并发内核智能体协调/由内核侧执行（本轮不实施，避免冲突）。
- 试用套件改进属试用体系（tasks_docs/trials/_toolkit/），可独立窗口实施（非内核）。
- 全程本地 commit、禁 push；不触碰 main。

## 五、实施记录（2026-08-15，exp/max-inst-cleanup）

按本文定案执行死代码清理：
- 删除 `main.py` 顶层与 `run` 子命令的 `--max-inst` 参数。
- 删除 `Interpreter.max_instructions` / `instruction_count` 字段、getter、序列化与重置点。
- 删除 `ExecutionContextImpl.get_instruction_count_callback` / `get_instruction_count`；
  `coordinator.py` 同步删除 `lambda: 0`。
- 删除 `IStackInspector.get_instruction_count` 协议方法；`idbg.env()` 删除
  `instruction_count` 字段（对外可观测字段同步移除）。
- 删除 `VMExecutor.max_steps` / `step_count` 及步数检查；**保留**同一循环内的
  `cancel_event` 协作取消检查。
- 试用套件 `_toolkit/run_one.py` / `run_batch.py` 不再传 `--max-inst`；日志头与
  register 记录删除 `max_inst` 字段；`T07 rerun_old_suites.py` 同步删除。
- 相关文档（NEXT_STEPS / _HANDOFF_NEXT_TRIAL / _toolkit 文档 / 各试用地基 DESIGN/REGISTER
  的保护表述）同步修正为“OS 超时 SIGKILL + LLM 调用超时”。
- 全量 pytest 零回归；死循环防护职责完全落在试用套件 OS 层。
