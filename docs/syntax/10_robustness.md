## 10. 健壮性与自愈

### 10.1 llmexcept

`llmexcept` 附着在可能触发 LLM 不确定性的语句之后，提供重试机制：

```ibci
int result = @~ 1+1 等于几？只答数字 ~
llmexcept:
    print("AI 响应无法解析为整数，正在重试...")
    retry "请务必只返回一个纯数字，不要任何其他内容"
```

- `llmexcept` 必须与它保护的语句保持**相同缩进级别**，紧跟其后
- `retry` 后的字符串会作为额外系统提示词注入到重试调用中
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
- 重试耗尽 → 抛出 `LLMRetryExhaustedError`（`LLMError` 的子类，可被 `try except` 捕获，详见 §4.6）

> 历史说明：在更早的版本中，重试耗尽会将目标变量置为 `Uncertain` 而非抛出异常；当前版本统一改为
> 抛出 `LLMRetryExhaustedError`，使 LLM 失败与一般运行时异常走同一处理通道。
> 对于**无 `llmexcept` 保护**的裸 LLM 赋值，内容解析失败时 VM 内部会临时产生 `Uncertain` 哨兵，
> 并在该变量被后续读取时抛出 `LLMParseError`；LLM provider 层失败（网络/鉴权）则立即抛出
> `LLMCallError`（行为见 §4.6）。`Uncertain` 哨兵是 VM 内部信号，用户代码无需处理。

`llmexcept` 体内**禁止写入外部变量**（编译期 `SEM_LLMEXCEPT_BODY_WRITE` 错误）：

```ibci
int x = 1
int result = @~ 计算结果 ~
llmexcept:
    x = 2            # SEM_LLMEXCEPT_BODY_WRITE：禁止在 llmexcept 中写入外部变量
    retry "重试"
```

**磁盘型变量在 retry 体内的额外限制（PT-ARCH-27）**：

`file_handle`/`audio`/`image`/`video` 是磁盘引用身份对象。`llmexcept` 快照保存的是路径引用的浅拷贝，因此 retry body 中调用 `file.write_overwrite` / `file.write_overwrite_bytes` 会**污染 gold snapshot**，导致后续 retry 恢复到已被修改的文件状态。G6 起运行时直接禁止：

```ibci
import file

file_handle fh = file.open("data.txt")
str result = @~ 根据 $fh 总结内容 ~
llmexcept:
    file.write_overwrite(fh, "mutated")   # 运行时错误：retry body 中禁用 overwrite
    retry "请只返回摘要"
```

**推荐做法**：在涉及可能失败的 LLM 调用时，使用 `file.write_copy` / `file.write_copy_bytes` 创建新文件，避免副作用污染快照。

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
