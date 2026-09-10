# NEXT_STEPS — 当前最紧要项

> 本文件**只**记录当前最紧要、可立即开工的下一步与强制工作约束；长期规划见
> `tasks_docs/PENDING_TASKS.md`。本文件不承载历史完成记录（git 承载）；任务控制
> 治理见 `tasks_docs/GOVERNANCE.md`。
>
> **书写要求**：更新本文档必须按尾部「书写模式」模板与格式书写，保持一致。

---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. 禁止 compat shim / 兼容层：新设计就是真设计，旧代码要么真合并、要么真删除。
2. 禁止胶水实现：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定。
3. 禁止 tricky 实现：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. 禁止过程式硬编码分发：同一决策只通过协议驱动（`receive()` / vtable），不写 `if 能力标志位`。
5. 质量优先于速度：技术债必须先清；潜伏 bug 不允许过渡修复。
6. 原则优先于行为维持：既有行为违反一般工程/架构原则时，以原则为准，不以"保持已有行为"为主。
7. 可推翻 IBCI 自身设计缺陷：即使设计思路已在文档记录，也可按更普适、实践更合理的方案重建。
8. 破坏性重构授权：符合一般工程经验且经分析优于现有体系时默认已授权自主推进，详记决策。
9. 大范围破坏性重构分支政策：无法确认边界/危害程度的重构 100% 授权在独立隔离分支实验
   （允许任意程度破坏性实验）；**确认零风险（全量 pytest 零回归 + 复核放行，无对外
   契约/架构级风险）后直接合并（ff）到 `unsafe-vibe-dev`；merge 无误后直接删除无用分支**
   （除 `main` 与 `unsafe-vibe-dev` 外不长期保留分支，短期工作分支合并即删）；判定以
   "是否确认零风险"为准，非以改动规模；永远不触碰 `main`。

---

## 🔴 当前状态

> **测试基线（唯一锚点）**：`.venv/bin/python -m pytest tests/`（唯一权威命令；addopts 已含 `-q`，
> 勿显式再加——双 `-q` 会隐藏计数行）；末次全量 **4276 passed / 1 skipped 零回归**（2026-09-10 实跑，
> P9 阶段③ 第九增量[执行核心类型池/node_to_type 反序列化 + 类型表差分 1 例]阶段边界放行门；数字以实跑为准，不冻结）。
> **使用策略（临时，2026-09-10 → 直至 Rust 内核替换结束）**：单任务默认验证 = 受影响子集 + smoke 子集
> （`tests/contracts` + `tests/compiler`，~13s）；全量仅 merge/放行门 / 公理层或语义错误集 / 阶段边界 /
> 开新分支前（单点真理 = `AGENTS.md` §测试；Rust 替换结束且耗时显著降低后重新评估）。分支 =
> `unsafe-vibe-dev`（日常开发主线）= 本地（领先 origin `e5f6fd2d` 12 提交，**不 push**——用户 2026-09-10
> 本 session 明确；2026-09-09 已推送 `11a893a7..123a341f` 13 提交，用户授权）；`main` 永不触碰。

