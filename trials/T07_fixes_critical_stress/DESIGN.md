# T07_fixes_critical_stress — 四项修复批判性对抗 + 旧套件全量重跑（2026-08-14）

> 2026-08-14。**试用与记录任务，不是修复任务（用户 2026-08-14 明确：不查看内核代码成因、
> 不直接修改任何内容，发现问题只记录）**。目标：对 T05/T06 剩余代码缺陷四项修复
> （CROSSMOD-LLM-1 跨模块类型注解解析 / KI-2 统一 Optional 值模型 / 幽灵诊断码根治 /
> set_mock_mode 对称开关）后的最新内核做**批判性对抗试用**；**充分复用已有试用地基**
> （_toolkit 工具链 + T01-T06 套件用例模式 + 既有缺陷编号体系），并**对以前已有试用
> 体系 T01-T06 全量重跑**（用户强调），核对无回归与既有缺陷状态。
>
> 基线：unsafe-vibe-dev 17e75d72（四项修复后），全量 2665 passed / 1 skipped（已实跑确认）。
> 关联：`_HANDOFF_NEXT_TRIAL.md`（本套权威交接）、`_HANDOFF_GENERIC_REMAINING.md`
> （D4 泛型剩余边界 7 项复测）、`_HANDOFF_T05_ISSUES.md`（历史缺陷状态）。

## 一、工作模式与硬约束

| 约束 | 内容 |
|------|------|
| 死循环保护 | 每例经 harness 硬超时 SIGKILL 进程组兜底；无超时不运行（--timeout 必填） |
| 记录优先 | **只记录登记，不查内核成因、不改内核、不改用例**；logs/ + register.jsonl + REGISTER.md 确定性记录 |
| 分层 | mock 用例（快，并行 4-8）+ 真实 LLM 用例（qwen3.6-35b-a3b @ 127.0.0.1:1234，先探测，并行 1-2） |
| 分类 | PASS | GUARD | KERNEL_ISSUE | BOUNDARY | LIMIT | DOC_ISSUE | LLM_BEHAVIOR | HARNESS（CLASSIFICATION.md） |
| 登记纪律 | 非 PASS 先对照 KNOWN_LIMITS/docs 分诊（LIMIT ≠ 免罪）；缺陷编号全局唯一（INDEX.md） |
| 禁 push | 全程本地 commit |

## 二、检测矩阵

### D0 — 旧套件全量重跑（用户强调，当前 HEAD 下 T01-T06 重跑）

| 套件 | 用例 | 重跑方式 | 核对点 |
|------|------|----------|--------|
| T01_llm_full | 104（57 LLM + 47 mock） | run_batch（root mock:false） | 零回归；已知 GUARD 保持 |
| T02_enum_import | 9（3 LLM） | run_batch | enum/import 无回归 |
| T03_user_class_generics | 30（mock） | run_batch | 泛型压力无回归 |
| T04_generics_fix_regression | 35（mock） | run_batch | 泛型修复回归无回退 |
| T05_critical_stress | 32 mock + 8 D3 LLM | run_batch(cases/) + 逐目录 D3 | **KI-1（D1-10）/KI-2（D2-03）触发用例转 PASS 核销**；无新缺陷 |
| T06_class_identity | 20（7 LLM，全目录型） | 逐目录 run_one | **CROSSMOD-LLM-1（D3-02/D2-05）转 PASS 核销** |

### D1 — 四项修复回归对抗（mock，重点覆盖区）

| 用例 | 目标 |
|------|------|
| D1-01 | CROSSMOD-LLM-1：跨模块类作函数参数/返回类型注解（geo.Counter） |
| D1-02 | CROSSMOD-LLM-1：跨模块泛型注解 geo.Box[int] 作函数参数/返回 + 容器 list[geo.Box[int]] |
| D1-03 | CROSSMOD-LLM-1：深层模块限定 subpkg.util.Counter（嵌套包） |
| D1-04 | CROSSMOD-LLM-1：跨模块类作字段类型注解（class Wrapper: geo.Counter c） |
| D1-05 | KI-2：Optional 嵌套全组合（Optional[Optional[int]] / Optional[list[int]] / list[Optional[int]] / dict[str,Optional[int]] / tuple[Optional[int],str]） |
| D1-06 | KI-2：for Optional[int] x in [None,5] 迭代元素包装（None→is None True / 5→值） |
| D1-07 | KI-2：None==x / x==None / None is x / x is None 全对称 |
| D1-08 | KI-2：Optional 作字段默认值 + 继承链（auto-init） |
| D1-09 | KI-2：Optional deep_clone 保 _is_some（容器内 Optional） |
| D1-10 | 幽灵码：除零 RUN_DIVISION_BY_ZERO（嵌套函数内） |
| D1-11 | 幽灵码：越界 RUN_INDEX_ERROR（try-except 外/内对比） |
| D1-12 | 幽灵码：键缺失（dict 访问）实际码观察 |
| D1-13 | 幽灵码：属性缺失 RUN_ATTRIBUTE_ERROR（线程内） |
| D1-14 | 幽灵码：0x/0b/0o 残缺 + 进制尾字母 + 残缺科学计数 → LEX_INVALID_NUMBER |
| D1-15 | 幽灵码：缩进失配嵌套块 → PAR_INDENTATION_ERROR |
| D1-16 | set_mock_mode：mock→真实→mock 往返配置状态（mock 层，真实调用见 D3-05） |

