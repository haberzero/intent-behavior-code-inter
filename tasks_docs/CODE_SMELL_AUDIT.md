# 代码异味核对分析 — 独立分支任务（技术债）

> **来源**：2026-08-02 反射排查。用户指出对话与代码分析中反复出现的"兜底、混合方案、双轨制、多轨制、双通道、多通道、双形态、三策略"等表述（及同类模式：双写真相、半接通、死分支、恒真/恒假探测、防御姿态、承重探测、回退、静默降级、best-effort）可能暗示代码异味，属技术债。
> **状态**：周期事实回顾（2026-08-09 完成 A/C 区全部数据行核验，B7 已核验）；D1/D2 全仓模式扫描仍待做。独立分支（不与主线混置）
> **核验基准**：`.opencode/skills/code-quality/SKILL.md` 健康诊断十查 + 判定基准（A 职责分离合法保留 / B 穿透应修根因 / 死代码删除 / 双通道收敛单一入口）
> **方法**：证据驱动——逐点禁用验证/实测，禁静态推演；每批 `python -m pytest tests/` 全量零回归。
> **纪律**：不写单一反射关键字作检索信号；以机制理解 + 模式覆盖自主检索。

---

## 一、异味术语与代码位置总清单

> 标注：**【保留】**=承重/分层/设计内（已证据确认）｜**【待核验】**=疑似异味未定案｜**【已记录】**=已有专项任务

### A. 兜底 / fallback 家族（静默回退、默认值降级）

| # | 位置 | 特征 | 状态 |
|---|---|---|---|
| A1 | `compiler/semantic/passes/_expression_visitors.py:303` | resolve_call_return 统一入口外直读 return_type 作最后兜底（功能性双通道） | **已记录并处置** |
| A2 | `llm_executor/_prompt.py:26/41-48/59/84/315` | to_native/__to_prompt__ 多级 fallback 链（异常驱动逐级降级） | **已核验：窄化 + fail-fast（2026-08-09）**——`_obj_to_prompt_str`/`_obj_to_payload` 仅对协议缺失（AttributeError）回退，用户实现体内真实 bug（TypeError 等）fail-fast / 经 `kernel_diagnostic` 上报（KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK），非静默吞错 |
| A3 | `llm_parsing_strategy.py:287-316/356` | DefaultParsingStrategy 兜底 + "safe fallback just in case" | **已核验：设计内 LLM 重试契约（2026-08-09）**——解析失败→`uncertain_result`（触发 llmexcept retry），是语言层"LLM 输出不确定→重试"的承载，非吞错 |
| A4 | `spec/registry/_inference.py:63/93` | 无显式返回类型 → axiom fallback → `resolve("any")` | **已核验：设计内动态类型逃生（2026-08-09）**——`any` 是语言显式未知类型标记，方法 docstring 记录解析序尾段，非掩盖 |
| A5 | `vm/handlers/_shared.py:385-386` | 同步后备路径兜底字段（CPS 主路径无视） | **已核验：设计内同步后备契约（2026-08-09）**——`_execution_context` 仅作 host/反序列化后同步 `.call` 后备；CPS 主路径经 `_vm_invoke_behavior` 无视之（callables.py:97-98 记录 ContextVar 优先解析）。可达（coordinator.py:289 线程体/宿主路径），边界明确非吞错 |
| A6 | `vm/handlers/assignment.py:52-86` | dispatch_eager 失败兜底同步路径（"极少触发"） | **已核验：显式条件分派（2026-08-09）**——`dispatch_eager` 仅对非 llmexcept/parallel 开/非 cell 捕获目标启用；复杂目标/llmexcept/parallel 关走同步路径是文档化条件决策（非失败兜底），`dispatched_future is None` 是分派判定非降级 |
| A7 | `vm/handlers/llm_behavior.py:140` | 防御性兜底 handler（"解析器不再生成此节点类型"） | **已失效（2026-08-09 事实回顾）**——目标（不可达 `IbBehaviorInstance` handler）已于 R3 批次（f5d3f94，2026-08-05）删除（dispatch + llm_behavior 清理）；条目行号随文件漂移已失准 |
| A8 | `llm_except_frame.py:186-194` | 深克隆兜底 / `__restore__` 失败 best-effort 保留当前状态 | **已核验：协议回退+诊断上报（2026-08-09）**——`__snapshot__` 失败经 `kernel_diagnostic`（KDIAG_PROTOCOL_SNAPSHOT_FALLBACK）上报 + 深克隆回退，非静默（PT-FEAT-9 观测面承载） |
| A9 | `vm_executor.py`（CPS 调度循环） | CPS 求值 vs fallback 双路径 | **已核验：结构化分派（2026-08-09）**——调度循环对 child 类型（None/Waitable/UserFunctionCall/str uid）的条件分支是 CPS 协议的结构化处理，非降级兜底 |
| A10 | `objects/kernel/base.py` `receive` | 内置类型 call 方法 Python 直调兜底 | **已核验：设计内公理下沉（2026-08-09）**——`__call__` 经公理能力探测下沉（非 hasattr 探测），统一消息分派入口 |
| A11 | `kernel/registry.py:388` | make_llm_parse_error 类查找逐级回退 | **已核验：设计内错误构造降级链（2026-08-09）**——LLMParseError→Exception→None 为 bootstrap 边界防护；正常路径首分支命中。终态 None 为 edge-case 最后兜底（下游会暴露为运行时错误），非静默吞错 |
| A12 | `engine.py:183/245/248/270/272` | plugin_paths 多优先级来源 + 嗅探兜底 | 设计内（多优先级，非异味） |
| A13 | `binding_analysis_pass.py:513/537/922` | 无名称兜底 / 运行时守卫兜底 / 父作用域查找兜底 | **已核验：设计内边界兜底（2026-08-09）**——三处均有显式非适用性论证（513 非 module spec 直接 False；537 owned_scope 缺失运行时守卫；922 仅覆盖函数体完全未出现该名的退化情形），非掩盖 |
| A14 | `runtime_context.py:121-122` | 无 UID 引导期 fallback_uid | 设计内（引导期；assert 已强制 uid/name） |
| A15 | `objects/kernel/_helpers.py` | 节点形状兼容 fallback | **已失效（2026-08-09 事实回顾）**——注释明示"无节点形态嗅探兜底"：形状嗅探已消除，改用侧表 node_to_type 单一判别源 |
| A16 | `kernel/axioms/primitives/base.py:103` | 多模态 payload 文本 fallback | 设计内（封存 feature） |