> **🔴 当前 P0 = IBCI 原生数据库（世界模型知识图谱）+ 自指性主线收束 + 测试进程内化**：
> - **执行进度**：**P1 R-A quote/eval ✅**（`meta.quote`/`meta.eval` + `quoted` 一等值类型——单一
>   验证门[良构由构造成立] + 值通道[返回值非文本]）→ **P2 R-B 世界模型 KB ✅**
>   （`knowledge` 就地演化为三元组知识图谱：facts 事实日志[单一权威源] + vocab 治理词表 +
>   8 派生索引 + 27 方法面 + 内建治理门 + 墓碑/版本化；双写根治 = 词关系/展开态/索引
>   全派生；设计/裁定 = `_p2_world_model_kb_design.md` + WORKLOG）→ **P3 磁盘格式 ✅**
>   （`world_model` 模块：KB 内容寻址 artifact + load_kb/save_kb + 三级验证门；**B1 验收达成**
>   load 后活查询 + 增量 100 事实无需重编译；设计/裁定 = `_p3_disk_format_design.md` + WORKLOG）
>   → **P4 R-C 确定性执行模式 ✅**（`--deterministic` 零 LLM 不变量：汇点 guard +
>   RUN_DETERMINISTIC_LLM_CALL + result-json 凭证 {enforced, llm_calls: 0}；**M1 验收
>   达成**；附带 budget location 既有缺陷修复 + KNOWN_LIMITS §二十七；设计/裁定 =
>   `_p4_deterministic_mode_design.md`[已删] + WORKLOG）
>   → **P5 R-D 工件加载 ✅**（`narrow_model` 值类型[不可变冻结 KG 嵌入工件] +
>   `world_model.bind_artifact`/`save_artifact` 窄模型工件面[TransE 纯算术推理
>   score/topk，三级验证门同 load_kb]；**R-D 验收达成** = bind 后 score/topk 可
>   调用且确定性，全程零训练零 LLM；设计/裁定 = `_p5_artifact_loading_design.md`
>   [已删] + WORKLOG）
>   → **P6 向量面 ✅**（knowledge 词嵌入面[set_embedding/embedding/embed_search
>   暴力 cosine 内容信号非判定] + KB artifact v2[vector 节加法演进，v1 向后
>   兼容]；词级嵌入持久化 + 确定性 tie-break；设计/裁定 =
>   `_p6_vector_plane_design.md`[已删] + WORKLOG）
>   → **P7 R-F 投影派生视图 ✅**（`knowledge.to_ibci()` = KB 当前态的确定性
>   IBCI 代码派生视图[非存储层]——全词汇/全事实无 lossy + 确定性逐字节一致 +
>   对拍活 KB 一致；替代 lossy stopgap schema_to_ibci；设计/裁定 =
>   `_p7_projection_design.md`[已删] + WORKLOG）
>   → **P8 测试进程内化 ✅**（消端到端流水线可复现性 4x 冗余 dual-channel——
>   P5/P6/P7 e2e 两 run → 单 run CLI 凭证，确定性归并进 process + P4 M1 代表性
>   流水线可复现性；e2e 子进程开销大部分不可化约[CLI 机制 + 子运行 by design]，
>   主价值 = 消冗余质量而非大幅省时；设计/裁定 = WORKLOG P8 条目）
>   → **P9 Rust 内核 阶段① 地基 ✅**（构建链 + 差分等价 harness——crate
>   ibci-ext[pyo3 0.23] + build_rust_ext.sh[pin CARGO_HOME/TARGET_DIR workspace]
>   + tests/diff_harness[常设安全网：双内核同输入→同输出逐字节等价；14 条语料
>   种子面 + Python 参考确定性验证；Rust 未就绪不冒充]；双内核协议[Python 一等
>   实验内核默认 + Rust 生产快路径 opt-in 无静默回退]；零风险加法式地基，
>   merge unsafe-vibe-dev 删分支；设计/裁定 = WORKLOG P9 阶段① 条目 +
>   `_rust_kernel_survey.md`）
>   → **P9 终点（用户 2026-09-10 裁定，重新定义）**：Rust 部分（阶段②③④）完成
>   后开启**新评估 + 新自主执行模式**，评估**全核心逻辑全量 Rust 化**（编译/语义/
>   执行/调度/并发等核心面）；**保留关键部分 Python 接口**（灵活性 + 供 Python 入口
>   能力，非 100% 无 Python）；**证明绝大部分关键核心逻辑可 Rust 化时全量转向
>   Rust，废弃 Python 双通道/对比**（迁移期安全网退场）。双内核 + 差分 harness =
>   **迁移期临时安全网**（非永久）。设计/裁定 = `_rust_kernel_survey.md` §2.3/§2.6
>   + WORKLOG（P9 终点裁定条目）。
>   → **P9 阶段② 首增量 ✅**（Rust lexer 移植——对齐 Python core normal 模式
>   [StrStream + CoreScanner + IndentProcessor + 行处理]；`ibci_ext.lex` 暴露
>   token 流；差分 harness 加 token 级差分面；**14/14 语料 token 级逐条等价**；
>   修 3 类移植 bug[运算符先消费首字符/INDENT column 消费前记录/EOF dedent
>   column=0]；行为块/意图/三引号/raw/变量引用 = 后续增量；零风险加法式，merge
>   删分支；设计/裁定 = WORKLOG P9 阶段② 首增量条目）
>   → **P9 阶段② 第二增量 ✅**（Rust parser 移植——最小语句/表达式面[Assign /
>   ExprStmt / Constant / Name / BinOp[+] / Call] + AST 规范 dumper[ast_dump.py
>   structure 模式] + `ibci_ext.parse_struct` 暴露 + 差分 harness 加 AST 级差分面；
>   **6/6 片段 AST 级逐字节等价**；渐进移植 + 差分门，非 subset 双通道；零风险
>   加法式，merge 删分支；设计/裁定 = WORKLOG P9 阶段② 第二增量条目）
>   → **P9 阶段② 第三增量 ✅**（Rust parser 完整语句/表达式面——从最小面扩至
>   完整语料面[if/elif 链 / for[target ctx='Store'] / func def[typed args +
>   returns] / return / break / pass + BinOp 全运算符[+ - * / // % ** 递归下降
>   优先级] / UnaryOp / Compare[链] / List / Dict / Attribute / Subscript / Call
>   + INDENT/DEDENT body 解析 + 回退式前瞻 Assign[Name/Subscript target]]；
>   **14/14 语料 AST 级逐字节等价**；渐进移植 + 差分门，非 subset 双通道；零风险
>   加法式，merge 删分支；设计/裁定 = WORKLOG P9 阶段② 第三增量条目）
>   → **P9 阶段② 第四增量 ✅**（Rust parser 位置跟踪对齐——每节点
>   lineno/col_offset/end_lineno/end_col_offset 对齐 Python _loc[start token
>   line/col + end token end_line/end_col]；lexer 合成 token[NEWLINE/EOF/INDENT/
>   DEDENT] end 位置修复 = (0,0)[此前 token 级差分只比 type/value/line/column，
>   漏过 end 位置 bug]；AST dumper 含位置 + 差分 harness 升级[AST 完整形态含位置
>   比对 + token 完整位置比对]；**14/14 语料 AST 完整形态[含位置]逐字节等价 +
>   token 完整位置 14/14 等价**；节点特定规则[IbAssign end=target.end / IbReturn
>   end=RETURN.end / IbUnaryOp end=op.end / IbIf·For·FunctionDef end=DEDENT(0,0)
>   / IbModule end=None]；零风险加法式，merge 删分支；设计/裁定 = WORKLOG P9
>   阶段② 第四增量条目）
>   → **P9 阶段② 第五增量 ✅**（Rust parser 剩余语句/表达式面——While /
>   Try[except/else/finally，IbExceptHandler] / ClassDef[fields=Assign / methods=
>   FunctionDef] / IfExp 三元[body if test else orelse，最低优先级层 parse_ternary→
>   parse_compare，右结合] / Lambda[IbLambdaExpr，typed params + 返回类型，
>   `lambda[(typed params)][: or -> TYPE:] body`]；位置跟踪[IbWhile/IbClassDef=
>   keyword/DEDENT(0,0) / IbTry=TRY token 止 / IbIfExp=body 起/orelse 止 /
>   IbLambda=LAMBDA 起/body 止] + 递归类型断环[Box Arg.annotation/default +
>   Lambda.returns]；**7/7 剩余面 AST 完整形态[含位置]逐字节等价 + 语料面 14/14
>   无回归**；零风险加法式，merge 删分支；设计/裁定 = WORKLOG P9 阶段② 第五增量
>   条目）
>   → **战略微调（2026-09-10）**：语义层（7427 行 + 完整环境依赖）Rust 移植推迟
>   = 全量 Rust 化后续；**直接推进阶段③ 执行核心（主战场）**——执行核心消费
>   Python 前端产出的序列化 artifact（FlatSerializer JSON，含语义层输出），Rust
>   侧反序列化 + 执行（cProfile 实证性能瓶颈，价值最高）
>   → **P9 阶段③ 首增量 ✅**（Rust artifact 反序列化器——nodes 池[UID 引用] →
>   Rust AST[复用 parser Expr/Stmt + dumper] + serde_json 依赖 + 差分 harness 加
>   反序列化器差分面；**14/14 语料反序列化 AST 逐字节等价**[artifact → Rust AST
>   == Python AST]；执行核心输入契约就位；零风险加法式，merge 删分支；设计/裁定
>   = WORKLOG P9 阶段③ 首增量条目）
>   → **P9 阶段③ 第二增量 ✅**（执行核心：Rust 对象模型[IbValue：Int/Float/Str/
>   Bool/None/List/Dict，List/Dict 经 Rc<RefCell> 共享可变] + tree-walking 解释器
>   [Assign/ExprStmt/If/For/While/FunctionDef/Return/Break/Continue/Pass + 表达式
>   全面 + 内建 print/len/range + 方法 append/str] + IBC 数值语义[/ 与 // = floor
>   除，int+float=float] + 环境/作用域链[递归] + `ibci_ext.run_artifact` 暴露 +
>   差分 harness 加数据面差分面；**11/11 非 KB 语料数据面逐条等价**[Rust 执行 ==
>   Python 执行]；**主战场突破**；KB 语料面[宿主服务] = 后续增量；零风险加法式，
>   merge 删分支；设计/裁定 = WORKLOG P9 阶段③ 第二增量条目）
>   → **P9 阶段③ 第三增量 ✅**（执行核心性能基准——常设基准脚本
>   `scripts/bench_rust_kernel.py`[Python run_ibci vs Rust run_artifact，微秒/次，
>   300 次均值]实证 **Rust 执行核心比 Python 快 23–30x**[均值 ≈27x，tree-walking
>   未优化即显著领先]；公平对比[两侧均含 load + execute：Python compile 缓存查找
>   vs Rust JSON 反序列化]；非 KB 语料面 11 条；非测试[性能断言 flaky]；加法式零
>   风险直接提交；设计/裁定 = WORKLOG P9 阶段③ 第三增量条目）
>   → **P9 阶段③ 第四增量 ✅**（执行核心 KB 语料面——host service 桥接[Rust →
>   Python 回调，KB 逻辑留 Python 单点真理，不复制避免双通道]：IbValue::Host
>   [宿主对象引用] + knowledge() 经桥接 create_knowledge + KB 方法委托 Python
>   对象[register_world/add_fact/worlds/exists/lookup_pair/contradicts] + 参数/
>   结果双向转换[Rust IbValue ↔ Python 对象，嵌套结构正确] + `ibci_ext.
>   run_artifact(artifact_json, bridge)` 暴露 + 桥接助手 bridge.py[经 registry
>   创建 knowledge]；**全语料 14/14 数据面逐条等价**[11 非 KB + 3 KB]；零风险
>   加法式，merge 删分支；设计/裁定 = WORKLOG P9 阶段③ 第四增量条目）
>   → **P9 阶段③ 第五增量 ✅**（执行核心更宽 IBCI 语料 + 布尔逻辑解析——语料 14
>   → 20[+control_while/expr_ternary/expr_bool/function_nested/string_methods/
>   list_more]；Rust parser 加布尔逻辑层级[parse_or/parse_and/parse_not，优先级
>   ternary<or<and<not<compare 对齐 Python，BoolOp 左结合/not 右结合]+ deserializer
>   加 IbBoolOp + interpreter 加 and/or 短路 + not；**全语料 20/20 四级差分逐条
>   等价**[token/AST/反序列化/数据面]；零风险加法式，merge 删分支；设计/裁定 =
>   WORKLOG P9 阶段③ 第五增量条目）
>   → **P9 阶段③ 第六增量 ✅**（执行核心闭包完整语义——Rc<RefCell<Environment>>
>   重构[环境共享可变，作用域链 + 闭包捕获经 Rc 共享]+ Function 捕获 enclosing
>   [定义处环境，嵌套函数 call_env parent = enclosing 访问 outer 局部/顶层 =
>   global 递归+读全局]+ global_rc 短借用走链[不跨递归持借用，避免 RefCell
>   panic]；语料 +closure_capture/closure_top_global；**22/22 四级差分逐条等价**
>   [token/AST/反序列化/数据面]；IBCI 闭包边界对齐[mut captured 全局是 IBCI 限制]；
>   零风险加法式，merge 删分支；设计/裁定 = WORKLOG P9 阶段③ 第六增量条目）
>   → **P9 阶段③ 第七增量 ✅**（执行核心更宽 IBCI 面——链式比较[a < b < c 左到右
>   全链]+ list 方法[index/pop]+ dict 方法[get 带默认/keys/values]+ str 方法
>   [split/find]+ 嵌套容器[subscript on subscript 经递归]；语料 +list_methods/
>   dict_methods/nested_container/str_methods/chained_cmp；**27/27 四级差分逐条
>   等价**[token/AST/反序列化/数据面]；while-else 是 IBCI 限制[编译失败，非执行核心
>   缺陷]；零风险加法式，merge 删分支；设计/裁定 = WORKLOG P9 阶段③ 第七增量条目）
>   → **P9 阶段③ 第八增量 ✅**（执行核心符号池/侧表反序列化——完整 artifact
>   消费：反序列化器从 nodes 池[AST] 扩展至 symbols 池 + node_to_symbol 侧表
>   [语义层输出，变量/函数/方法符号解析]；Symbol 结构[name/kind/type_uid] +
>   `ibci_ext.symbol_table` 暴露[node → symbol 名解析规范表示，按 node_uid 排序]+
>   差分 harness 加符号表差分面；**27/27 全语料符号表差分等价**[Rust symbol_table
>   == Python node_to_symbol 解析]；本增量不用于执行[tree-walking 用简单变量绑定，
>   符号表用于后续类型检查/错误报告/CPS 分发]；零风险加法式，merge 删分支；设计/
>   裁定 = WORKLOG P9 阶段③ 第八增量条目）
>   → **P9 阶段③ 第九增量 ✅**（执行核心类型池/node_to_type 反序列化——完整
>   artifact 消费续：反序列化器从 symbols 池 + node_to_symbol 侧表扩展至 types 池
>   + node_to_type 侧表[语义层类型输出，节点类型解析]；`ibci_ext.type_table` 暴露
>   [node → type 名解析规范表示，按 node_uid 排序]+ 差分 harness 加类型表差分面；
>   **27/27 全语料类型表差分等价**[Rust type_table == Python node_to_type 解析]；
>   本增量不用于执行[tree-walking 用简单变量绑定，类型表用于后续类型检查/错误报
>   告/CPS 分发]；资产池本增量不含[语料面 assets 池为空]；零风险加法式，merge 删
>   分支；设计/裁定 = WORKLOG P9 阶段③ 第九增量条目）
>   → **当前批次 = P9 阶段③ 续（执行核心：CPS 优化[43 节点 enum 分发，在 27x 基础
>   上进一步提升] + 资产池反序列化 + 更宽 IBCI 语料[quoted 值/行为表达式]；隔离
>   分支续）**。
> - **是什么**：把 IBCI 数据层（D 纸带）从现状（trial 侧 lossy 静态代码投影）演进为**一等
>   世界模型知识图谱**——单一权威源 = append-only 事实日志 `(world,s,r,o)`+source/status，
>   融合**图/三元组平面**（治理词表 + 8 倒排索引 + 矛盾/传递/展开，D1 零 LLM）与**向量平面**
>   （内容信号，非判定）；**quote/eval**（数据/行为二元）地基 + 确定性执行模式 + 推理时窄模型
>   工件加载。**"不能永远用 IBCI 代码/JSON 承载数据"**——IBCI 值化 KB 取代二者（值化存储，非服务）。
> - **需求权威源**：试用方 v2（`/home/dsh/proj/ibci-trial/docs/REQ_IBCI_WORLD_MODEL_INTEGRATION.md`
>   R-A~R-F + M1-M4）+ 数据分析（`DATA_STRUCTURE_DATABASE_ANALYSIS.md`）；**设计单点真理 =
>   `tasks_docs/_world_model_db_design.md`**（本轮定稿，含调研结论/决策点/风险/P0-P9 执行清单）。
> - **设计裁定（用户 2026-09-10 授权推进）**：① 演化现有 `knowledge` 为一等 KB（单点真理，不另立
>   平行类型）② R-A quote/eval 先设计+POC（触及公理层 → 全量 pytest 评估）③ 向量面 = 纯 IBCI 值 +
>   `ImmutableArtifact` 工件（暴力 cosine 起步，格式预留 ANN）④ 磁盘格式 = IBCI 内容寻址 artifact
>   （JSON 降传输格式，IBCI 代码降派生视图 `to_ibci()`）。
> - **工作节奏（三轴收束，不新设竞争主线）**：R-A 并入 selfref 弧线（C3/D1）/ R-B 演化 knowledge /
>   R-C 确定性模式横切；**Rust 内核 = 独立隔离分支 `rust-kernel`（设计 + 构建均可：pin
>   `CARGO_HOME` 到 workspace + 允许网络 → 免审批），harness 语料 = 世界模型里程碑**；
>   **e2e 进程内化 = 早期使能项**（降全量门成本）。
> - **硬约束**：9 项 VM 设计不变量 + 工作模式定论九条 + D1（判定零 LLM）+ 每批验证（单任务=受影响
>   子集+smoke；全量仅 merge 门/公理层或语义错误集/阶段边界/开新分支前）+ 详尽落账（WORKLOG）。
>
> **里程碑记录（过程/细节 = git 历史 + WORKLOG，不在此登记）**：round3 ✅ / meta 层 MVP ✅ /
> VISION-6 P1-P7 ✅（P7 进程级隔离 subprocess+JSON 协议）/ **Round4 MEM+REC ✅**（memory 一等值
> 类型·ai.recall/recall_stats 向量原语+doc 缓存·REC-6+MRL·meta.compile 行为值）/ **Round5 整合 +
> C1/C2 ✅**（selfref 地基·verify 三关门·吸收试用者 REC-6/TYPE-1）/ **Rust 内核替换调研 ✅**
> （VM 执行层定性·pyo3 四阶段·双内核纪律·全量 pytest 临时策略）——收束 `unsafe-vibe-dev`。

