# M1 实施追踪 — run_result 值类型 + 执行路径统一（meta 层 MVP 批次 M1）

> 临时实施文档（`code-workflow` Phase 3 多修改单元追踪；M1 交付后删除，最终内容按治理
> 收敛入 `docs/`）。设计权威源 = `_meta_layer_design.md` §八.4 M1；本文件记录 **M1 落地
> 阶段的具体设计细化**（§八 未定的实现取舍）+ 修改单元清单 + 变化前后。

## 一、M1 设计细化（§八 未定的实现取舍）

> §八 给出字段面（exit_status: str / stdout: str / exception: any[None 或结构化 dict
> {code, message, source{file,line,column,snippet}}]）+ 批次边界；本节细化**如何落地**
> 的具体取舍（均机制同构既有先例，非新执行模型）。

1. **run_result 类型身份 = 内核原生不可变值类型**（CLASS kind，parent Object，PRELUDE
   可见——同 knowledge/environment 先例；命名与 thread_result 区分[不同概念不同名，
   非泛型]）。`kind=CLASS`（用户可 `run_result r = ...` 声明 + 有方法面），
   `_axiom_name` 缺省 = name（无特化重定向需求）。
2. **字段访问面 = 字段（attribute，非方法/非下标）**（record 固定字段）：
   `r.exit_status`（str）/ `r.stdout`（str）/ `r.exception`（any：None 或结构化 dict
   装箱 IbDict）——无括号 attribute 访问。裁定依据：① 设计 §8.3 明言"**字段面**"
   （字段非方法）；② IBCI record 字段先例 = `Exception.message`（`MemberSpec
   kind="field"`，经 `_dispatch_getattr` 实例字段优先命中）；③ 下标 = map 语义
   （run_result 非 map），方法 `r.exit_status()` 会误导（绑定方法须括号）——字段
   最贴合 record 语义。三字段装箱值存 `obj.fields`，原生结构存 `payload`
   （to_native/序列化消费）。现有判别测试 `r["exit_status"]`（dict 下标）→
   精化为 `r.exit_status`（字段）——消费方仅本轮判别测试，破坏性精化授权。
3. **值语义 = 不可变**（无修改方法面；同 vector——deep_clone 走不可变引用复用分支
   [deep_clone 不可变原语列表 + "run_result"]；`__hash__ = None`[不作 dict 键]，
   `__eq__` 按三字段值相等）。payload = 原生值容器
   `{"exit_status": str, "stdout": str, "exception": native-dict-or-None}`（异常
   结构化字段全为原生 str——序列化直存，exception() 访问时经 box 装箱 IbDict）。
4. **异常捕获面结构化 = 与 CLI --result-json 同一权威源**（统一设计语言，防双写
   真相）：抽共享 helper `core/runtime/exception_record.py`（build_exception_record /
   build_source_dict / _read_source_line），CLI main.py 的 `_extract_compile_error` /
   `_extract_runtime_error` / `_source_dict` / `_read_source_line` 委托之；host 层
   run_file/run_code 捕获子异常时同 helper 构建 {code,message,source}。子异常可能为
   CompilerError[.diagnostics] / IBCBaseException[.error_code/.location] /
   ThrownException / 裸异常 / collect 超时[无 __cause__]——helper 分支覆盖。
5. **执行路径统一 = 单一 spawn 核心两源形式**（§八 M1）：`request_spawn_isolated`
   增 `code: Optional[str] = None` 源形式参数——恰好一（entry_path XOR code，fail-fast）；
   文件形式 = 既有 `_validate_and_derive_isolated` + `sub_engine.run(abs_path)`
   [R3-⑥ 行为不变]；字符串形式 = sub project_root 派生自父 project_root
   [合成 entry 锚定 __string_exec__，隔离反转校验平凡成立[锚定即父内]] +
   `sub_engine.run_string(code)`。两源共享 E1 LLM 继承快照 / 防卡死 collect_timeout /
   输出捕获 output_callback / 唤醒回调表——单一 spawn 核心，仅子线程体按源形式分派
   （run / run_string）。
