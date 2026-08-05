# 完整复核审查工作清单

> 状态：**R1 ✅ / R2 ✅ / R3 ✅ 已完成；R4-R5 待做**（2026-08-05）
> 用途：会话 1-15 累计改动的**完整独立复核审查**清单。R 系列为审查动作；D 系列为
> docs/ 技术手册未同步项（随 R5 收敛）。
> R1/R2/R3 详细处置表已归档（git 历史 + WORKLOG 会话 13-16），本文件只保留待办 + 完成摘要。

---

## 〇、审查动作（R 系列——当前待做）

| # | 内容 | 说明 | 状态 |
|---|------|------|------|
| **R1** | 正式 code-review 复核 | 三阶段主线 + 收尾 L1-L8 独立复核（general agent） | ✅ 完成（会话 13） |
| **R2** | code-quality 健康诊断十查 | 全仓健康审计（残留/双通道/双写真相/fail-fast/封装） | ✅ 完成（会话 14-15） |
| **R3** | code-odor 全面异味扫描 | 特征扫描（嵌套分支/能力探测/兜底字样/反射变体） | ✅ 完成（会话 16） |
| **R4** | 覆盖率核对 | 新增测试是否覆盖全部新行为（subscriber 生命周期/class_ref/泛型特化分支/瞬态协议/构造入口） | ⬜ **待做（下一阶段）** |
| **R5** | doc-governance 审计 | docs/ 治理流程（配合 §三 D 系列文档收敛） | ⬜ 待做 |

> 约束：subagent **仅可用 general agent**；每批全量 pytest 零回归；新缺陷按"不删也不修=不可接受"
> 两档处置（根本修复或彻底删除）；commit 留痕（仅本地，禁 push）。

---

## 〇b、R1/R2/R3 完成摘要（详细处置表已归档）

- **R1（会话 13）**：三阶段主线 + 收尾 L1-L8 独立复核，整体正确无高严重缺陷；新增缺陷
  A1/C1/B1-B6/D1-D6 全部处置（D 系列经用户质询重分类修正）。范围 `e217b8b^..80b463e`。
- **R2（会话 14-15）**：健康诊断十查发现约 50 项；经四 subagent 二次复核（架构层面 +
  IBCI 设计思路），30 项彻底修复/删除（批次 A-E），12 项确认真设计决策保留+文档化。
  含 IbSlot.update 方案 A 接通 CAS RMW、Task→Thread 语言面改名（用户授权）等。
- **R3（会话 16）**：code-odor 全面异味扫描。4 个 general agent 独立扫描
  （Zone A compiler+kernel / B interpreter+vm / C objects+shared+base / D ibci_modules+sdk）
  + 主会话实证核验。26 项疑似真缺陷中，约 23 项定案处置（4 批）：
  - **批次 A 死代码/不可达清除**：lexer 无作用 try、axiom 重复 return、解析链死 fallback、
    snapshot 恒假 scheduler 探测、idbg 悬空 `is_in_fallback`（潜伏 AttributeError）、
    check.py 死常量、engine 静默 axiom 注册、删除不可达 `vm_handle_IbBehaviorInstance`。
  - **批次 B 恒真守卫移除**：registry hasattr 4 处、axiom get_diff_hint、method return_type、
    llm 帧 get_active_intent_ibobj、interpreter 防御分支、capture_mode getattr、spec params、
    native_module 白名单 hasattr、service runtime_context 直访、parallel 开关简化。
    另删除数据源缺失的 hydration 参数计数死检查（水化 spec 不携带签名）。
  - **批次 C except 窄化/fail-fast**：module_manager try 仅包 getattr、事件总线窄化
    CommClosedError、iruntime 去静默 try、ibci_net 9 处收窄 RequestException、
    type_def 解析检查点窄化、scheduler lexer 诊断窄化、coordinator 去死兜底。
  - **批次 D 真缺陷重构**：assignment 复杂目标不再 dispatch（消除双通道/二次 LLM 调用/
    绕过 llmexcept）、behavior 序列化 round-trip 修复（captured_intents 存 intent_context
    uid 而非 list + 补 capture_mode/params_uids + 二次序列化不再 TypeError）。
  - **残留清理**：移除 2 处未用导入。
  - **保留+文档化**：axiom 家族分裂（未重构）、LAZY→any/分层 any permissive 语义、
    deep_clone `type() is` 精确判别、media 封存零改动、llm_except best-effort 协议兜底、
    ibci_ai 宽 except（待决策）、closure 序列化限制（与 fn_callable 一致）等。
- **验证**：全量 pytest = 1506 passed / 6 skipped 零回归（以实跑为准，每批均验证）。
- commit 序列：f5d3f94/cb2edbd/c73914d/a1ffbbe/bffe195（仅本地，未 push）。

---

## 三、docs/ 技术手册未同步（D 系列——随 R5 收敛）

| # | 内容 | 影响文档 |
|---|------|---------|
| D1 | `signal` 关键字/类型移除 | `docs/subsystems` 通信/并发章节、语法文档、`KNOWN_LIMITS.md` |
| D2 | pubsub 语言面打通 + `subscriber` 新类型 | 通信/并发文档、类型参考 |
| D3 | 通信 Signal 移除裁定（零消费者空壳 + 撞名） | 相关设计记录 |
| D4 | `send_nowait` 语言面补齐 + 语义变化（无订阅者 False） | 通信文档 |
| D5 | 线程对象模型细化（thread 槽位化/thread_result IbValue/瞬态序列化协议） | 线程/值对象文档 |

---

## 四、thread 架构/类型系统隐患调查（T 系列——已全部落地）

> 调查结论浓缩（2026-08-04）：thread 特有突兀分支 + 构造机制三轨，根因 = 统一泛型模型
> 半落地。落地：成员特化协议化 ✅ / 瞬态序列化协议化 ✅ / 公理 any 机制化 ✅ /
> `_create_blank` 统一构造入口 ✅。完整决策见 WORKLOG 会话 9/10/12。
