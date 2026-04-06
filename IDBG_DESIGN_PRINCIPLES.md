# IBCI idbg 模块设计规范

**文档版本**: 1.0
**状态**: 设计中（暂缓实施）
**生成时间**: 2026-04-06

---

## 一、设计理念

**idbg** (IBCI Debug) 模块的设计理念是：

> **非侵入式交互** - 提供 IBCI 运行状态的便利查询，而非侵入式调试控制。

### 核心原则

1. **非侵入式**: 不暂停程序执行，不修改运行时行为
2. **信息获取**: 提供运行时的状态信息、prompt 信息、AI 反馈
3. **便利性**: 简单的 API，快速获取调试信息
4. **无副作用**: 查询操作不影响程序执行结果

### 与传统调试器的区别

| 特性 | 传统调试器 | idbg |
|------|-----------|------|
| 断点 | ✅ 支持 | ❌ 不支持 |
| 单步执行 | ✅ 支持 | ❌ 不支持 |
| 变量检查 | ✅ 支持 | ✅ 支持 |
| Prompt 查看 | ❌ 不支持 | ✅ 支持 |
| AI 结果查看 | ❌ 不支持 | ✅ 支持 |

---

## 二、设计范围

### 应该实现的功能（非侵入式）

| 功能 | 说明 | 示例 |
|------|------|------|
| `vars()` | 获取当前作用域变量 | `dict v = idbg.vars()` |
| `last_llm()` | 获取上次 LLM 调用信息 | `dict info = idbg.last_llm()` |
| `last_result()` | 获取上次 AI 执行结果 | `any result = idbg.last_result()` |
| `retry_stack()` | 获取当前重试帧栈 | `list stack = idbg.retry_stack()` |
| `intents()` | 获取详细意图栈 | `list intents = idbg.intents()` |
| `env()` | 获取环境变量 | `dict env = idbg.env()` |
| `fields(obj)` | 检查对象的字段 | `dict f = idbg.fields(my_dict)` |
| `prompt()` | 获取当前 LLM prompt | `str p = idbg.prompt()` |
| `full_prompt()` | 获取完整对话 prompt | `str p = idbg.full_prompt()` |

### 不应该实现的功能（侵入式）

| 功能 | 说明 | 原因 |
|------|------|------|
| `breakpoint()` | 设置断点 | 侵入式，会暂停执行 |
| `set_trace()` | 启用交互式调试 | 侵入式，改变执行流程 |
| `step()` | 单步执行 | 侵入式，改变执行流程 |
| `continue()` | 继续执行 | 侵入式，改变执行流程 |
| `watch()` | 监视变量 | 侵入式，需要暂停 |
| `stack()` | 调用栈追踪 | 已有替代方案 |

---

## 三、API 设计

### 3.1 状态查询

```ibci
# 获取当前作用域的所有变量
dict local_vars = idbg.vars()

# 获取指定对象的字段信息
dict fields = idbg.fields(my_object)

# 获取环境变量
dict env_info = idbg.env()
```

### 3.2 AI 交互信息

```ibci
# 获取上次 LLM 调用的详细信息
dict llm_info = idbg.last_llm()
# {
#     "prompt": "...",
#     "model": "...",
#     "timestamp": "...",
#     "duration_ms": 1234
# }

# 获取上次 AI 执行的实际返回结果
any result = idbg.last_result()

# 获取当前正在构建的 prompt
str current_prompt = idbg.prompt()

# 获取完整的对话历史 prompt
str full_prompt = idbg.full_prompt()
```

### 3.3 意图系统信息

```ibci
# 获取意图栈
list intent_stack = idbg.intents()

# 获取重试帧栈
list retry_stack = idbg.retry_stack()
```

---

## 四、实施优先级

### 高优先级

1. `vars()` - 获取当前变量，最常用的调试功能
2. `last_llm()` - 查看 AI 调用信息
3. `last_result()` - 查看 AI 返回结果

### 中优先级

4. `prompt()` / `full_prompt()` - 查看 prompt 构建
5. `intents()` - 查看意图栈
6. `fields()` - 检查对象结构

### 低优先级

7. `env()` - 环境变量
8. `retry_stack()` - 重试信息

---

## 五、暂不实现的功能

以下功能暂不实现，未来可根据需求评估：

1. **断点调试** - 侵入式调试，违反设计原则
2. **单步执行** - 侵入式调试，违反设计原则
3. **变量监视** - 需要暂停执行
4. **交互式 REPL** - 需要暂停执行

---

## 六、模块性质

### 侵入式插件 vs 非侵入式插件

idbg 虽然自身是"侵入式插件"（需要访问内核状态），但其提供的功能是**非侵入式的**：

```
idbg 模块性质
├── 形式: 侵入式插件（需要访问内核）
└── 功能: 非侵入式交互（不改变执行流程）
```

这与 `isys` 模块类似：
- `isys`: 侵入式插件，提供非侵入式路径查询
- `idbg`: 侵入式插件，提供非侵入式状态查询

---

## 七、示例用法

### 7.1 调试变量

```ibci
import idbg

int x = 10
str name = "test"

# 查看当前变量
dict vars = idbg.vars()
print("当前变量: " + (str)vars)
```

### 7.2 查看 AI 调用

```ibci
import idbg

#@ 让 AI 回答问题
str answer = @~什么是 IBCI？~

# 查看 AI 调用信息
dict llm_info = idbg.last_llm()
print("模型: " + (str)llm_info["model"])
print("耗时: " + (str)llm_info["duration_ms"]) + "ms")
print("结果: " + (str)idbg.last_result())
```

### 7.3 查看意图栈

```ibci
import idbg

# 执行一些行为描述
str result = @~写一首诗~
str result2 = @~解释这首诗~

# 查看意图历史
list intents = idbg.intents()
print("意图数量: " + (str)intents.len())
```

---

## 八、文档更新

### 02_ai_modules README 更新

原内容：
```markdown
## 目录结构

```
02_ai_modules/
├── README.md              # 本文件
├── 01_ai_basics.ibci     # AI 基础使用
├── 02_intent_annotation.ibci  # 单行意图注释
└── 03_idbg.ibci          # 交互式调试
```
```

更新为：
```markdown
## 目录结构

```
02_ai_modules/
├── README.md              # 本文件
├── 01_ai_basics.ibci     # AI 基础使用
└── 02_intent_annotation.ibci  # 单行意图注释
```

> 注意: `idbg` 模块的交互式断点调试功能暂不实现。
> 当前 idbg 提供非侵入式状态查询功能。
```

---

**文档结束**
