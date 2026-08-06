# 代码异味核对分析 — 独立分支任务（技术债）

> **来源**：2026-08-02 反射排查。用户指出对话与代码分析中反复出现的"兜底、混合方案、双轨制、多轨制、双通道、多通道、双形态、三策略"等表述（及同类模式：双写真相、半接通、死分支、恒真/恒假探测、防御姿态、承重探测、回退、静默降级、best-effort）可能暗示代码异味，属技术债。
> **状态**：待执行（独立分支，不与主线混置）
> **核验基准**：`.opencode/skills/code-quality/SKILL.md` 健康诊断十查 + 判定基准（A 职责分离合法保留 / B 穿透应修根因 / 死代码删除 / 双通道收敛单一入口）
> **方法**：证据驱动——逐点禁用验证/实测，禁静态推演；每批 `python -m pytest tests/` 全量零回归。
> **纪律**：不写单一反射关键字作检索信号；以机制理解 + 模式覆盖自主检索。

---

## 一、异味术语与代码位置总清单

> 标注：**【保留】**=承重/分层/设计内（已证据确认）｜**【待核验】**=疑似异味未定案｜**【已记录】**=已有专项任务

### A. 兜底 / fallback 家族（静默回退、默认值降级）

| # | 位置 | 特征 | 状态 |
|---|---|---|---|
| A1 | `compiler/semantic/passes/_expression_visitors.py:303` | resolve_call_return 统一入口外直读 return_type 作最后兜底（功能性双通道） | **已记录 PT-SEM-4** |
| A2 | `llm_executor/_prompt.py:26/41-48/59/84/315` | to_native/__to_prompt__ 多级 fallback 链（异常驱动逐级降级） | 待核验 |
| A3 | `llm_parsing_strategy.py:287-316/356` | DefaultParsingStrategy 兜底 + "safe fallback just in case" | 待核验 |
| A4 | `spec/registry/_inference.py:63/93` | 无显式返回类型 → axiom fallback → `resolve("any")` | 待核验 |
| A5 | `vm/handlers/_shared.py:241` | 同步后备路径兜底字段（CPS 主路径无视） | 待核验 |
| A6 | `vm/handlers/assignment.py:82/106` | dispatch_eager 失败兜底同步路径（"极少触发"） | 待核验 |
| A7 | `vm/handlers/llm_behavior.py:140` | 防御性兜底 handler（"解析器不再生成此节点类型"） | **疑似死代码，优先核验** |
| A8 | `llm_except_frame.py:78/245/267` | 深克隆兜底 / `__restore__` 失败 best-effort 保留当前状态 | 待核验（best-effort 语义） |
| A9 | `vm_executor.py:239` | CPS 求值 vs fallback 双路径 | 待核验 |
| A10 | `objects/kernel/base.py:46` | 内置类型 call 方法 Python 直调兜底 | 待核验 |
| A11 | `kernel/registry.py:363` | make_llm_parse_error 类查找逐级回退 | 待核验 |
| A12 | `engine.py:183/245/248/270/272` | plugin_paths 多优先级来源 + 嗅探兜底 | 设计内（多优先级，非异味） |
| A13 | `binding_analysis_pass.py:513/537/899` | 无名称兜底 / 运行时守卫兜底 / 父作用域查找兜底 | 待核验 |
| A14 | `runtime_context.py:121-122` | 无 UID 引导期 fallback_uid | 设计内（引导期；assert 已强制 uid/name） |
| A15 | `objects/kernel/_helpers.py:23/28` | 节点形状兼容 fallback | 待核验 |
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
| B7 | `vm_executor.py:239` | CPS 主路径 + fallback 双路径（同 A9） | 待核验 |
| B8 | `interpreter.py:17 注释` | 自述"无 fallback_visit，无 assign_to_target" | 信息（确认单路径） |

### C. 静默 except / 静默降级（fail-fast 违反面）

