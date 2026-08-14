# 交接：重启真实批判性试用 + 文档全方位同步（下一 session 主任务）

> 2026-08-14 编制。承接本 session 的 T05/T06 剩余代码缺陷四项修复（全部完成，
> 全量 **2665 passed / 1 skipped** 零回归）。
> **用户指示：下一 session 任务 = 重启真实批判性试用 + 文档内容的全方位同步更新。**

## 〇、基线状态（本 session 交接时）

- 分支：`unsafe-vibe-dev`，工作树干净，最后 commit `6d099036`。
- 全量 pytest：**2665 passed / 1 skipped**（本 session 起 2616 → 2665，+49 判别性回归）。
- LLM 服务：**在线**（qwen3.6-35b-a3b @ 127.0.0.1:1234，思考已禁用，响应 <1-2s）。
- 本 session 四项修复 + 独立复核整改，设计记录：
  - `_code_optional_unify.md`（CROSSMOD-LLM-1 变更 A + KI-2 统一 Optional 值模型）
  - `_code_ghost_codes.md`（幽灵诊断码 7 发射 + 1 删减 + RUNTIME_ERROR 替换 + CAT-7）
  - `_code_set_mock_mode.md`（set_mock_mode 对称开关）

## 一、本 session 修复的代码面（真实批判性试用的重点覆盖区）

> 四项修复改动面广（47 文件 +1617 行），下一 session 的批判性试用应**针对这些改动面**
> 做对抗性验证，确认无回归、无隐藏缺陷。每项给出已落判别性回归与**建议新增对抗用例方向**。

### 1.1 跨模块类型注解解析（CROSSMOD-LLM-1）

- **改动**：`_resolve_type`/`resolve_type_annotation`/`_resolve_annotation`/
  `_annotation_to_typeref` 支持 `IbAttribute` 点号限定注解（`geo.Counter`，
  含泛型 `geo.Box[int]`），行为节点 node_to_type 绑定 module 限定 spec。
- **已落回归**：`tests/runtime/test_ibc_file_imports.py` +3（node_to_type 绑定 /
  泛型注解 / 无 `__from_prompt__` fail-fast）。
- **建议对抗**：跨模块类作行为表达式目标在**函数参数/返回/容器/嵌套包**位置的组合；
  跨模块类作 LLM 输出 + 同一模块也有同名类（不误配）；`subpkg.util.Counter` 深层
  模块限定。

### 1.2 统一 Optional 值模型（KI-2）

- **改动**：`wrap_optional` 单一包装权威 + `is_none_value` 统一判空 + 全值创建路径
  （参数 spec 解析 / 字段 member_types / 容器元素）+ `is`/`is not` None 双向语义 +
  `is_none()` + `None==Opt` 对称 + deep_clone 保 `_is_some` + llmexcept 类符号跳过。
- **已落回归**：`tests/runtime/test_optional_value_model.py` +20（局部/参数/返回/
  字段/容器/嵌套/对称/deep_clone）+ `tests/runtime/test_optional_runtime.py` 保持。
- **建议对抗**（这是用户此前警告"可能藏更深根源"的领域，须重点挑刺）：
  - `Optional[Optional[int]]`、`Optional[list[int]]`、`list[Optional[int]]`、
    `dict[str,Optional[int]]`、`tuple[Optional[int],str]` 全组合。
  - Optional 参与序列化 round-trip / llmexcept 快照 / 深克隆 / 线程 worker。
  - `for Optional[int] x in [None,5]` 迭代元素包装。
  - `None == x` / `x == None` / `None is x` / `x is None` 全对称。
  - Optional 作字段默认值 + 继承链 / auto-init。

### 1.3 幽灵诊断码根治

- **改动**：7 码发射（`_runtime_error_code_for` 异常映射 + collections/permissions
  显式码 + llmexcept 快照警告 + 词法器 LEX_INVALID_NUMBER + indent_processor 改码）；
  PAR_MULTIPLE_INTENTS 删减；`InterpreterError` 默认码 RUNTIME_ERROR →
  RUN_GENERIC_ERROR；CAT-7 可发射性契约。
- **已落回归**：`tests/contracts/test_diagnostic_emission.py` +10 +
  `tests/contracts/test_diagnostic_catalog.py` CAT-7。
- **建议对抗**：除零/越界/键缺失/属性缺失/权限在**不同上下文**（嵌套函数/线程/
  try-except 内）的码是否正确；`0x`/`0b`/`0o` 残缺 + 进制尾字母 + 残缺科学计数；
  缩进失配嵌套块。

### 1.4 set_mock_mode 对称开关

- **改动**：`set_mock_mode(enable: bool = True)` 对称开关（enable=False 退出 +
  重建客户端 + 未配置 fail-fast）。
- **已落回归**：`tests/runtime/test_set_mock_mode_switch.py` +3。
- **建议对抗**：mock→真实→mock 往返在**真实 LLM 调用**下（非仅 MOCK: 指令）验证；
  mock 模式退出后配置缺失 fail-fast 的报错路径。

## 二、重启真实批判性试用（T07）

> 复用 `tasks_docs/trials/` 成熟体系（`_toolkit/run_one.py` + `run_batch.py` +
> `CLASSIFICATION.md` + `LLM_SERVICE.md`）。新建 `trials/T07_fixes_critical_stress/`
> （命名遵循 `T<nn>_<主题>`，INDEX.md 登记）。

