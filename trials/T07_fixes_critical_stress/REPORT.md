# T07 批判性对抗试用报告（2026-08-14）

> 基线：unsafe-vibe-dev 17e75d72（T05/T06 剩余缺陷四项修复后，全量 2665 passed / 1 skipped 已实跑确认）。
> 试用对象：四项修复面（CROSSMOD-LLM-1 跨模块类型注解解析 / KI-2 统一 Optional 值模型 /
> 幽灵诊断码根治 / set_mock_mode 对称开关）+ **旧套件 T01-T06 全量重跑**（用户强调）+ 泛型剩余边界复测。
> 方法：43 新用例（18 D1 修复对抗 + 10 D2 对抗组合 + 8 D3 真实 LLM + 7 D4 泛型边界）经 harness
> 死循环保护运行（mock 并行 6 / LLM 并行 2，qwen3.6-35b-a3b @ 127.0.0.1:1234 真实调用）+ 旧套件
> 238 用例重跑。**本任务是试用/记录/汇报任务（用户 2026-08-14 明确）：不查看内核代码成因、
> 不修改任何内容，只记录登记**。

## 一、结果总览

| 层 | 用例 | 结果 |
|----|------|------|
| D1 四项修复回归对抗（mock） | 18 | **11 PASS + 6 GUARD + 1 KERNEL_ISSUE**（属性读取静默 None） |
| D2 对抗组合（mock） | 10 | **7 PASS + 1 GUARD + 2 KERNEL_ISSUE**（函数内 Optional unwrap / Optional 容器方法） |
| D3 真实 LLM（qwen3.6-35b-a3b） | 8 | **7 PASS + 1 GUARD**（Optional LLM 目标编译期守卫，PT-DECIDE-1 设计内） |
| D4 泛型剩余边界复测（mock） | 7 | **4 PASS + 3 GUARD**（S0-S7 根治全部确认有效） |
| D0 旧套件全量重跑（T01-T06） | 238 | **202 PASS + 24 GUARD + 1 LIMIT + 1 KERNEL_ISSUE(陈旧断言) + 9 HARNESS(5 陈旧断言+4 设计内)** |

**核心结论**：
- **四项修复面零回归、零新缺陷**——跨模块注解解析（参数/返回/容器/字段/深层模块）、Optional 判空
  （is None/is_none/is_some/对称/嵌套容器）、7 幽灵码守卫、set_mock_mode 真实往返全部通过；
  真实 LLM 7/7 全 PASS（含同名类不误配、深层模块限定、意图、长提示、enum、mock↔真实切换）。
- **2 项遗留缺陷核销**：KI-1（线程跨模块类，T05 D1-10 转 PASS）、CROSSMOD-LLM-1（T06 D2-05/D3-02
  转 PASS + T07 D3 系列重验）；KI-2 修复行为确认（T05 D2-03 实际 True|True|False，用例断言陈旧）。
- **新暴露 3 项既有 KERNEL_ISSUE（P1，均围绕 Optional 改动面，验证"Optional 可能藏更深根源"警告）**：
  - **OPTIONAL-SCOPE-1**：函数作用域内 Optional 先 None 后赋值，`unwrap()`/`is_some()` 报
    `Object of type 'None'`（顶层/lambda 正常，路径不一致）；文档 arch/03_type_system §8
    "任何路径可用"不成立。
  - **OPTIONAL-CONTAINER-1**：`Optional[list[int]]` 有值包装后 `len()`/下标不可用
    （`no method 'len'`/`'__getitem__'`）；"接受 T"语义下容器操作断裂。
  - **ATTR-READ-1**：未声明属性**读取**返回 None（静默），仅**调用**路径报 RUN_ATTRIBUTE_ERROR；
    15_diagnostics 触发条件描述与实现不符。
  - 均**只登记不修复**（PENDING_TASKS + INDEX），根因分析留待后续任务。
- **旧套件重跑零回归、零新内核缺陷**：5 处旧用例断言为**陈旧**（值层身份收敛新语义：
  `type()` 显示特化名 `list[int]`/`generator[str]`、chan 泛型实参编译期拦截、D2-03 is None 新语义），
  按 PHASE_D 流程待更新；4 处 helper/smoke/deadloop 为设计内 HARNESS。
- **泛型剩余边界 7 项复测**：句柄类值身份水化（thread[int]/chan[int]/slot[int]/generator[int]）、
  generator 嵌套值类型、元组解包检查、`-> auto` 实参推断、`*expr` 元素级校验、特化赋值封闭
  全部确认（S0-S7 根治有效）。

## 二、新发现明细（3 KERNEL_ISSUE + 5 DOC_ISSUE）

| 编号 | 级别 | 现象 | 证据 |
|------|------|------|------|
| KERNEL_ISSUE-OPTIONAL-SCOPE-1 | P1 | 函数内 Optional 先 None 后赋值，unwrap/is_some 报 Object of type 'None'（顶层正常） | cases/D2-09.ibci + logs/B-D2-09.log |
| KERNEL_ISSUE-OPTIONAL-CONTAINER-1 | P1 | Optional[list[int]] len/下标不可用 | cases/D2-10.ibci + logs/B-D2-10.log |
| KERNEL_ISSUE-ATTR-READ-1 | P1 | 未声明属性读取静默 None（调用才报 RUN_ATTRIBUTE_ERROR） | cases/D1-13.ibci + logs/B-D1-13.log |
| DOC-24 | P2 | arch/03_type_system §8 "任何路径可用"不成立（同 OPTIONAL-SCOPE-1） | — |
| DOC-25 | P2 | §8 Optional 容器方法不可用未说明（同 OPTIONAL-CONTAINER-1） | — |
| DOC-26 | P2 | 15_diagnostics RUN_ATTRIBUTE_ERROR 触发条件与实现不符（同 ATTR-READ-1） | — |
| DOC-27 | P3 | KNOWN_LIMITS §10.2 可补 qualified 路径实证（裸名退化表述仍成立） | — |
| DOC-28 | P3 | 5 处旧套件用例断言陈旧待更新（PHASE_D） | — |

## 三、方法说明（真实 LLM 确认）

- T07 LLM 组与旧套件 expect-llm: true 用例均经本机真实服务调用：先探测
  `curl /v1/models`（qwen3.6-35b-a3b 在线），root api_config `mock: false`；
  T01 B-D3-60 日志输出 qwen 生成中文长文本（4.24s）、T07 D3 系列 0.95-3.46s 全真实调用；
  mock 组（无 expect-llm 标记）经 MOCK: 指令层运行，不触网（设计如此）。

## 四、下一步

1. 3 项新 KERNEL_ISSUE 修复（独立窗口，含 tests/ 判别性回归，Phase D 收敛流程）；
2. 5 处陈旧断言更新（T01 D1-01-001/D1-05-008/D1-05-008b、T03 D2-07、T04 R5-03、T05 D2-03）；
3. DOC-24~27 文档同步（doc-governance，正文修改待用户确认后执行）。
