# Rust 内核替换 · 调研结论与交接（2026-09-10）

> **性质**：临时任务控制文档（设计/调研阶段），供下一 agent 接手。
> **用户裁定（2026-09-10）**：把 ibci 主工程最耗时、负担最重的部分用 Rust 实现，
> 编译为 Python 可直接访问形态，整合进 ibci——同时保持 Python 灵活性 + Rust 性能 +
> 线程真并行（不再受 GIL 制约）。**Python 侧代码保留不删**，实验阶段仍可用 Python
> 侧灵活修改。全量 pytest 策略临时调整（见下，至 Rust 替换结束重估）。
> 裁定单点记录 = WORKLOG §二"Rust 内核替换方向" + "全量 pytest 使用策略临时调整"两行。

---

## 一、实测定性：最耗时/最重负担部分 = VM 执行层

### 1.1 生产工作负载侧（cProfile 实测，2026-09-10）

- **微基准**：40000 次 ibci 整数加法循环 = **~1.1s / 24.5M Python 函数调用**
  （~611 次 Python 调用/迭代）。热点（tottime 排序）：
  - `isinstance` 3.55M 次（每步类型检查）
  - `vm_executor._drive_loop_gen`（CPS 主调度循环，cumtime 4.6s）
  - `typing.__instancecheck__` 240k / `runtime_context._check_type` 80k（每步反射）
  - `inspect.getattr_static` 240k（反射开销）
  - `ast_view.__getitem__/_wrap/get` ~2.7M 次（AST 字段访问包装间接）
  - `_make_task` 160k / `get_side_table` 160k（每步任务生成 + 侧表查询）
- **编译期**：82KB/99 class 脚本（trial e28 规模）`check` 全链路 <0.2s——摊薄后非主导
- **LLM I/O**：网络主导；GIL 在 socket 等待期本已释放，Rust 对此无收益（线程已够）
- **结论**：执行层每步的 Python 反射/间接开销是数量级瓶颈（Rust 移植后同循环预计
  ~1ms 量级，100-1000x）

### 1.2 套件侧（全量 pytest --durations 实测，2026-09-10）

| 层 | 耗时 | 占比 | 性质 / Rust 受益 |
|---|---|---|---|
| e2e | 46.6s | 44% | 每测试子进程启动（导入+编译 ~300-500ms/例）+ 实时等待；**Rust 不解决启动开销** |
| runtime | 40.2s | 38% | 进程内解释器 CPU——**Rust 直接受益面** |
| contracts | 9.6s | 9% | 协议契约（白箱，机器无关） |
| compliance | 7.0s | 7% | 并发语义（parallel dispatch / 执行隔离） |
| compiler | 1.3s | 1.2% | 编译期（Rust 前端受益） |
| meta | 1.1s | 1% | 元测试 |

- 全量基线：**main ~45s / 3185+1；unsafe-vibe-dev ~114s / 3990+1**（2026-09-10 实跑）
- 最慢单测试多为实时等待类（timeout 3.0s / streaming 2.2s / 并发 1.3s）——本质慢，
  与 Rust 无关
- **e2e 44% 启动开销是独立问题**：conftest 已有 `run_ibci()` 黑箱助手
  （编译+执行免子进程），大量 e2e 用例可进程内化——待拍板是否同期立项（见 §五）

### 1.3 线程现状

- `core/runtime/vm/task_scheduler.py` 文档化约束："**受 Python GIL 限制，本并发只为
  服务 LLM 调用（IO 密集），不追求** [CPU 并行]"
- `vm_executor.py` 同注。engine 有 spawned tasks（threading.Thread）+ 协作取消事件
- Rust 内核执行期 `py.allow_threads` 释放 GIL → 该约束可解除 = "线程真正可用"落点

## 二、Rust 化方案评估（推荐：pyo3，分四阶段）

### 2.1 技术选型

- **pyo3**（maturin 构建）：执行期 `allow_threads` 释放 GIL；LLM/IO 内建经 pyo3
  回调回 Python 侧（重新获取 GIL；I/O 本非 GIL 敏感）
- 构建链：pyproject `[build-system]` + optional-dependencies（rust 扩展可缺省，
  Python 内核零依赖可装——保持 wheel 现有发布面不变）

### 2.2 分阶段（每阶段独立有价值、可回退）

| 阶段 | 内容 | 修改面 | 风险 |
|---|---|---|---|
| ① 地基 | 构建链 + **差分等价 harness**（双内核同输入→输出比对；常设交付物，整个替换的安全网；语料 = 现有测试用例 + fuzz 种子） | pyproject / 新 crate `ibci-ext/` / tests 层 harness | 零 |
| ② Rust 前端 | lexer/parser/semantic → 序列化 AST（与现有 `core/compiler/serialization` 契约对接） | crate 前端模块 + engine 前端 kernel 选择点 | 低（纯 CPU、契约最清晰：字节串→AST） |
| ③ Rust 执行核心（主战场） | 43 节点 CPS dispatch 表 → Rust enum 分发（或直 AST walk）；帧栈/内建运算/侧表；JIT codegen 面（`jit_codegen.py` 热直线体缓存）对应设计 | crate 执行模块 + engine.run kernel 入口 + 差分门 | 高（语义=公理）——对策：差分等价 + contracts 红线门 + 公理层零改动 |
| ④ 并发解除 | task_scheduler 从 IO-only 升 CPU+IO 真并行（GIL-free 执行体） | task_scheduler/vm_executor 并发面 | 中（并发语义测试 compliance 层已有门） |

### 2.3 双内核协议（核心设计裁定）

- **Python 内核 = 一等实验内核**（用户明确保留不删）：实验阶段 `kernel="py"` 继续
  Python 侧灵活修改（热迭代、原生 traceback 调试）