6. **host 层 run_file 精化 + run_code 落地**：run_file 返回值 dict → run_result
   [IbRunResult，经 box 透传]；新增 run_code(code, policy) → run_result（run_file
   镜像：字符串源 spawn + collect + 结果作值）。防卡死/错误作值/输出捕获语义与
   run_file 一致（同一 spawn 核心）。
7. **诊断码面**：预期零新码（run_result 无新错误面——字段为既有 str/any；子运行
   失败经 exception 值面传递既有码；超时 = 既有 collect_timeout 语义）。若实施中确
   需新码按纯增面纪律。

## 二、修改单元清单

- [x] **U1 值类型 run_result（新文件）**
  - `core/kernel/axioms/primitives/run_result.py`：RunResultAxiom（name + method_specs
    [exit_status->str / stdout->str / exception->any] + is_compatible）
  - `core/runtime/objects/primitives/run_result.py`：IbRunResult（register_ib_type +
    payload + 三方法访问器 + to_native + __eq__/__hash__=None + cast_to + __to_prompt__
    + __repr__ + serialize_for_debug）
- [x] **U2 值类型注册链（既有文件增补）**
  - `core/kernel/axioms/primitives/registry.py`：import + register RunResultAxiom
  - `core/kernel/spec/specs.py`：RUN_RESULT_SPEC（CLASS kind / parent Object / PRELUDE）
  - `core/kernel/spec/registry/_runtime.py`：import + register RUN_RESULT_SPEC
  - `core/runtime/objects/primitives/__init__.py`：import + __all__ IbRunResult
  - `core/runtime/objects/deep_clone.py`：不可变原语列表 + "run_result"
  - `core/runtime/serialization/runtime_serializer.py`：_collect_run_result + hydration
- [x] **U3 异常记录共享 helper（新文件 + CLI 接入）**
  - `core/runtime/exception_record.py`：_read_source_line / build_source_dict /
    build_exception_record
  - `main.py`：_source_dict / _extract_runtime_error / _read_source_line 委托共享
    helper（_extract_compile_error 经 build_exception_record 同形态）
- [x] **U4 执行路径统一 + host（既有文件）**
  - `core/engine.py`：request_spawn_isolated 增 code 源形式（单一 spawn 核心两源）
  - `core/runtime/host/service.py`：run_file dict→run_result + 异常结构化；新 run_code
  - `core/runtime/interfaces.py`：IKernelOrchestrator.request_spawn_isolated 签名 +
    IHostService.run_file 返回类型 + run_code
- [x] **U5 ihost 模块 + TypeDef**
  - `ibci_modules/ibci_ihost/core.py`：run_file 返回 run_result + 新 run_code
  - `core/runtime/bootstrap/builtin_modules.py`：_SPEC_IHOST run_file return
    dict→run_result + 新 run_code member
- [x] **U6 判别测试**
  - `tests/runtime/test_run_result_type.py`（值类型注册：字段访问/值相等/序列化往返/
    to_native/deep_clone）
  - 更新 `tests/e2e/test_ihost_run_file.py`（run_file → run_result；字段方法访问）
  - `tests/e2e/test_ihost_run_code.py`（run_code：正常/异常结构化[code+source 定位]/
    超时/E1 继承/沙箱边界[字符串代码 fs 限 project_root]）
- [x] **U7 文档**
  - `docs/syntax/11_modules.md` §11.6：run_file 返回类型精化 + run_code + 异常结构化面
    （字段访问示例）
  - `docs/KNOWN_LIMITS.md` §二十六：威胁模型[非对抗性·进程内子环境·无进程级隔离] +
    性能[每调用一次子引擎构造·候选验证充分]边界
  - **不加入中央类型清单**（vector/knowledge 先例——值类型经其特性文档[此处 =
    11_modules §11.6 ihost 节]文档化，非 01_types/12_builtins 中央表）

## 三、验证

- 全量 `.venv/bin/python -m pytest tests/` 零回归（基线 3867 passed / 1 skipped）。
- 残留扫描：无裸 dict 消费 run_file 返回值（全仓 grep `run_file` / `run_code` 消费点
  同步精化）。
- 交付自查：code-quality §九 + self-grill 未决断项归零。