### D2 — 对抗组合（mock，挑刺）

| 用例 | 目标 |
|------|------|
| D2-01 | 线程 worker 内跨模块类 + Optional 参数组合 |
| D2-02 | chan/slot + Optional 值传递 |
| D2-03 | 生成器 + Optional（yield Optional[int]） |
| D2-04 | 诊断码在控制流内（try-except 内除零 / 嵌套函数越界 / 线程内键缺失） |
| D2-05 | 容器深嵌套 + Optional（dict[str, list[Optional[int]]]） |
| D2-06 | 跨模块类作内置泛型实参 + Optional 组合（Optional[geo.Box[int]]） |
| D2-07 | lambda + Optional 捕获 |
| D2-08 | 深递归 + 幽灵码（递归内除零触发 RUN_DIVISION_BY_ZERO） |

### D3 — 真实 LLM 批判（qwen3.6-35b-a3b，expect-llm: true）

| 用例 | 目标 |
|------|------|
| D3-01 | CROSSMOD-LLM-1 核销重验：跨模块类 LLM 输出（geo.Point，T06 D2-05 同款重验 + 泛型 geo.Box 输出） |
| D3-02 | 跨模块类 LLM 输出 + 同一模块也有同名类（不误配） |
| D3-03 | Optional 作 LLM 输出目标（@~ 返回 Optional[int]） |
| D3-04 | subpkg.util.Counter 深层模块限定 LLM 输出 |
| D3-05 | set_mock_mode mock→真实→mock 往返真实 LLM 调用 |
| D3-06 | 长提示格式约束（跨模块类目标） |
| D3-07 | 意图 @/@! + Optional/跨模块组合 |
| D3-08 | enum 成员名→值 + mock 共存（T05 D3-04 同类无回归确认） |

### D4 — 泛型剩余边界复测（mock；_HANDOFF_GENERIC_REMAINING.md 7 项，S0-S7 已声称根治，复测现状）

| 用例 | 目标 |
|------|------|
| D4-01 | #1/#7 句柄类值身份：thread[int]/chan[int]/slot[int]/generator[int]/thread_result[int] type() 特化名 |
| D4-02 | #3 generator value_type 嵌套：generator[list[int]] 值 type() |
| D4-03 | #4 元组解包错误类型检查：["x"] 赋 list[int] → 编译期拦截 |
| D4-04 | #5 -> auto 泛型实参推断（容器字面量带实参） |
| D4-05 | #6 *expr 元素级校验 |
| D4-06 | #2 跨引擎 round-trip 多模块同名特化（geo.Box[int] 序列化恢复不误配） |
| D4-07 | 句柄类特化 is_assignable 编译期封闭（generator[int] = gen_str() → 拦截） |

### D5 — 文档核验（DOC_ISSUE 记录，不改正文）

- KNOWN_LIMITS §10.2 跨模块类措辞重估（CROSSMOD-LLM-1 修复后裸名返回路径措辞是否过时）
- 修复面文档完整性：03_operators §3.5 / 03_type_system §8 / 15_diagnostics 触发条件 / 11_modules set_mock_mode
- 试用中一切行为与文档不符处 → DOC_ISSUE 记录

## 三、运行

```bash
# 服务探测（每次试用前必做）
curl -s -m 5 http://127.0.0.1:1234/v1/models   # 期望含 qwen3.6-35b-a3b
# T07 全量（mock 先 + llm 后）
python _toolkit/run_batch.py T07_fixes_critical_stress --timeout 45 --parallel 4 --repo-root <repo>
# 旧套件重跑（driver：rerun_old_suites.py，处理文件/目录混合布局 + 各套自有 api_config）
python trials/T07_fixes_critical_stress/rerun_old_suites.py --timeout 60 --parallel 4
```

## 四、产出

- `logs/` + `register.jsonl` + `REGISTER.md` + `REPORT.md`
- 旧套件重跑对照（T01-T06 各套 register 增量 B- 记录 vs 原记录）
- 缺陷登记（PENDING_TASKS + INDEX.md 状态更新，只登记不修复）
- D5 文档核验 DOC_ISSUE 清单（正文修改待用户确认）
- 收尾同步 NEXT_STEPS/HANDOFF/WORKLOG。全程本地 commit、禁 push。
