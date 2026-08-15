# IBCI 试用套件体系

> 本文档描述仓库根 `trials/` 目录中的试用套件体系：结构、用途、用例契约、分类与报告机制。
> 面向需要运行、编写或扩展真实 LLM 试用套件的开发者。阅读前需了解 IBCI 基本语法（见 `docs/SYNTAX_REFERENCE.md`）。

## 一、体系定位

试用套件是 IBCI 语言语义与内核行为的**可判定回归资产**。它用结构化的用例头部断言
（`expect-*`）把“期望行为”编码进用例本身，由 harness 自动判定结果。套件分两层：

| 层 | 依赖 | 作用 |
|----|------|------|
| mock 层 | 无需外部服务 | 快速回归语言语义、诊断码、控制流与容器行为 |
| 真实 LLM 层 | OpenAI 兼容 API 服务 | 验证 LLM 调用机制、解析契约与真实模型行为 |

## 二、目录结构

```
trials/
├── _toolkit/                          # 统一工具链
│   ├── run_one.py                     # 单用例 harness（进程组超时 SIGKILL）
│   ├── run_batch.py                   # 批量运行器（mock/llm 分层）
│   ├── CONTRACT_FORMAT.md             # 用例头部断言规范
│   ├── CLASSIFICATION.md              # 分类、级别、命名规范
│   └── LLM_SERVICE.md                 # 本机与自定义 API 服务规范
├── T<nn>_<主题>/                      # 各试用地基
│   ├── DESIGN.md                      # 试用维度与覆盖矩阵
│   ├── REGISTER.md                    # 结果汇总与缺陷登记
│   ├── cases/                         # 用例脚本（.ibci）
│   └── logs/                          # 本地运行记录（不纳入版本控制）
└── INDEX.md                           # 跨套索引与缺陷状态权威
```

`logs/` 目录保存每次运行的输出与 `register.jsonl` 机械记录，用于本地参考分析，不参与
Git 管理。

## 三、用例契约

每个用例头部以 `# expect-*:` 声明机器可判定的期望。harness 解析这些断言并自动判定分类，
不依赖人工判断。

```ibci
# expect-class: PASS
# expect-out: total=6 | DONE
# expect-llm: false
```

| 字段 | 含义 |
|------|------|
| `expect-class` | 必填，目标分类 |
| `expect-out` | 按顺序出现的期望输出行，多行用 `|` 分隔 |
| `expect-exit` | 期望退出码：`0` / `1` / `nonzero` |
| `expect-code` | 期望出现的诊断码，可逗号分隔多个 |
| `expect-llm` | 是否依赖真实 LLM，批量运行器据此分层 |

分类与判定规则见 `trials/_toolkit/CONTRACT_FORMAT.md`。

## 四、运行入口

单用例运行：

```bash
python trials/_toolkit/run_one.py trials/T<nn>_<主题>/cases/<case>.ibci \
    --label <case_id> --dim <dim> --doc <章节> --expected <描述> \
    --timeout <秒，必填> --root trials/T<nn>_<主题>
```

批量运行：

```bash
python trials/_toolkit/run_batch.py trials/T<nn>_<主题> --mock-only --timeout 10
python trials/_toolkit/run_batch.py trials/T<nn>_<主题> --llm-only --timeout 60
```

真实 LLM 运行前需配置 `api_config.json`，见 `docs/howto/run_trials.md`。

## 五、缺陷状态

非 `PASS` 结果由 `trials/INDEX.md` 统一编号与跟踪。缺陷状态机为：

```
发现 → 登记 → 修复（tests/ 补回归）→ 回归试用（触发用例核销）→ 已修复
```

## 六、深入指引

- 如何运行真实 LLM 试用：`docs/howto/run_trials.md`
- 用例契约与判定逻辑：`trials/_toolkit/CONTRACT_FORMAT.md`
- 分类、级别与命名：`trials/_toolkit/CLASSIFICATION.md`
- 本机与自定义 API 服务：`trials/_toolkit/LLM_SERVICE.md`
