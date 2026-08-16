## 10. 健壮性与自愈

> 本章描述 IBCI 的 AI 容错控制流机制。面向已阅读意图系统章节的开发者。覆盖 `llmexcept` 异常捕获、`retry` 重试机制、LLM 异常体系与快照隔离。

### 10.1 llmexcept

`llmexcept` 附着在可能触发 LLM 不确定性的语句之后，提供重试机制：

```ibci
int result = @~ 1+1 等于几？只答数字 ~
llmexcept:
    print("AI 响应无法解析为整数，正在重试...")
    retry "请务必只返回一个纯数字，不要任何其他内容"
```

- `llmexcept` 必须与它保护的语句保持**相同缩进级别**，紧跟其后
- `retry` 后的字符串作为纠错指令注入重试调用（经标准多轮对话的 `message_history` 回喂，不拼入系统提示词）；重试调用同时自动回喂上一次失败响应与解析错误（自动错误回喂）
- 重试次数由 `ai.set_retry(n)` 配置（默认 3 次）

保护条件语句时，`llmexcept` 跟在条件块末尾：

```ibci
if @~ $text 是正面的吗？只答 1 或 0 ~:
    print("正面")
llmexcept:
    retry "只返回 0 或 1"
```

保护循环体内的行：

```ibci
for str item in items:
    int score = @~ 给 $item 打分 1-10 ~
    llmexcept:
        retry "请只返回一个 1 到 10 的整数"
    print("分数: " + (str)score)
```

### 10.2 llmretry 语法糖

```ibci
str res = @~ 判断当前状态，只回答正常或异常 ~
llmretry "如果无法判断，请回复 0 并说明原因"
```

`llmretry` 等价于只有 `retry` 语句的 `llmexcept`，是其精简写法。

### 10.3 快照隔离模型

`llmexcept` 使用**快照隔离**保证 retry 的一致性：

- 进入 LLM 语句执行时，创建当前变量/意图上下文/循环状态的快照
- LLM 调用成功 → 结果 commit 到目标变量，退出快照
- LLM 调用失败 → 执行 `llmexcept` 体，然后从快照恢复状态并 retry
- 重试耗尽 → 抛出 `LLMRetryExhaustedError`（`LLMError` 的子类，可被 `try except` 捕获，详见 `04_control_flow.md` 的 try/except 章节）

对于**无 `llmexcept` 保护**的裸 LLM 赋值，内容解析失败时抛出 `LLMParseError`；LLM provider 层失败（网络/鉴权）时立即抛出 `LLMCallError`。

`llmexcept` 体内**禁止修改参与 LLM 调用的变量**（编译期 `SEM_LLMEXCEPT_BODY_WRITE` / `SEM_LLMEXCEPT_MUTATING_CALL` 错误）：

保护集为：`$` 插值引用的变量、意图注解引用的变量、接收 LLM 结果的赋值目标。

```ibci
int x = 1
str result = @~ 翻译 $text ~
llmexcept:
    result = "fallback"   # SEM_LLMEXCEPT_BODY_WRITE：result 是 LLM 赋值目标
    text = "other"        # SEM_LLMEXCEPT_BODY_WRITE：text 参与 $ 插值
    x = 2                 # 允许：x 未参与 LLM 调用
    retry "重试"
```

对被保护变量的 mutating 方法调用同样禁止：

```ibci
list items = [1, 2, 3]
str summary = @~ 总结 $items ~
llmexcept:
    items.append(4)       # SEM_LLMEXCEPT_MUTATING_CALL：items 参与 $ 插值
    retry "请只返回摘要"
```

非 LLM 参与变量的修改默认允许（辅助统计、诊断标记等用途）。

**运行期安全网**：即使编译期未捕获的变异路径（如用户函数内部间接修改），运行期在 retry 前会比对被保护变量与黄金快照。若检测到篡改，发出快照隔离违规警告（`RUN_LLMEXCEPT_SNAPSHOT_VIOLATION`）并恢复黄金快照后继续 retry。

**磁盘型变量在 retry 体内的额外限制**：

`file_handle`/`audio`/`image`/`video` 是磁盘引用身份对象。`llmexcept` 快照保存的是路径引用的浅拷贝，因此 retry body 中调用任何文件写/删都会**污染黄金快照**（写新文件若路径撞上已有 backing 同样污染；删除令 handle 悬空），导致后续 retry 恢复到已被破坏的文件状态。

retry body 内**禁止文件写/删操作**（`file.write` 与 `remove`），编译期以 `SEM_LLMEXCEPT_FILE_WRITE` 拦截直接与间接调用，运行时兜底动态分派等漏检情形。只读操作（`open` / `read` / `read_bytes` / `exists`）允许。

```ibci
import file

file_handle fh = file.open("data.txt")
str result = @~ 根据 $fh 总结内容 ~
llmexcept:
    file.write(fh, "mutated", overwrite_flag="overwrite")   # 编译错误 SEM_LLMEXCEPT_FILE_WRITE：retry body 中禁用文件写/删
    retry "请只返回摘要"
```

**推荐做法**：文件 I/O 放在 `llmexcept` 块之外完成；retry body 内仅用 `retry "hint"` 提供修正指引。

> **固有边界**：外部进程（非 IBCI 代码）触碰 backing 文件无法被 IBCI 拦截，是磁盘态快照的固有限制（详见 `docs/KNOWN_LIMITS.md`）。

### 10.4 用户自定义快照协议

对于复杂对象，可以通过 `__snapshot__` / `__restore__` 协议控制快照粒度：

```ibci
class Config:
    str mode
    int attempts

    func __snapshot__(self) -> int:
        return self.attempts    # 只快照关键字段

    func __restore__(self, int saved):
        self.attempts = saved   # 恢复关键字段
```
---

## 深入指引

- llmexcept 实现机制：docs/architecture/04_vm_interpreter.md §6
- 快照与序列化：docs/architecture/08_storage_model.md
- llmexcept 文件写限制：docs/KNOWN_LIMITS.md §二十
