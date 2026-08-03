# 条件分支与异常嵌套复杂度审计 — 独立分支任务（技术债）

> **来源**：2026-08-02 用户裁定。异常过多的 if-else 并用、异常过深的 if-else、过多过深的 except 嵌套（及同类复杂度异味）属技术债，需独立分支核对分析。
> **状态**：待执行（独立分支，不与主线混置）
> **方法**：AST 静态度量 + 证据驱动人工复核；每批 `python -m pytest tests/` 全量零回归。
> **核验基准**：`.opencode/skills/code-quality/SKILL.md` 判定基准（A 合法保留 / B 修复根因 / 死代码删除 / 双通道收敛）。

---

## 一、度量基线（AST 全仓扫描）

### 1.1 深层嵌套（if/try/with/for/while 组合嵌套深度 ≥ 5）

| 深度 | elif 链长 | 文件 | 说明 |
|---|---|---|---|
| **14** | **13** | `runtime/serialization/runtime_serializer.py` | `_collect_instance` 巨型类型分派链（ib_class.name 分支） |
| **10** | **9** | `compiler/lexer/core_scanner.py` | 扫描器状态机分支 |
| 9 | 8 | `semantic/passes/binding_analysis_pass.py` | 符号/赋值分析 |
| 9 | 5 | `vm/handlers/_shared.py` | LLM 调用参数处理 |
| 9 | 3 | `kernel/spec/registry/_members.py` | 成员解析 |
| 9 | 2 | `compiler/scheduler.py` | 导入解析 |
| 8 | 5 | `parser/components/statement.py` | 语句解析 |
| 8 | 3 | `interpreter/interpreter.py` | 解释器 |
| 7 | 7 | `loader/artifact_rehydrator.py` | 反水化 |
| 7 | 6 | `ibci_modules/ibci_schema/core.py` | schema 插件 |
| 6 | 6 | `parser/components/declaration.py` | 声明解析 |
| 6 | 3 | `parser/components/expression.py` | 表达式解析 |
| 6 | 2 | `objects/primitives/callables.py` | 可调用对象 |

### 1.2 宽 except（bare / `except Exception`）— 全仓 **70 处**

| 位置 | 特征 | 初始判定 |
|---|---|---|
| `ibci_modules/ibci_net/core.py`（**12 处** 75/87/99/111/123/135/147/158/169…） | HTTP 错误统一 `except Exception` | **已核验 2026-08-02**：9 处（get/post/put/delete/head/get_json/post_json/post_form/get_status_code）均为 `except Exception as e: raise RuntimeError(...)`——重抛非吞掉（**fail-fast 保留，非掩盖型兜底**）；但**过度宽捕获**会把非网络程序错误（如参数 `TypeError`）误包成 "Network failed" 掩盖真实 bug。建议窄化为 `requests.RequestException` + json 解码 `ValueError` 单独处理——错误类型细化属行为变更，**列待决策（本批未改）** |
| `engine.py`（5 处 388/477/523/751/818） | 编译/运行包装 | 待核验 |
| `compiler/scheduler.py`（4 处 151/280/323/605） | 导入/编译 | 待核验 |
| `interpreter/llm_parsing_strategy.py`（5 处 143/209/250/270/279） | LLM 解析兜底 | 待核验【**已核验 2026-08-03**：合法解析失败回退链——解析失败→`uncertain_result`/`None`，驱动 llmexcept 重试协议（"LLM 输出不确定→重试"语言语义），非吞语言级异常、非静默掩盖。边缘：用户 `__from_prompt__` 抛真异常会被按"不确定"处理，属"输出不确定"语义固有取舍，可接受】 |
| `llm_executor/_prompt.py`（4 处 40/47/81/253） | prompt 降级链 | 待核验【**已核验 2026-08-03**：合法 prompt 表示降级链——对象→prompt 文本转换失败时降级 `to_native()`/`str()`/None（构建提示词的尽力而为韧性），非掩盖程序错误。边缘：用户 `__to_prompt__` 内真 bug 会被静默吞掉并降级，可考虑窄化 except，属可选优化】 |
| `llm_except_frame.py`（3 处 185/266/318） | 快照/恢复 | 部分设计内（best-effort） |
| `user_functions.py`（2 处 61/220）、`base.py:95/127`、`functions.py:66` 等 | 原生函数包装 | 待核验（部分设计内：ThrownException 穿透）【**已核验 2026-08-02**：**无语言级异常误吞**。`functions.py:66` 为正确示范——显式透传 `InterpreterError` 与 `ThrownException`（用户代码主动抛的语言级异常，须由 IbTry/顶层 try 体系处理），仅将真正的原生 bug 包为 `InterpreterError`；`base.py:95`（cast 失败→透传后抛明确 TypeError）、`:113`（`__to_prompt__` 显示兜底，窄 except `(AttributeError, InterpreterError)`）、`:127`（`__from_prompt__` 协议返 `(False, 错误)`，非静默）、`user_functions.py:61/220`（模块导入失败→`raise InterpreterError(...) from e` 重抛）——均 fail-fast / 协议契约，非掩盖型兜底】 |
| `ibci_ai/core.py`（4 处 98/167/249/466） | OpenAI 客户端 | 待核验 |
| `ibci_idbg/core.py`（2 处 383/398）、`auto_discovery.py`（4 处） | 观察者/发现 | 待核验 |
| `llm_except_frame.py:318`、`debugger.py:139` | 值比较/调试 | 设计内 |

