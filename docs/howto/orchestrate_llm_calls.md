# 如何编排稳健的 LLM 调用链

> 面向已能发起 `@~ ... ~` 调用并了解 `llmexcept` 语法的开发者。解决"如何把多个 LLM 调用
> 组合成不易因单次失败而崩溃的流程"的具体问题。
> 前置知识：`docs/syntax/10_robustness.md`（健壮性与自愈）、`docs/syntax/08_llm_callable.md`
> （LLM 可调用类）。入门级异常处理见 `docs/guide/03_handling_errors.md`；失败排查见
> `docs/howto/debug_llm_calls.md`。

## 三层失败防线

单个 LLM 调用可能因三类原因失败，编排时应逐层设防：

| 失败 | 防线 | 目的 |
|------|------|------|
| 内容解析失败（`LLMParseError`） | `llmexcept` + `retry` | 给模型一次修正机会 |
| 网络/鉴权失败（`LLMCallError`） | `ai.set_retry(n)` | 基础设施抖动自动重试 |
| 重试耗尽（`LLMRetryExhaustedError`） | 外层 `try/except` | 最终降级，流程不崩 |

## 单次调用：类型即约束

先让 LLM 输出**可被解析**——声明左值类型，编译器注入输出格式约束：

```ibci
# ❌ 裸调用：模型返回任意文本，int 解析大概率失败
result = @~ 计算 1+1 ~

# ✅ 声明 int：模型收到"只返回数字"的约束
int result = @~ 计算 1+1 ~
```

解析失败才需要 `llmexcept` 纠错；类型声明本身已经大幅降低失败率。

## 修正型重试：llmexcept + retry

LLM 返回不符合类型时，`retry` 注入一句纠错指令，并自动回喂失败响应与解析错误：

```ibci
int score = @~ 给 $product 打分 1-10 ~
llmexcept:
    retry "请只返回 1 到 10 之间的整数，不要任何其他文字"
```

需要额外副作用（打日志、计数）时在 `llmexcept` 体内做，但**不得修改参与调用的变量**：

```ibci
int attempt = 0
str summary = @~ 总结 $doc ~
llmexcept:
    attempt = attempt + 1        # 允许：attempt 未参与调用
    print("第 " + (str)attempt + " 次尝试")
    retry "请只返回一段摘要，不要解释"
```

## 长链调用：每个环节独立设防

多步流程中，每一步都可能失败。按"单步最小防 + 整链兜底"编排：

```ibci
# 第 1 步：提取关键词
str keywords = @~ 从 $text 提取 3 个关键词 ~
llmexcept:
    retry "请只返回关键词本身"

# 第 2 步：基于关键词判断情绪
if @~ $keywords 整体是正面还是负面？只答 1 或 0 ~:
    print("正面")
llmexcept:
    retry "只返回 0 或 1"

# 第 3 步：生成最终回复
str reply = @~ 用 $keywords 生成一句回复 ~
llmexcept:
    retry "请直接输出回复内容"
```

## 循环中的调用

每轮迭代独立保护；`llmexcept` 放在循环体行末，缩进与受保护语句一致：

```ibci
for str item in items:
    int score = @~ 给 $item 打分 1-10 ~
    llmexcept:
        retry "请只返回一个 1 到 10 的整数"
    print((str)score)
```

## 调用级策略：__retry__

若失败可归因于"这类调用本身格式敏感"，在 LLM 可调用类上声明 `__retry__` 默认策略，
调用点无需逐处写 `llmexcept`：

```ibci
class 翻译:
    func __retry__(self) -> dict:
        return {"max_retry": 3, "hint": "只输出译文，不要解释"}

    func __llm_call__(self, any 文本) -> dict:
        return {"user_prompt": "将 \"" + str(文本) + "\" 翻译为英语"}

翻译 t = 翻译()
str en = t("你好")     # 失败时按策略自动重试 3 次
```

- `__retry__` 是**调用级**重放（同一请求失败轮回喂），`llmexcept` 是**语句级**窗口重求值。
- 两者互补：调用级策略耗尽后，若调用点处于 `llmexcept` 保护内，帧机制继续接管重试。

## 最终降级：try/except

重试耗尽后必须给用户一个确定的出路。用外层 `try/except` 捕获
`LLMRetryExhaustedError` 做降级：

```ibci
import ai
ai.set_retry(2)

try:
    int score = @~ 给产品打分 1-10 ~
    llmexcept:
        retry "请只返回 1 到 10 之间的整数"
    print("分数：" + (str)score)
except LLMRetryExhaustedError:
    print("服务暂时不可用，使用默认分 5")
```

## 编排决策速查

| 场景 | 选用 |
|------|------|
| 单次调用、输出格式敏感 | 声明类型 + `llmexcept` + `retry` |
| 单次调用、网络可能抖动 | `ai.set_retry(n)`（自动重试基础设施失败） |
| 某一类调用反复格式失败 | 类上声明 `__retry__` 默认策略 |
| 重试耗尽后必须继续 | 外层 `try/except LLMRetryExhaustedError` 降级 |
| 循环/长链中的每一步 | 每步独立 `llmexcept` + 整链一个兜底 `try/except` |

## 常见陷阱

- **retry 体内改参与变量**：编译器报 `SEM_LLMEXCEPT_BODY_WRITE`；计数、日志用
  非参与变量。
- **retry 体内写文件**：磁盘型变量会污染黄金快照，编译器报 `SEM_LLMEXCEPT_FILE_WRITE`；
  文件 I/O 放 `llmexcept` 块之外。
- **把 `retry` 当兜底值**：`retry` 是重试指令，不是 fallback 赋值；需要默认值用外层
  `try/except`。

## 深入指引

- 完整机制与快照隔离：`docs/syntax/10_robustness.md`
- LLM 可调用类与 `__retry__`：`docs/syntax/08_llm_callable.md` §8.4
- 失败排查与调试：`docs/howto/debug_llm_calls.md`
- 批量调用（`ai.run_batch`）：`docs/syntax/08_llm_callable.md`