| # | 位置 | 特征 | 状态 |
|---|---|---|---|
| C1 | `module_system/discovery.py:158` | `except ImportError: pass`（协议1探测失败） | 设计内（探测语义） |
| C2 | `module_manager.py:141` | `except AttributeError: pass` | 待核验 |
| C3 | `llm_executor/_scheduler.py:105` | `except Exception: pass` | 待核验 |
| C4 | `objects/kernel/native_module.py:115/121` | `except KeyError/AttributeError: pass`（**原 4.3.4 吞错根因面**） | **待核验（已修 4.3 部分，复核残留）** |
| C5 | `modules/file_impl.py:156` | `except (OSError, ValueError): return False`（**原 5.6：沙箱权限降级"文件不存在"**） | 待核验 |
| C6 | `kernel/config.py:47` | `except OSError: return {}`（**原 5.8：损坏 JSON 静默吞**） | **待核验（区分"不存在=空"与"损坏=报错"）** |
| C7 | `base/support/fuzzy_json.py:29/71/81/108/118` | 5 处 JSONDecodeError/ValueError pass（容错解析） | 待核验（容错 vs 掩盖） |
| C8 | `base/diagnostics/debugger.py:59` | 配置解析异常 pass | 待核验 |
| C9 | `ibci_modules/ibci_idbg/core.py:383/398` | `except Exception: pass` | 待核验 |
| C10 | `extension/auto_discovery.py:73/87/101` | OSError/PermissionError/Exception 静默 | 待核验 |
| C11 | `objects/kernel/base.py:113/140` | `__to_prompt__`/`__outputhint_prompt__` 兜底 | 设计内（协议降级有明确语义） |
| C12 | `llm_except_frame.py:318` | `except Exception: return a is b`（值比较 best-effort） | 设计内（浅比较兜底） |
| C13 | `_prompt.py:137` | StopIteration → value/"" | 待核验 |
| C14 | `kernel/axioms/primitives/sequences.py:178/257/336` | ValueError → 解析失败返回（有明确 retry_hint） | 设计内（解析错误语义） |

### D. 防御性探测 / 双路径判别残留

| # | 位置 | 特征 | 状态 |
|---|---|---|---|
| D1 | 约 30 处 `getattr(x, ..., None) or []` 模式 | 防御性兜底（`core/` 内） | **待核验（逐点判恒真/承重）** |
| D2 | 45 文件含 `hasattr` | 大部分为协议/分层合法反射，需分类复核 | **待核验（按判定基准分类）** |
| D3 | 5 处 to_native/ib_class 鸭子判别保留（B3/B4） | 见 B 分类 | 保留（已证据确认） |

### E. 本次已处置项的复核边界（技术债收尾）

| # | 内容 | 复核点 |
|---|---|---|
| E1 | `unbox()` 边界函数（85 处转换） | 复核恒等回退→unbox 转换的边界语义（str/bool/int 回退、callable 透传、memo 传参站点） |
| E2 | 承重保留站点（descriptor/sentinels memo/loader callable/kernel 分层） | 复核保留理由是否仍成立 |
| E3 | 死代码删除（registry.is_truthy/_cast_*/export_metadata/IntegrityChecker/is_package_dir/create_plugin/create_instance/Diagnostic.node_uid） | 复核零消费方判定是否遗漏动态引用 |
| E4 | 组8 处置（_extract_signature fail-fast、IbNativeFunction.__getattr__ 删除、method_missing 删除） | 复核 fail-fast 是否引入插件兼容回归；__getattr__ 删除是否有隐性消费者 |
| E5 | `_expression:304` 兜底、loader↔check 复制 | 已记录（PT-SEM-4 / REFLECT-ARCH-1 设计决策），不重复修复 |

---

## 二、核验流程（独立分支执行）

1. **分类定案**：对 A/C/D 每项用判定基准定性——A 合法保留（协议/分层/多优先级设计）／B 修复根因／死代码删除／双通道收敛。禁用验证（临时移除后全量测试）确认"死代码/冗余"判定。
2. **优先级**：A7（疑似死代码）→ C4/C5/C6（已知吞错面）→ C3/C9/C10（宽 except）→ C7/C8（容错 vs 掩盖）→ A2/A3/A5/A6（fallback 链）→ D1/D2（防御性探测分类）→ B6（双轨复核）。
3. **每批**：`python -m pytest tests/` 全量零回归 + 全仓残留扫描。
4. **收尾**：定案结果回写本清单（标注 ✅ 已修复／保留），已修复项删除，保留项说明理由；不写独立 ADR。
