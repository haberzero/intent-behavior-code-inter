# D1 用例矩阵 — 全语法遍历（真实 LLM）

> 来源：docs/SYNTAX_REFERENCE.md + docs/syntax/01-15 + docs/KNOWN_LIMITS.md（已全读）。
> 每个特性一个用例，真实 LLM 跑一遍；死循环保护由 harness 强制执行。
> 命名：`cases/D1-<章>-<特性>-<编号>.ibci`。执行状态在 REGISTER.md 统一汇总。

## 1. 类型系统（01_types）
- D1-01-001 基础类型 + 字面量 + type() 内省
- D1-01-002 泛型容器 list[int]/dict[str,int]
- D1-01-003 Optional[T] or_else/unwrap/is_some
- D1-01-004 类型转换 (str)/(float)/(bool)/(any) + cast_to
- D1-01-005 None 语义 + (str)None
- D1-01-006 any 逃生阀 + 运行时校验 + LLM 初始化 any

## 2. 变量声明（02_variables）
- D1-02-001 auto 推断锁定 + 裸赋值 auto 语义
- D1-02-002 元组解包 + 多重赋值交换
- D1-02-003 global 写访问
- D1-02-004 nonlocal 写回 + 只读自动捕获
- D1-02-005 any 显式动态 + 异类型重赋
- D1-02-006 LLM 初始化（含 A2 内建遮蔽 int sum = @~...~）

## 3. 运算符（03_operators）
- D1-03-001 算术含 int/int 地板除 / 浮点除 / 幂 / 位运算 / 移位
- D1-03-002 字符串/列表拼接与重复
- D1-03-003 比较 / 逻辑 / 成员 in / 身份 is
- D1-03-004 三元表达式 ?: 与 Python 风格

## 4. 控制流（04_control_flow）
- D1-04-001 if/elif/else + for range + break/continue
- D1-04-002 switch/case（+default）
- D1-04-003 try/except/raise/finally + 自定义异常 + 类型窄化
- D1-04-004 pass / void / None 返回

## 5. 函数（05_functions）
- D1-05-001 func 声明 + auto 返回推断 + void/None 区别
- D1-05-002 默认值/具名调用/*args/**kwargs/splat
- D1-05-003 递归（深递归到环境限制边界）
- D1-05-004 嵌套函数 + 闭包 + fn 引用
- D1-05-005 fn[(...)->(...)] 高阶签名 + callable 内省 type(f)/__return_type__
- D1-05-006 lambda -> T / -> auto（含行为体 -> auto=str 强制）
- D1-05-007 snapshot 冻结意图（定义时）
- D1-05-008 yield 惰性生成器（含 LLM 挂起组合）
- D1-05-009 yield from 委托 + next() 推进

## 6. OOP（06_oop）
- D1-06-001 类定义/构造/字段默认值/方法
- D1-06-002 继承 + 覆盖 + super()
- D1-06-003 Enum + switch + LLM 输出枚举
- D1-06-004 协议 __call__/__iter__/__to_prompt__/__from_prompt__/__outputhint_prompt__
- D1-06-005 __snapshot__/__restore__ 自定义快照

## 7. 行为表达式（07_behavior_expressions）
- D1-07-001 即时 @~ str/int/float/bool/list + $插值
- D1-07-002 类型约束输出格式（-> int/bool/list 解析）
- D1-07-003 行为驱动 if/for 布尔上下文
- D1-07-004 lambda/snapshot 延迟执行（A1 意图路径重验）
- D1-07-005 ai.run_batch 批量并发（A5 观测重验）
- D1-07-006 命名模型路由 @NAME~（未注册报错）
- D1-07-007 长提示/复杂 __to_prompt__（C1）
- D1-07-008 行为体 -> tuple[int,str] / 泛型返回解析

## 8. LLM 函数（08_llm_functions）
- D1-08-001 llm...llmend 定义/调用/__sys__/__user__/$插值
- D1-08-002 -> int 返回解析 + __llmretry__ 重试块
- D1-08-003 -> auto/str/自定义类型

## 9. 意图系统（09_intent_system）
- D1-09-001 @ 一次性 smear（A1 赋值路径重验）
- D1-09-002 @! 排他 override（A1）
- D1-09-003 @+ 持久 / @- 移除 / @- 弹栈
- D1-09-004 intent_context 实例 push/pop/use
- D1-09-005 意图注入对真实模型效果实证

## 10. 健壮性（10_robustness）
- D1-10-001 llmexcept + retry 收敛
- D1-10-002 llmretry 语法糖
- D1-10-003 重试耗尽 LLMRetryExhaustedError + try/except
- D1-10-004 快照隔离：retry body 修变量编译期拦截
- D1-10-005 无保护裸 LLM 解析失败 LLMParseError

## 11. 模块（11_modules）
- D1-11-001 import 位置约束 / 命名导入 / 模块导出
- D1-11-002 ai 模块 API（set_config/get_retry/probe/has_api_key/run_batch/current_call_info）
- D1-11-003 isys 路径查询
- D1-11-004 idbg vars/current_llm/current_result/show_*（A4 重验：dispatch 赋值后立即可观测）
- D1-11-005 ihost 隔离（B1 补记）
- D1-11-006 file 模块读写/沙箱（B3 组合）
- D1-11-007 json 模块 parse/stringify/merge/keys/nested
- D1-11-008 宿主绑定 bind（import python ...: bind，多文件）

## 12. 内建（12_builtins）
- D1-12-001 类型转换内建 int()/str()/float()/bool()
- D1-12-002 序列辅助 enumerate/zip/sorted/reversed/sum/all/min/max/len/range
- D1-12-003 str/list/dict/tuple 方法
- D1-12-004 内建遮蔽（int len = 5 等，A2 相关）

## 13. MOCK（13_mock_testing）
- D1-13-001 MOCK 指令真实模式不生效/真实调用（MOCK 字符串被当真提示词？）
- D1-13-002 set_mock_mode + MOCK:INT/STR 校验

## 14. 并发（14_concurrency）
- D1-14-001 chan stream/message/pubsub + subscriber
- D1-14-002 send_nowait/recv_nowait
- D1-14-003 slot set/get/update CAS
- D1-14-004 thread join/thread_result/expect/is_done/cancel
- D1-14-005 await thread[T]/await chan（C4 并发扩展）
- D1-14-006 线程体 + LLM 组合

## 15. 诊断（15_diagnostics）
- D1-15-001 已知诊断码触发路径抽查（编译期错误信息 + catalog 说明）