- **Rust 内核 = 生产快路径**：显式启用（配置/CLI 旗标/环境变量，形态待定）；
  **无静默回退**（fail-fast 一致——rust 内核不可用 = 显式报错，不悄悄切 py）
- 两内核共享同一 AST 契约 + contracts 层语义红线；语言语义单点真理不变
- 注意：双内核 ≠ compat shim（工作模式定论）——是"同一语言的两个一等执行后端"，
  选择经协议显式化；Python 内核不是过渡残留，定位写入架构文档

### 2.4 预期效果（供替换后对比，基线 = §一）

- 简单循环工作负载：40k 迭代 1.1s → ~1ms（100-1000x）
- runtime 层（38%）：5-20x（测试本身有 Python setup/teardown 残留）
- 套件全量：114s → 预计 50-70s（e2e 启动开销不受益）
- 长 run 生产：CPU 段数量级提速；LLM I/O 段不变
- 线程：CPU 段真并行（task_scheduler 约束解除）

### 2.5 风险与对策

1. **语义漂移（最高）**：差分等价 harness + contracts 红线 + 公理层/语义错误集变更
   仍走全量 pytest 红线（策略不变）
2. **构建链复杂度**：本机 Rust 1.98 已验证可用（注意：DSH 沙箱 workspace-write 下
   `/opt` 不可写，`CARGO_HOME=/home/dsh/.cargo` 覆盖方案已验证；gpu/dsh 容器构建
   wheel 时同法）
3. **调试性**：py 内核 = 调试路径；rust 内核错误面需映射回 ibci 诊断码（诊断面
   打包设计 P0-1 有先例）
4. **工作模式定论**：Rust 内核 = 同设计干净移植（CPS/调度表机制同构），禁止
   CPython 内部 hack / 隐式双通道

## 三、全量 pytest 使用策略（已落地，2026-09-10 生效）

- 单任务默认验证 = 受影响子集 + **smoke 子集**（`tests/contracts` + `tests/compiler`，
  实跑 828 用例 11.2s，纯进程内无子进程）
- 全量仅：① merge/放行门 ② 公理层/语义错误集变更 ③ 阶段边界/里程碑 ④ 开新分支前
- 单点真理 = `AGENTS.md` §测试（已同步 NEXT_STEPS 锚点 / code-workflow P4 /
  code-review P4 / WORKLOG §二）
- **实证坑**：pytest.ini addopts 已含 `-q`；验证命令再显式 `-q` = `-qq`，会吞掉
  最终计数行（exit 0 易误判）——验证命令不附加 `-q`
- 重估触发：Rust 内核替换结束且全量耗时显著降低

## 四、环境事实（2026-09-10 交接时点）

- 分支 = `unsafe-vibe-dev`：本地 `39924ebd`（领先 origin `e5f6fd2d` 两提交：
  `896fa102` e2e 计时测试降层白箱 + `39924ebd` pytest 策略文档），**待用户授权 push**
- 主工程 venv：`/home/dsh/proj/intent-behavior-code-inter/.venv`
  （python 3.12.3 + `pip install -e ".[dev]"` + pytest-timeout）
- git 身份：仓库局部 `Nan Shi (施楠) <yunnan_shinan@qq.com>`（按历史惯例）
- **gpu 容器（gpu-train）已部署完毕**（`ssh gpu` 127.0.0.1:2223 root 可达）：
  - NVIDIA RTX PRO 6000 Blackwell，97.9GB 显存（宿主 vllm 占 ~84GB，余 ~14GB）
  - conda 环境 base / pytorch（torch 2.14.0+cu132 + lightning 2.6.5）/ tilelang 0.1.14
  - JupyterLab 可用（`/opt/miniconda3/envs/pytorch/bin/jupyter`；非交互 ssh 无
    conda 在 PATH，用绝对路径或 `conda run -n`）
  - 说明书 = `/shared/TRAINING-TOOLS.md`（外部 agent 落）；训练脚本/数据/输出放
    `/gpu-work`（dsh 内 `/home/dsh/gpu-work`）
  - 注：`/shared/CONTAINERS.md` "当前状态速览"仍写 gpu-train"构建中"（过时，
    宿主侧文档，dsh 无写权限，待宿主/外部 agent 更新）

## 五、待用户拍板（接手 agent 勿自行决断）

1. **主线排布**：当前 P0 = VISION-8 Round5 自指性架构。Rust 替换何时立项？
   (a) Round5 收官后 (b) 并行独立分支（分支政策允许） (c) 先出本设计展开
   （`_rust_kernel_design.md`：双内核协议细节 / 阶段切分 / 等价 harness 设计 /
   crate 结构）再定
2. **e2e 进程内化**（套件 44% 启动开销，与 Rust 无关的独立提速面）：同期立项或
   缓行？
3. **两个本地提交**（`896fa102` + `39924ebd`）push 授权
4. 差分等价 harness 语料范围：现有 3990 用例全量比对 vs 专用 fuzz 语料 + 关键面？

## 六、下一步建议（若用户裁定 (c) 先设计）

1. 展开 `tasks_docs/_rust_kernel_design.md`：crate 结构（ibci-ext：frontend /
   exec / pyo3 绑定三层）、AST 序列化契约对接点（`core/compiler/serialization`）、
   kernel 选择协议（配置面/CLI/引擎参数）、差分 harness 设计（入口/比对粒度/
   失败面）、阶段 ① 实施清单
2. 阶段 ① 实施：构建链 + harness 骨架 + 前端 Rust 化（阶段 ② 可并入）
3. 每阶段出口 = 差分等价零差异 + 受影响子集 + smoke（全量按策略）+ 文档同步