### 2.1 试用矩阵建议

| 维度 | 覆盖 |
|------|------|
| **D1 本 session 修复回归** | 四项修复的判别性用例在真实环境重跑（见 §一，各"建议对抗"） |
| **D2 对抗组合** | 跨模块 LLM + Optional 组合、并发（thread/chan）+ 修复面、诊断码在控制流内、mock↔真实切换 + 修复面 |
| **D3 真实 LLM 批判** | 跨模块用户类 LLM 输出（D3-02/D2-05 已转 PASS 须重验）、Optional 作 LLM 输出目标、enum/mock 共存、长提示 |
| **D4 泛型剩余边界复测** | `_HANDOFF_GENERIC_REMAINING.md` 7 项（句柄类值身份/type_pool 匹配/元组解包/auto 推断/*expr）——验证是否仍为已知边界或已变化 |
| **D5 文档核验** | 见 §三 |

### 2.2 运行纪律

- 死循环保护：每例 harness 超时 SIGKILL + `--max-inst`；无超时不运行。
- 先 mock 后 llm（`run_batch.py` 默认）；LLM 服务先探测（`curl /v1/models`）。
- 只记录登记，不修复；缺陷登记 PENDING_TASKS + INDEX 编号全局唯一。
- 全程本地 commit、禁 push。

## 三、文档内容全方位同步更新

> 本 session 改动 docs 4 文件（03_operators / 03_type_system §8 / 11_modules /
> 15_diagnostics），但**仅针对修复点**。下一 session 在试用后应做**全方位**同步：

### 3.1 试用暴露 → 文档更新

- 试用发现的任何行为与文档不符 → 修文档或登记 DOC_ISSUE（按 doc-governance 流程）。

### 3.2 本 session 修复面的文档完整性核对（可能仍有缺口）

| 文档 | 状态 | 需核对 |
|------|------|--------|
| `03_operators.md` §3.5 | ✅ 已改（is None 三等价） | 是否有其它 `is`/`None` 表述残留 |
| `03_type_system.md` §8 | ✅ 已改（is_none + 统一值模型） | `is_none` 是否出现在应出现处；§8 完整性 |
| `15_diagnostics.md` | ✅ 已改（7 码去未发射 + 删 PAR_MULTIPLE_INTENTS + 快照 WARNING） | CAT-6 doc parity 已保证码集合；但每个码的**触发条件描述**是否与实现精确一致（试用核验） |
| `11_modules.md` | ✅ 已改（对称开关） | guide/01 是否需补 `set_mock_mode(False)` 示例 |
| `KNOWN_LIMITS.md` | ⚠️ 未改动 | **§10.2 "LLM 输出解析跨模块用户类 graceful 退化"边界需重估**——CROSSMOD-LLM-1 修复后，裸名返回路径仍退化但点号限定注解已可用，措辞可能过时；§十四 用户类泛型边界；Optional 相关若无记录可能需新增 |
| 其它 syntax/architecture/guide/howto | ⚠️ 未改动 | 试用后核对与实现一致性（如 Optional 判空、诊断码、跨模块类、set_mock_mode 出现在任何教程/参考中） |

### 3.3 文档治理纪律

- 走 doc-governance Phase 0-8（先审计 → 规划 → 交叉核验 → 实施 → 读者视角）。
- `docs/` 只面向人类，不引入 agent 元信息。
- KNOWN_LIMITS 修正须实证（不凭空改）。

## 四、已知参考（T05/T06 遗留）

- `_HANDOFF_T05_ISSUES.md`：四项已标"已修复"，**历史记录保留**（不回改）。
- `_HANDOFF_GENERIC_REMAINING.md`：7 项泛型剩余边界（均 P3 已知边界，建议 D4 复测）。
- `trials/INDEX.md`：缺陷编号全局唯一（新缺陷从 `KERNEL_ISSUE-*` 继续编号）。
- `PENDING_TASKS.md` §〇：供应商感知思考禁用机制（P2 待设计）等长期项。

## 五、任务控制文档同步清单（本 session 已完成）

- `NEXT_STEPS.md` 头注/交接要点：四项修复完成记录 + 设计文档指针 ✅
- `PENDING_TASKS.md` §〇：四行标已修复 + DOC_ISSUE 行代码联动项标完成 ✅
- `_HANDOFF_T05_ISSUES.md` §六：四项标已修复 ✅
- `WORKLOG.md`：五项条目（四项修复 + 收尾）✅
- `HANDOFF.md` §2.1：**⚠️ 待下一 session 更新为"重启真实批判性试用 + 文档同步"主任务**（本交接文档即权威指针）

## 六、启动步骤（下一 session 读我）

1. 读本文件 + `NEXT_STEPS.md` + `PENDING_TASKS.md` §〇 + `WORKLOG.md`（近期）+ git `6d5bcb74..HEAD`。
2. 探测 LLM 服务（`curl -s -m 5 http://127.0.0.1:1234/v1/models`）。
3. 建 `trials/T07_fixes_critical_stress/`（DESIGN.md + api_config.json + harness 软链 +
   cases/ + 头部断言），按 §二 矩阵设计用例。
4. 跑 mock 组 → llm 组 → 汇总 REGISTER/REPORT → 登记缺陷 → 按 §三 文档同步。
5. 全程本地 commit、禁 push；不触碰 main。