### B. 双轨 / 双通道 / 双形态 / 多通道

| # | 位置 | 特征 | 状态 |
|---|---|---|---|
| B1 | `serialization/serializer.py:119 _collect_symbol` | Symbol / MemberSpec 双形态判别（kind 字符串 vs 枚举） | **保留**（证据确认承重） |
| B2 | `runtime_serializer.py:255` | IModuleScope 双形态（IbNativeObject vs ScopeImpl） | **保留**（双实现协议） |
| B3 | `runtime_serializer.py:201` | `__to_descriptor__` 协议返回鸭子判别 | **保留**（协议不保证 IbObject；测试有 mock） |
| B4 | `kernel/axioms/primitives/enum.py:104/110`、`kernel/registry.py:298` | kernel 层无法导入 runtime → 鸭子类型 | **保留**（分层强制） |
| B5 | `_expression_visitors.py:352/359` | 三策略签名解析（param_descriptors / param_types / 无静态签名） | **保留**（三策略设计，承重） |
| B6 | `llm_except_frame.py:101` | 活跃 intent_context IBCI 指针与 `_intent_ctx` 双轨断裂风险 | 待复核（快照恢复正确性） |
| B7 | `vm_executor.py`（CPS 调度循环） | CPS 主路径 + fallback 双路径（同 A9） | **已核验：同 A9（2026-08-09）**——结构化分派非降级兜底 |
| B8 | `interpreter.py:17 注释` | 自述"无 fallback_visit，无 assign_to_target" | 信息（确认单路径） |

### C. 静默 except / 静默降级（fail-fast 违反面）

