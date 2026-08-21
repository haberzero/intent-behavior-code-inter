# REGISTER — T14 fs 模块 + Optional/容器 + 值语义（五大地基新特性）

> 分类/级别/编号规范：`_toolkit/CLASSIFICATION.md`。全部 mock/无 LLM 依赖（确定性）。
> 参考规范版本：_toolkit 当前 HEAD。

## 一、总览

- **用例总数**：9 个，全部经死循环保护（run_batch 默认 60s OS 级超时）。
- **PASS**：8 例；**GUARD**：1 例。
- **KERNEL_ISSUE**：0 项。**BOUNDARY**：0 项。**DOC_ISSUE**：0 项。
- **LIMIT**：0 项。**LLM_BEHAVIOR / HARNESS**：0 项。

## 二、缺陷登记

无缺陷。关键确认：

- **FS-G1**：`file_handle` 只读语义——`fh.write(...)` → `RUN_ATTRIBUTE_ERROR`（捕获确认
  read_only=True，PASS；初版守卫用例泄漏临时文件，改为捕获式 + 清理，无泄漏）。
- **FS-M5（沙箱）**：越出 project_root 的写入 → `RUN_PERMISSION_ERROR: Security Error:
  Permission denied for write on path outside workspace ... IBC-Inter is currently restricted
  to its root directory.`（守卫生效，实测）。**沙箱无漏洞**——初版 `../` 用例仅回到套件根
  （= project_root）未真正越界，改用 `../../` 后正确拒绝。
- **OPT-M1/M2**：Optional[T] 值模型（is_some/unwrap/or_else/None 接受/容器元素）全过。
- **VS-M1**：值语义（复合对象赋值别名、不可变原语赋值复制）与 02_variables §2.8 权威契约一致。

## 三、LIMIT / 待修候选池

无。

## 四、逐例明细

| case_id | 目标 | 期望 | 实际 | 分类 | 级别 | 证据日志 |
|---------|------|------|------|------|------|----------|
| FS-M1 | write/open/read 双入口/remove | h=hello-fs p=hello-fs | 同 | PASS | — | logs/B-T14-FS-M1.log |
| FS-M2 | new 副本 vs overwrite 就地覆盖 | orig=mutated copy=copied | 同 | PASS | — | logs/B-T14-FS-M2.log |
| FS-M3 | exists/remove 生命周期 | pre=False post=True removed=True | 同 | PASS | — | logs/B-T14-FS-M3.log |
| FS-M4 | read_bytes | len=3 | 同 | PASS | — | logs/B-T14-FS-M4.log |
| FS-G1 | file_handle 只读（捕获确认） | read_only=True | 同 | PASS | — | logs/B-T14-FS-G1.log |
| FS-M5 | 沙箱越界写入拒绝 | RUN_PERMISSION_ERROR | 同 | GUARD | P2 | logs/B-T14-FS-M5.log |
| OPT-M1 | Optional 值模型 | a=0 b=1 some=True | 同 | PASS | — | logs/B-T14-OPT-M1.log |
| OPT-M2 | Optional 容器元素 | some=True first=1 | 同 | PASS | — | logs/B-T14-OPT-M2.log |
| VS-M1 | 值语义 | aliased=True copied=True | 同 | PASS | — | logs/B-T14-VS-M1.log |

## 五、结论

- **验证达成**：fs 模块全接口（open/read/read_bytes/write new+overwrite/exists/remove）+
  只读守卫 + 沙箱守卫生效；Optional 值模型 + 容器元素；值语义与权威契约一致。全部确定性通过。
- **确认**：沙箱无漏洞（越界写入被 RUN_PERMISSION_ERROR 拒绝）。
- **下一步**：T15_edge_malicious（恶意边界：`trials/INDEX.md` 33 项起点 + 自行扩展）；
  其余 LLM 层回归按 `trials/INDEX.md` 排布。
