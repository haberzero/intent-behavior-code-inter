# 临时交接：exp/protocol-kernel 恢复与继续

> 用途：供新 session 恢复 `exp/protocol-kernel` 无人值守任务。
> 背景：上一智能体在推进 IBCI 内核协议化/函数统一时，因模型上下文超限中断。

---

## 当前代码现状

- 分支：`exp/protocol-kernel`
- HEAD：`306ae2ed refactor: eliminate IbLLMFunction as a distinct runtime class`
- 相对 `unsafe-vibe-dev`：领先 39 个 commit
- 工作区有 1 个未提交修改：

```text
M core/runtime/objects/kernel/base.py
```

未提交 diff：

```diff
             if spec_reg and self.ib_class.spec:
+                if not spec_reg.satisfies_protocol(self.ib_class.spec, "from_prompt"):
+                    return (False, f"无法将 '{raw_response}' 解析为 {self.ib_class.name} 类型")
                 cap = spec_reg.get_from_prompt_cap(self.ib_class.spec)
                 if cap:
                     return cap.from_prompt(raw_response, self.ib_class.spec)
```

这是上一智能体在最后一次 commit 后、崩溃前刚加入的改动，属于“协议注册表替换硬编码能力”清理链，应保留并提交。

---

## 中断原因

- 时间：2026-08-16 01:29:49
- 原因：模型请求超过上下文长度上限（`CONTEXT_WINDOW_EXCEEDED`）
- 最后动作：修改 `base.py` 的 `__from_prompt__` 后尚未运行测试/提交，即中断

---

## 已完成进度

1. **协议内核地基**
   - `ProtocolDef` / `ProtocolRegistry`
   - `SpecRegistry.satisfies_protocol()` / `get_protocol_cap()`
   - `TypeKind.PROTOCOL`
   - 统一 `PromptRenderer` 与 `PromptPart` 装配模型
   - `PROTOCOL` 序列化/rehydration 支持

2. **用户协议语法**
   - `protocol Name:`
   - `class Foo implements Bar:`
   - `protocol Child(Parent):`
   - 协议方法存在性检查
   - 协议方法签名兼容性检查

3. **泛型与协议约束**
   - `class Box[T: SomeProtocol]`
   - 泛型函数与调用点推断
   - 泛型协议：`protocol Container[T]:`
   - 特化协议实现：`class Box implements Container[int]:`

4. **Retroactive implementation**
   - `impl SomeProtocol for SomeType:`
   - 编译期检查已有类型是否满足协议方法
   - 通过后记录实现关系

5. **普通函数与 LLM 函数统一**
   - AST 层次：`IbLLMFunctionDef` 继承 `IbFunctionDef`
   - 运行时层次：`IbLLMFunction` 继承 `IbUserFunction`
   - Prompt 渲染统一
   - CPS 执行路径统一
   - trampoline 调度统一
   - 最终：移除独立 `IbLLMFunction` 类，仅保留兼容别名

6. **协议注册表替换硬编码能力**
   - 编译器 LLM parse 能力检查
   - output-hint 能力查询
   - VTable `__from_prompt__` 能力判断
   - unparseable-type 检测
   - `IbObject.__from_prompt__` 前置检查（即当前未提交改动）

---

## 测试状态

- 上一智能体在最后一次 commit 前，全量 pytest 通过。
- 当前未提交改动尚未全量验证，需按项目标准测试流程验证后提交。

---

## 接下来怎么做

1. 验证并提交当前未提交改动：
   - 运行相关协议/LLM 定向测试
   - 提交 `core/runtime/objects/kernel/base.py`
2. 跑全量 pytest 确认零回归。
3. 继续下一批清理/重构：
   - 继续用协议注册表替换剩余硬编码能力判断
   - 清理 `IbLLMFunctionDef` 残留特殊分支
   - 统一 Prompt 相关散落逻辑
   - 清理序列化/动态宿主/插件体系中的类型分支
   - 将 retroactive implementation 从“声明式”推进到“可为已有类型补充方法”
4. 更新 `docs/LANGUAGE_DESIGN_EVOLUTION.md`：
   - “尚未开始”列表已过时，应把已完成项移到“已完成”，保留真正未做的项（如意图值栈、动态宿主隔离、诊断码等）。

---

## 已知小问题

- `core/kernel/spec/registry/_protocol.py` 中 `protocol_methods()` 重复定义，建议顺手清理。
- `docs/LANGUAGE_DESIGN_EVOLUTION.md` 的“尚未开始”部分需要同步更新。
- 该分支是独立实验分支，按项目惯例不要直接合并到 `unsafe-vibe-dev` / `main`，除非用户明确授权。

---

## 一句话总结

> `exp/protocol-kernel` 已完成协议/Trait 地基、泛型约束/泛型函数、retroactive implementation、普通函数与 LLM 函数统一；当前只剩一个未提交的 `base.py` 协议化小改动，原智能体因 context 超限中断。新 session 应先验证并提交该改动，再继续“用协议注册表替换剩余硬编码能力 + 清理残留 + 统一 Prompt 散落逻辑”的下一批整理。
