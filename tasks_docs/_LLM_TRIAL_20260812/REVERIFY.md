# REVERIFY — 修复后回归试用计划（2026-08-12）

> 背景：PT-DEBT-25/26/27/28 + O1/I1/O2 修复 + 文档修正已落地（全量 2252 passed / 1 skipped）。
> 本次重验目的：① 已修复问题的复现用例确认已处理；② 修复触及的子系统的回归验证；
> ③ 与修复相关（可能受影响/可能已被处理）的问题再测试。全部经死循环保护 harness。

## 修复触及的核心文件 → 受影响子系统

| 修复 | 文件 | 受影响子系统 |
|------|------|-------------|
| PT-DEBT-27 异常投递 | `vm_executor.py` | 调度器/Waitable/异常投递（C3 超时、llmexcept、run_batch、线程） |
| PT-DEBT-25 global | `symbol_resolution_pass.py` | 符号解析/作用域（函数/嵌套/nonlocal/global） |
| PT-DEBT-26 import | `scheduler.py` / `_expression_visitors.py` | 模块导入/成员类型解析（整模块/命名/星号/泛型/零参数） |
| PT-DEBT-28 ai API | `_spec.py` | ai 模块 API 契约 |
| O1 调用分派 | `base.py` / `ib_class.py` / `user_functions.py` | 可调用实例/类构造/方法调用/序列化 |
| I1 生成器 __iter__ | `iterable.py` / `user_functions.py` | 迭代协议/生成器/yield from |
| O2 字段默认值 | `ib_class.py` | 类字段/深克隆/序列化 |

## 重验范围

### R1：已修复问题复现用例（应已处理）
- global：D1-02-003b-global-min / D1-02-003-scope
- 整模块 import：D1-11-002-modimport / D1-11-002d/e / D1-11-002g-namedimport
- 异常逃逸：D3-C3-timeout / D3-C3d / D3-C3e（真实 provider 失败可捕获）
- ai API：D3-50/51/51b

### R2：O1/I1/O2 修复验证
- O1 obj() 深递归 / fn 引用 / __call__+LLM / __call__+chan
- I1 生成器 __iter__ for / 生成器 __call__ / yield from 实例
- O2 字段默认值（嵌套 list/用户对象/plain list）

### R3：受影响子系统回归（真实 LLM 组合）
- 调度器/异常：D1-10-001 llmexcept、D3-31 并发 llmexcept、D3-C4 并发扩展
- 生成器：D1-05-008 generator+LLM、D1-05-008b to_list、D1-05-006 lambda
- 模块：D1-11-001 modules、D2-21 plugin、D1-11-006 filejson
- 类型绑定：D1-05-002 recursion（fn 签名/内省）、D1-06-001 oop、D1-06-003 enum
- 调用分派：D1-05-002 高阶 fn、D1-05-007 snapshot、D2-03 类+LLM+slot
- 意图：D1-09-001 intent、D1-09-004 intentctx、D3-30 global-intent

### R4：全量 pytest + 汇总
- 全量 pytest 已 2252 passed；重验结果汇总 REGISTER，报告更新。

## 执行方式
- 复用 `harness/run_one.py`（死循环保护强制）+ `cases/` 既有用例 + `reverify/` 新用例。
- 每例真实 LLM 跑一遍；审阅分类回填 REGISTER。
- 不修复新发现缺陷（记录待评估），除非是本次修复引入的回归（立即报告）。