### 1.3 嵌套 try（全仓 **5 处**）

| 位置 | 说明 |
|---|---|
| `vm/handlers/_shared.py:530` | LLM 调用处理内嵌套 try |
| `interpreter/llm_parsing_strategy.py:273` | 解析兜底链内嵌套 |
| `interpreter/module_manager.py:172` | 模块导入 |
| `interpreter/intrinsics/io.py:25` | IO 读取（与局部 import 同点，见 LOCAL_IMPORT_AUDIT L12） |
| `objects/kernel/ib_class.py:124` | 类方法解析 |

> 逐处核验异常处理范围是否过宽、是否可扁平化（try 范围应尽量窄，嵌套 handler 归属难判断）。

### 1.4 混合 if-else + 异常流控制（多级 fallback 链）

> 与 `CODE_SMELL_AUDIT.md` A 家族重叠（`_prompt.py`、`llm_parsing_strategy.py` 的多级 try→fallback 降级链）。此处重点核验"异常当控制流"——用 try/except 探测能力/形态而非数据判定。

---

## 二、我的工程经验补充判断（超出用户列举的两类）

1. **守卫子句缺失**：深层 if 嵌套中大量为"先检查再深入"，应改为守卫子句提前 return/continue，降低嵌套深度（`runtime_serializer` 类型分派、`core_scanner` 状态机为重点）。
2. **长 elif 链 → 查表/策略分派**：`elif ≥ 6` 的链（13/9/8/7/6 处）应评估改显式分派表（类似 VM `_dispatch` / vtable 的正面模式），消除线性决策梯。
3. **宽 except 吞掉语言级异常**：`except Exception` 需核对是否误吞 `ThrownException`/`InterpreterError`（语言级异常必须穿透，见 `functions.py:66` 已有正确示范）；凡含 `except Exception: pass` 的静默点并入 `CODE_SMELL_AUDIT.md` C 家族协同核验。
4. **异常做能力探测**：try/except 探测"是否支持某操作"（而非协议/类型判定）——本家族最危险变体，命中即修（对应工作模式定论：协议驱动）。
5. **嵌套 with/for + try 混合**：资源管理与异常处理交错，`finally` 语义难核——逐处核对资源释放路径。
6. **布尔表达式超载**：单条件过长（多 and/or 无括号）——可读性异味，随重构顺带处理。

---

## 三、核验流程

1. 对每处按判定基准定性：设计内（状态机/分派表/协议降级有明确语义）保留；可扁平化/查表化/窄化 → 标记修复方案。
2. 优先级：宽 except 误吞语言级异常（最高）→ 异常当控制流 → 深度 >7 的巨型分派链 → elif ≥6 决策梯 → 嵌套 try → 守卫子句扁平化。
3. 每批 `python -m pytest tests/` 全量零回归；收尾定案回写本清单。