## 下一步候选（当前主干按序；支线仅在不打断主线时介入）

**排布总则**：健康度优先（代码/架构）→ 功能稳健 → 对外能力 → 远期演进；同一时刻只推
一个 P0。**试用方需求恒高优先**（来自真实试用者的功能性需求优先于自研/卫生项）。

1. **主线 = IBCI 原生数据库（世界模型知识图谱）+ 自指性收束 + 测试进程内化**（见上"当前
   状态"；**设计单点真理 = `_world_model_db_design.md`**；自主推进，无人值守偏好 + 总体规划
   可灵活微调[用户 2026-09-10 裁定]；执行序列
   P1 R-A quote/eval ✅ → P2 R-B KB ✅ → P3 磁盘格式 ✅ → P4 R-C 确定性模式 ✅
   → P5 R-D 工件加载 ✅ → P6 向量面 ✅ → P7 R-F 投影派生视图 ✅ → P8 测试进程内化 ✅
   → **P9 Rust 内核 阶段① 地基 ✅ → 阶段② 首增量 Rust lexer ✅
   → 阶段② 第二增量 Rust parser 最小面 ✅ → 阶段② 第三增量 Rust parser 完整面 ✅
   → 阶段② 第四增量 位置跟踪对齐 ✅ → 阶段② 第五增量 剩余语句/表达式面 ✅
   → 阶段③ 首增量 执行核心反序列化器 ✅（语义层 Rust 移植推迟 = 全量 Rust 化
   后续；执行核心消费 Python artifact）→ 阶段③ 第二增量 执行核心对象模型 +
   解释器 + 数据面 11/11 等价 ✅**（**主战场突破**）
   → 阶段③ 第三增量 执行核心性能基准 23–30x ✅
   → 阶段③ 第四增量 执行核心 KB 语料面 host service 桥接 全语料 14/14 ✅
   → 阶段③ 第五增量 更宽语料 20 条 + 布尔逻辑解析 四级 20/20 ✅
   → 阶段③ 第六增量 闭包完整语义 Rc<RefCell> + enclosing 22/22 四级 ✅
   → 阶段③ 第七增量 更宽 IBCI 面[链式比较/方法/嵌套容器] 27/27 四级 ✅
   → 阶段③ 第八增量 符号池/侧表反序列化 完整 artifact 27/27 符号表 ✅
   → 阶段③ 第九增量 类型池/node_to_type 反序列化 27/27 类型表 ✅
   → 阶段③ 续（CPS 优化 + 资产池 + quoted 值/行为表达式）[当前]
   → 阶段④ 并发解除
   → P9 Rust（设计 + 构建；差分 harness 语料已含 quote/eval + KB 判别面；
   harness 语料纪律 = 自包含脚本，磁盘面不入库语料——P9 如需文件语料再显式
   扩 temp root）；
   每步受影响子集+smoke 零回归 + commit + 同步 NEXT_STEPS/WORKLOG）。