| # | 位置 | 特征 | 状态 |
|---|---|---|---|
| C1 | `module_system/discovery.py:158` | `except ImportError: pass`（协议1探测失败） | 设计内（探测语义） |
| C2 | `module_manager.py:77/147/156` | `except Exception: pass` / `except AttributeError: pass` | **已核验：设计内（2026-08-09）**——`:77` 清除缓存后 re-raise（非吞）；`:147/156` AttributeError → 显式 `InterpreterError`（fail-fast） |
| C3 | `llm_executor/_scheduler.py:138` | `except Exception: pass` | **已核验：标准 `__del__` best-effort（2026-08-09）**——GC 期 `shutdown(wait=False)` 非阻塞清理，异常无害（标准 Python 模式） |
| C4 | `objects/kernel/native_module.py:113-129` | `except KeyError/AttributeError: pass`（**原 4.3.4 吞错根因面**） | **已核验：协议降级链（2026-08-09）**——receive 三层分派（member access → scope.receive → base 公理），KeyError/AttributeError 是"本层未处理"的协议信号，super() 是第三层非吞错 |
| C5 | `modules/file_impl.py:150` | `except (OSError, ValueError): return False`（**原 5.6：沙箱权限降级"文件不存在"**） | **已核验：设计内（2026-08-09）**——`_resolve_path` 沙箱越权抛 `InterpreterError`（不被 except 捕获，正确传播）；except 仅捕 OS 级路径错误（非法路径→"不存在"语义），与 docstring"权限拒绝必须传播"一致 |
| C6 | `kernel/config.py:47` | `except OSError: return {}`（**原 5.8：损坏 JSON 静默吞**） | **已核验：已解决（2026-08-09）**——JSONDecodeError 已改 fail-fast `raise ValueError`（`Invalid CONFIG_FILENAME: malformed JSON`）；`OSError` 分支为"文件不存在→空配置"（存在性语义）非损坏掩盖 |
| C7 | `base/support/fuzzy_json.py` | 5 处 JSONDecodeError/ValueError pass（容错解析） | **已核验：设计内容错多策略解析（2026-08-09）**——LLM 输出非严格 JSON，解析链（严格→剥 codeblock→python 字面量）是功能性 fallback 链，注释明示非 RFC 严格 |
| C8 | `base/diagnostics/debugger.py:59` | 配置解析异常 pass | **已解决（2026-08-06，OBSERVABILITY 2A：机制整体移除）** |
| C9 | `ibci_modules/ibci_idbg/core.py:383/398` | `except Exception: pass` | **已解决（2026-08-06，OBSERVABILITY 2C：show_intents 单一权威源，去双源回退）** |
| C10 | `extension/auto_discovery.py:73-81` | OSError/PermissionError/Exception 静默 | **已核验：目录扫描容错 + 加载 fail-fast（2026-08-09）**——listdir 不可读跳过（发现期容错）；`_load_plugin_spec` 失败 re-raise `RuntimeError`（非静默） |
| C11 | `objects/kernel/base.py:113/140` | `__to_prompt__`/`__outputhint_prompt__` 兜底 | 设计内（协议降级有明确语义） |
| C12 | `llm_except_frame.py:318` | `except Exception: return a is b`（值比较 best-effort） | 设计内（浅比较兜底） |
| C13 | `_prompt.py:154` | StopIteration → value/"" | **已核验：标准生成器耗尽信号（2026-08-09）**——段迭代结束返回 `si.value or ""`，控制流处理非吞错 |
| C14 | `kernel/axioms/primitives/sequences.py:178/257/336` | ValueError → 解析失败返回（有明确 retry_hint） | 设计内（解析错误语义） |

### D. 防御性探测 / 双路径判别残留

| # | 位置 | 特征 | 状态 |
|---|---|---|---|
| D1 | 约 30 处 `getattr(x, ..., None) or []` 模式 | 防御性兜底（`core/` 内） | 待核验（逐点判恒真/承重；专项独立窗口） |
| D2 | 45 文件含 `hasattr` | 大部分为协议/分层合法反射，需分类复核 | **抽样已核验（2026-08-09）：协议/primitive 边界判别为主**——`hasattr(val, 'receive')` 系判别 IbObject（可消息分派）vs 原始 Python 值（协议层边界检查，_prompt.py:35/70、module_manager.py:43、media.py:46）；`hasattr(value, '__dict__')` 系 base 层泛型对象遍历（serialization.py:27）。全量逐点分类仍待专项窗口 |
| D3 | 5 处 to_native/ib_class 鸭子判别保留（B3/B4） | 见 B 分类 | 保留（已证据确认） |

### E. 本次已处置项的复核边界（技术债收尾）

| # | 内容 | 复核点 |
|---|---|---|
| E1 | `unbox()` 边界函数（85 处转换） | 复核恒等回退→unbox 转换的边界语义（str/bool/int 回退、callable 透传、memo 传参站点） |
| E2 | 承重保留站点（descriptor/sentinels memo/loader callable/kernel 分层） | 复核保留理由是否仍成立 |
| E3 | 死代码删除（registry.is_truthy/_cast_*/export_metadata/IntegrityChecker/is_package_dir/create_plugin/create_instance/Diagnostic.node_uid） | 复核零消费方判定是否遗漏动态引用 |
| E4 | 组8 处置（_extract_signature fail-fast、IbNativeFunction.__getattr__ 删除、method_missing 删除） | 复核 fail-fast 是否引入插件兼容回归；__getattr__ 删除是否有隐性消费者 |
| E5 | `_expression:304` 兜底、loader↔check 复制 | 已记录并处置；loader↔check 复制为设计决策，不重复修复 |

---

## 二、核验流程（独立分支执行）

1. **分类定案**：对 A/C/D 每项用判定基准定性——A 合法保留（协议/分层/多优先级设计）／B 修复根因／死代码删除／双通道收敛。禁用验证（临时移除后全量测试）确认"死代码/冗余"判定。
2. **优先级**：A7（疑似死代码）→ C4/C5/C6（已知吞错面）→ C3/C9/C10（宽 except）→ C7/C8（容错 vs 掩盖）→ A2/A3/A5/A6（fallback 链）→ D1/D2（防御性探测分类）→ B6（双轨复核）。
3. **每批**：`python -m pytest tests/` 全量零回归 + 全仓残留扫描。
4. **收尾**：定案结果回写本清单（标注 ✅ 已修复／保留），已修复项删除，保留项说明理由；不写独立 ADR。