2. **selfref 弧线（C3-C5, Phase D）与主线收敛**：R-A quote/eval 地基已落（C3 起 selfref.verify
   验证门可改走 `meta.quote` 单点化——C3 批评估）；R-B KB 与 memory/meta.compile 机制同构
   （已落）。C3 自修改安全 / D1 SR-4 行为值直接执行 随主线一并推进。
3. **Rust 内核替换 = 独立隔离分支 `rust-kernel`（设计 + 构建均可：pin `CARGO_HOME` 到 workspace +
   允许网络，免审批）**：`_rust_kernel_survey.md` 四阶段（① 构建链+差分 harness → ② 前端 →
   ③ 执行核心 → ④ 并发解除）；harness 语料 = 世界模型里程碑；确认零风险后 merge unsafe-vibe-dev 并
   删分支。
4. **支线 · e2e 进程内化**（套件 44% 子进程开销，`conftest run_ibci` 进程内助手）：升格为
   早期使能项（降全量门成本，服务主线高频验证）。
5. **支线 · 周期质量维护**（PT-AUDIT-1/3 + Tier B/C）+ **恶意边界未测项**（`trials/INDEX.md`
   mock 层）+ **远程 CI 启用（暂不启动，待用户授权）**。
6. **远期演进（试用稳定后）**：VISION-4 类型理论加固 / VISION-5 函数式地基 / VISION-1 二层 IR
   （见 `PENDING_TASKS.md` §八）；PT-SEALED-1 保持封存。

**长期登记（状态单点真理 = `PENDING_TASKS.md`）**：PT-DECIDE-2（供应商思考禁用，已解封）/
PT-FEAT-17 N3 度量（shelved）/ PT-FEAT-6/12（远期）/ bind 默认值语法（独立立项）。
（最近完成与过程记录见 git log；长期裁定见 `tasks_docs/WORKLOG.md`。）

---

## 工作规则

- 同一时刻只主推一个 P0 阶段。
- 工作模式定论优先；改动公理层或语义错误集的任务需全量 pytest 评估破坏面。
- 重大架构决策直接写入 `docs/architecture/` 对应章节，不使用独立 ADR 文件。
- 测试基线以实跑为准，不冻结数字（唯一命令 `python -m pytest tests/`，见 AGENTS.md）。

---

## 附、书写模式（本文档专用模板，书写必须参照）

> 本节是本文档书写的**唯一权威模板**（模板归属 = 文档自身；`GOVERNANCE.md`
> §三 仅做索引）。更新本文档一律按下列结构与格式书写。

### 1. 文档结构

```
# NEXT_STEPS — 当前最紧要项
定位段（只记录当前最紧要、可立即开工的下一步与强制约束；不承载历史完成记录）
⛔ 工作模式定论（强制，凌驾于本文件一切任务之上；9 条硬约束）
🔴 当前状态（1 段：当前主线/任务 + 状态；无进行中主线时明确写出）
**下一步候选**（等待用户指示的候选项，按序编号）
工作规则（持续推进的硬规则）
（最近完成与过程记录由 git 承载，不在本文件登记）
```

### 2. 主线状态格式（有进行中主线时）

| 列 | 内容 |
|----|------|
| 阶段 | 阶段代号 + 一句话主题 |
| 状态 | 🔄 进行中 / ⏳ 待用户 / ❌ 阻塞（**不登记已完成阶段**——完成即从本文件移除） |
| 内容 | 本阶段正在做什么（2-4 项要点） |
| 验证 | 放行门（全量 pytest 实跑 + 复核，不冻结数字） |

### 3. 维护规则

- 主线变更时更新"当前状态"与"下一步候选"；**阶段完成即移除**（不保留完成登记）。
- **工作模式定论为最高约束**：修改其中条目属用户裁定级变更，须由用户拍板，不自主改写。
- 待用户确认项只在此标注；不建独立章节。
- 不出现日期戳、历史叙述、测试数字（基线以实跑为准）；引用其它任务控制文档用相对路径指针，不复制正文。