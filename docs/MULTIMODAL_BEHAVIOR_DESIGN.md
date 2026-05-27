# 全模态行为表达式设计规划

> **文档性质**：架构分析与设计规划文档，供未来实施者参考。
> **创建日期**：2026-05-26
> **前置理解**：需先阅读 `docs/ARCHITECTURE_PRINCIPLES.md`、`docs/IBCI_SYNTAX_REFERENCE.md`（§7-9）、`core/kernel/axioms/primitives.py`（prompt 协议实现）。

---

## 一、设计目标

### 1.1 核心诉求

在 IBCI 的行为表达式 `@~...~` / `@NAME~...~` 中，用户应该能够**以纯自然语言方式**描述涉及多模态数据（音频、图像、视频）的任务，而无需了解底层 API 的 payload 结构。具体而言：

```ibci
audio recording = file.read_audio("interview.wav")
str transcript = @WHISPER~ 识别 $recording 里的内容并转化为中文 ~
```

用户只需要知道：
1. `$recording` 引用了一个音频变量
2. 赋值目标 `str transcript` 声明了期望得到文本输出
3. 行为表达式内部描述了自然语言任务

**不需要**知道：
- OpenAI Audio API 的 payload 格式
- base64 编码细节
- multipart/form-data 构造方式
- 模型端点路由差异

### 1.2 与 IBCI 哲学的对齐

| IBCI 原则 | 本设计如何对齐 |
|-----------|---------------|
| **易用** — 让普通人也能无痛构建 Agent | 多模态数据作为普通变量参与行为表达式，无需 API 知识 |
| **可控** — 充分可靠的调试/监控 | 全模态类型提供内省接口，可追踪实际 payload 结构 |
| **可复用** — 不依赖具体大模型 | 通过命名模型路由 + 配置抽象，模型可替换 |
| **Behavior 是交互的桥梁** | 多模态数据自然融入行为表达式的 `$var` 插值 |
| **显式优于隐式** | 类型声明驱动输出模态；模型路由显式命名 |

---

## 二、现有架构基础分析

### 2.1 `__prompt__` 协议体系（现状）

IBCI 当前的 prompt 协议由三个方法构成，定义于公理层（`core/kernel/axioms/protocols.py`）：

| 协议方法 | 方向 | 作用 | 调用时机 |
|---------|------|------|---------|
| `__to_prompt__()` → `str` | 输入构建 | 将对象转化为 prompt 中的文本表示 | `_evaluate_segments_cps` 处理 `$var` 插值时 |
| `__outputhint_prompt__()` → `str` | 输出约束 | 注入系统提示词，约束 LLM 输出格式 | `_get_llmoutput_hint` 构建系统提示词时 |
| `from_prompt(raw_response)` → `(bool, Any)` | 输出解析 | 将 LLM 原始响应解析为目标类型 | `LLMResultParser` 策略链解析结果时 |

**关键代码路径**：

```
行为表达式执行:
  vm_handle_IbBehaviorExpr (handlers.py:1446)
    → LLMExecutorImpl.execute_behavior_expression (llm_executor.py:467)
      → _evaluate_segments_cps: 对每个 $var 调用 __to_prompt__()
      → _get_llmoutput_hint: 根据赋值目标类型调用 __outputhint_prompt__()
      → _call_llm: 构建 messages=[{role, content}] 调用 AIPlugin.__call__
      → LLMResultParser: 按目标类型调用 from_prompt() 解析响应
```

**当前局限**：

1. **`__to_prompt__()` 只返回 `str`** — 无法表达二进制/文件引用/base64 等非文本数据
2. **`_call_llm` 固定构建 `messages=[{role:system,content:str},{role:user,content:str}]`** — 不支持 content 中嵌入 image_url / audio 等多部分结构
3. **`from_prompt` 只接收 `str`** — 不支持解析模型返回的音频/图像二进制流
4. **AIPlugin 只调用 `chat.completions.create`** — 不支持 audio/images/transcriptions 等不同端点

### 2.2 `@tag~` 机制（现状）

**已具备的基础设施**：

- **词法层** (`core_scanner.py:270-283`): 扫描 `@[a-zA-Z]*~` 格式，生成 `BEHAVIOR_MARKER` token
- **语法层** (`expression.py:449-452`): 提取 tag 字符串存入 `IbBehaviorExpr.tag`
- **序列化层**: tag 字段通过通用 dataclass 序列化进入编译产物
- **运行时**: node_data 中可访问 `tag` 字段

**已验证的关键限制**（2026-05-27 实测）：

- ⚠️ **词法层仅识别纯字母 tag**：`core_scanner.py:272` 使用 `isalpha()` 循环，因此 `@GPT4o~`（含数字）会被词法器在 `GPT` 处截断，`peek(3)` 为 `4` 而非 `~`，整个 `@GPT4o~` 退化为 Intent token，导致 `PAR_002` 编译错误。**实测结果**：`@WHISPER~`（纯字母）成功；`@GPT4~`/`@GPT4o~`（含数字）失败。
- ✅ 纯字母 tag（如 `@WHISPER~`, `@gpt~`, `@GPTo~`）端到端编译成功，tag 字段正确传入 AST 并保留。

**尚未实现**：
- VM handler (`handlers.py:1446-1496`) 不读取 tag 字段
- `LLMExecutorImpl.execute_behavior_expression()` 不根据 tag 路由到不同模型
- AIPlugin (`ibci_modules/ibci_ai/core.py:278`) `__call__` 签名为 `(sys_prompt: str, user_prompt: str, scene: str)` — 无 `target_model` 参数

**结论**：`@NAME~` 语法的**部分**基础设施已就绪。Phase 1 实施时需**同时**修改词法层以支持字母+数字混合 tag（将 `isalpha()` 改为 `isalnum()`），否则文档中的 `@GPT4o~` / `@WHISPER1~` 示例无法工作。纯字母 tag 路径可零 lexer 改动实现。

### 2.3 公理系统扩展性

当前 `register_core_axioms()` 注册了 31 个公理。新增公理的标准路径：

1. 在 `core/kernel/axioms/primitives.py` 中定义 `XxxAxiom(BaseAxiom)` 类
2. 设置 `has_from_prompt_cap = True` / `has_output_hint_cap = True`
3. 实现 `from_prompt()` 和 `__outputhint_prompt__()` 方法
4. 在 `register_core_axioms()` 中注册
5. 在 `core/runtime/bootstrap/builtin_initializer.py` 中，axiom 自动触发 IbClass 创建
6. 提供 Python 实现类（如 `IbAudio(IbValue)`）通过 `get_ib_implementation()` 绑定

---

## 三、扩展设计：`__payload_prompt__` 协议

### 3.1 问题本质

多模态模型的 API 调用，其输入 payload 不再是纯文本 messages，而是包含**结构化内容块**的列表。以 OpenAI 为例：

```json
{
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "描述这张图"},
      {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    ]
  }]
}
```

以 OpenAI Audio API 为例：

```json
{
  "model": "gpt-4o-audio-preview",
  "modalities": ["text", "audio"],
  "audio": {"voice": "alloy", "format": "wav"},
  "messages": [{
    "role": "user", 
    "content": [
      {"type": "text", "text": "转录这段音频"},
      {"type": "input_audio", "input_audio": {"data": "base64...", "format": "wav"}}
    ]
  }]
}
```

核心矛盾：**现有 `__to_prompt__()` 返回 `str`，无法携带结构化 content block 信息**。

### 3.2 解决方案：双层协议扩展

引入 `__payload_prompt__` 作为 `__to_prompt__` 的**多模态增强版本**，同时保持 `__to_prompt__` 的向后兼容性：

```python
class TypeAxiom:
    # 原有（保留）
    def __to_prompt__(self) -> str: ...
    
    # 新增：多模态 payload 构建协议
    has_payload_prompt_cap: bool = False  # 能力标志
    
    def __payload_prompt__(self, value: Any) -> Union[str, Dict[str, Any]]:
        """
        返回值为以下之一：
        - str: 纯文本内容（退化为 __to_prompt__ 行为）
        - dict: 结构化 content block，如:
          {"type": "image_url", "image_url": {"url": "data:..."}}
          {"type": "input_audio", "input_audio": {"data": "...", "format": "wav"}}
        """
        ...
```

**调度逻辑变化**（`_evaluate_segments_cps` 中）：

```python
# 改造前（当前代码 llm_executor.py:268-275）:
if hasattr(val, '__to_prompt__'):
    content_parts.append(val.__to_prompt__())

# 改造后:
if hasattr(val, '__payload_prompt__'):
    payload_part = val.__payload_prompt__()
    if isinstance(payload_part, str):
        content_parts.append(payload_part)  # 纯文本，保持原逻辑
    else:
        content_parts.append(payload_part)  # 结构化块，后续组装
elif hasattr(val, '__to_prompt__'):
    content_parts.append(val.__to_prompt__())
```

**content_parts 后处理**（`_call_llm` 前）：

- 若 `content_parts` 全部为 `str` → 拼接为单一字符串 → 走传统 `messages=[{role,content:str}]` 路径
- 若 `content_parts` 含有 `dict` → 组装为 `content: [...]` 多部分列表 → 走多模态 payload 路径

### 3.3 兼容性保证

| 场景 | 行为 |
|------|------|
| 所有 `$var` 都是基础类型（str/int/list 等）| 无变化，走纯文本路径 |
| 存在 `$var` 是 audio/image/video | 自动切换为多模态 payload |
| 用户自定义类只实现了 `__to_prompt__` | 正常工作，不受影响 |
| 用户自定义类实现了 `__payload_prompt__` | 参与多模态 payload 组装 |

### 3.4 `__from_response__` 协议扩展

对应输出侧，当模型返回包含非文本数据时（如 audio output、generated image），需要扩展结果解析：

```python
class TypeAxiom:
    # 原有
    def from_prompt(self, raw_response: str) -> Tuple[bool, Any]: ...
    
    # 新增：多模态响应解析
    has_multimodal_response_cap: bool = False
    
    def from_response(self, response_obj: Any) -> Tuple[bool, Any]:
        """
        接收完整的 API response 对象（非仅 text content），
        从中提取目标模态的数据。
        """
        ...
```

---

## 四、全模态承接类型设计

### 4.1 类型体系

引入以下内置类型作为多模态数据的一等公民：

| 类型名 | 公理名 | 承载内容 | `__payload_prompt__` 行为 |
|--------|--------|---------|--------------------------|
| `audio` | AudioAxiom | 音频数据 | 返回 `{"type":"input_audio","input_audio":{...}}` |
| `image` | ImageAxiom | 图像数据 | 返回 `{"type":"image_url","image_url":{...}}` |
| `video` | VideoAxiom | 视频数据 | 返回 `{"type":"video","video":{...}}` |
| `media` | MediaAxiom | 全模态复合容器 | 按内容组合返回结构化块列表 |

### 4.2 `media` 全模态容器类型

`media` 是一个特殊的内置类型，用于承载全模态模型的复合输出（同时包含文本、音频、图像等）：

```ibci
# 全模态输出由 media 承接
media result = @GPT4o~ 朗读并分析这张图片 $img ~
# result.text → str：文本部分
# result.audio → audio：音频部分  
# result.image → image：图像部分（如有）

# 也支持元组解包（当用户明确知道输出模态时）
(str text, audio speech) = @GPT4o~ 朗读这段话 $content ~
```

### 4.3 存储与内存管理策略

全模态数据（特别是音频、视频）可能占据大量内存。设计以下**透明卸载机制**：

#### 4.3.1 架构层次

```
IbMedia (运行时对象)
  ├── MediaStorage (存储后端抽象)
  │     ├── InMemoryStorage   → 小数据直接持有
  │     └── DiskBackedStorage → 大数据卸载到临时文件
  └── 访问接口（对用户透明）
```

#### 4.3.2 卸载策略

```python
class MediaStorage:
    """
    多模态数据存储后端。
    阈值以下保持在内存中；超过阈值自动写入磁盘临时区。
    """
    MEMORY_THRESHOLD = 10 * 1024 * 1024  # 10MB 
    TEMP_DIR = ".ibci_media_cache/"       # 项目目录下的临时区
    
    def __init__(self, data: bytes, mime_type: str):
        if len(data) > self.MEMORY_THRESHOLD:
            self._path = self._write_to_disk(data)
            self._data = None  # 释放内存
        else:
            self._data = data
            self._path = None
    
    @property
    def data(self) -> bytes:
        """透明访问：用户不需要知道数据在内存还是磁盘"""
        if self._data is not None:
            return self._data
        return self._read_from_disk()
```

#### 4.3.3 与 IBCI 设计原则的对齐

- **运行时可观测性优先**：MediaStorage 提供 `.location` 属性（"memory" / "disk:/path"），调试时可追踪数据位置
- **不可变 JSON artifact 不受影响**：多模态数据不进入编译期 artifact，仅在运行时产生
- **HostService 断点兼容**：`save_state()` / `load_state()` 时，磁盘上的 media cache 文件可作为状态的一部分被保存

---

## 五、命名模型路由机制

### 5.1 `@NAME~` 路由设计

`IbBehaviorExpr.tag` 字段已在编译期正确序列化。运行时需要做的是：

1. **VM handler 提取 tag** (`handlers.py` 中 `vm_handle_IbBehaviorExpr`)
2. **传递给 LLMExecutorImpl** 作为 `target_model` 参数
3. **LLMExecutorImpl 委托 AIPlugin** 查找命名配置

#### 代码影响面分析

```
vm_handle_IbBehaviorExpr (handlers.py:1446)
  ↓ 新增: tag = node_data.get("tag", "")
  ↓ 传递: execute_behavior_expression(..., target_model=tag)

execute_behavior_expression (llm_executor.py:467)  
  ↓ 新增: 接收 target_model 参数
  ↓ 传递: _call_llm(..., target_model=target_model)

_call_llm (llm_executor.py:881)
  ↓ 新增: 传递 target_model 给 provider
  ↓ provider(sys_prompt, user_prompt, target_model=target_model)

AIPlugin.__call__ (ibci_modules/ibci_ai/core.py:278)
  ↓ 新增: 根据 target_model 查找模型配置
  ↓ 使用对应配置的 client/model/endpoint
```

### 5.2 多模型配置

扩展 `api_config.json` 格式：

```json
{
    "default_model": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-xxx",
        "model": "qwen3-30b-a3b"
    },
    "GPT4o": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-xxx",
        "model": "gpt-4o",
        "modalities": ["text", "audio", "image"],
        "audio_config": {"voice": "alloy", "format": "wav"}
    },
    "WHISPER": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-xxx",
        "model": "whisper-1",
        "endpoint": "audio/transcriptions",
        "modalities": ["audio"]
    }
}
```

同时支持在脚本中动态注册：

```ibci
import ai

ai.register_model("GPT4o", {
    "base_url": "https://api.openai.com/v1",
    "api_key": env("OPENAI_KEY"),
    "model": "gpt-4o",
    "modalities": ["text", "audio", "image"]
})
```

### 5.3 默认模型兼容性

- `@~ ... ~`（无 tag）→ 使用 `default_model` 配置（与当前行为完全一致）
- `@NAME~ ... ~`（有 tag）→ 查找命名配置；未找到时报运行时错误
- 不需要改动 lexer/parser — tag 已经正确解析

---

## 六、端到端示例分析

### 6.1 示例：音频转录

```ibci
import ai

ai.set_config("https://api.openai.com/v1", env("KEY"), "gpt-4o")
ai.register_model("WHISPER", {
    "base_url": "https://api.openai.com/v1",
    "api_key": env("KEY"),
    "model": "whisper-1",
    "endpoint": "audio/transcriptions"
})

audio recording = file.read_audio("meeting.wav")
str transcript = @WHISPER~ 识别 $recording 里的内容并转化为中文 ~
print(transcript)
```

**执行流程**：

1. `file.read_audio("meeting.wav")` → 返回 `IbAudio` 对象（内含 `MediaStorage` 管理的音频数据）
2. `@WHISPER~ ... ~` 进入 VM handler:
   - tag = `"WHISPER"` → 传给 LLMExecutor
3. `_evaluate_segments_cps` 处理 `$recording`:
   - `recording` 是 `IbAudio` → 调用 `__payload_prompt__()`
   - 返回 `{"type": "input_audio", "input_audio": {"data": "base64...", "format": "wav"}}`
4. `content_parts` 含结构化块 → 组装多模态 payload
5. AIPlugin 根据 `target_model="WHISPER"` 查找配置:
   - endpoint = `"audio/transcriptions"` → 调用对应 API
6. 响应为 str → 赋给 `str transcript`（标准 from_prompt 路径）

### 6.2 示例：全模态输出

```ibci
image photo = file.read_image("cat.png")
media result = @GPT4o~ 描述这张图片并用温柔的声音朗读描述 $photo ~

print(result.text)          # "这是一只橘色的猫..."
file.save_audio(result.audio, "description.wav")
```

**执行流程**：

1. `$photo` → `IbImage.__payload_prompt__()` → `{"type":"image_url",...}`
2. 多模态 payload 构建 → 设置 `modalities: ["text", "audio"]`
3. GPT-4o 返回包含 text + audio 的响应
4. 目标类型 `media` → `MediaAxiom.from_response()` 解析完整响应对象
5. 构建 `IbMedia` 对象 → `.text` / `.audio` 属性可分别访问

### 6.3 示例：与意图系统协作

```ibci
@ 使用专业医学术语进行描述
image xray = file.read_image("chest_xray.png")
str diagnosis = @GPT4o~ 分析这张X光片 $xray ~
```

**执行流程**：

意图系统不受影响 — 意图注入依然在系统提示词中：
```
sys_prompt = "你是一个意图行为代码执行器。\n当前上下文意图：\n- 使用专业医学术语进行描述"
```
同时 user content 为多模态结构（text + image）。两者正交组合。

---

## 七、分层实施路线

### Phase 1：命名模型路由（最小可行，不涉及多模态）

**改动范围**：

| 文件 | 改动 |
|------|------|
| `core/compiler/lexer/core_scanner.py` | L272: `isalpha()` → `isalnum()` 以支持含数字的 tag（如 `@GPT4o~`）|
| `core/runtime/vm/handlers.py` | `vm_handle_IbBehaviorExpr` 提取 `tag` 传递 |
| `core/runtime/interpreter/llm_executor.py` | 接收并传递 `target_model` |
| `ibci_modules/ibci_ai/core.py` | 多模型配置管理 + 路由分发 |

**不改动**：parser, AST, 序列化, 公理层

**注意**：lexer 需要一个单字符改动（`isalpha()` → `isalnum()`）以支持含数字的模型名。纯字母模型名（如 `@WHISPER~`）无需此改动。

**验证标准**：`@NAME~ 你好 ~` 路由到正确的模型配置

---

### Phase 2：`__payload_prompt__` 协议 + 多模态 payload 构建

**改动范围**：

| 文件 | 改动 |
|------|------|
| `core/kernel/axioms/protocols.py` | 新增 `has_payload_prompt_cap` + `__payload_prompt__` 签名 |
| `core/runtime/interpreter/llm_executor.py` | `_evaluate_segments_cps` 支持结构化返回值；`_call_llm` 支持多部分 content |
| `ibci_modules/ibci_ai/core.py` | `__call__` 支持 `content: [...]` 多部分 payload |

**不改动**：lexer, parser, AST, 现有类型的公理

---

### Phase 3：`audio` / `image` / `video` 内置类型

**改动范围**：

| 文件 | 改动 |
|------|------|
| `core/kernel/axioms/primitives.py` | 新增 `AudioAxiom`, `ImageAxiom`, `VideoAxiom` |
| `core/runtime/objects/builtins.py` | 新增 `IbAudio`, `IbImage`, `IbVideo` 运行时类 |
| `core/runtime/objects/media_storage.py`（新） | `MediaStorage` 存储后端 |
| `core/runtime/bootstrap/builtin_initializer.py` | 注册新类型（自动通过 axiom 驱动） |

**Lexer/Parser 需求评估**：
- 如果选择 `audio` / `image` / `video` 作为**类型关键字**（像 `int` / `str` 一样）→ 需要加入 KEYWORDS 表
- 如果选择作为**普通类名**（像 `Enum` 一样，通过 class 注册但不是关键字）→ 不需要改动 lexer
- **建议**：作为关键字注册，与 `str` / `int` / `list` 同级，体现语言级一等支持

---

### Phase 4：`media` 全模态容器 + 响应解析

**改动范围**：

| 文件 | 改动 |
|------|------|
| `core/kernel/axioms/primitives.py` | 新增 `MediaAxiom`（`has_multimodal_response_cap = True`）|
| `core/runtime/objects/builtins.py` | 新增 `IbMedia` 运行时类 |
| `core/runtime/interpreter/llm_parsing_strategy.py` | 新增 `MultimodalParsingStrategy` |
| `core/runtime/interpreter/llm_executor.py` | `from_response` 路径 |

---

### Phase 5：磁盘卸载与生命周期管理

**改动范围**：

| 文件 | 改动 |
|------|------|
| `core/runtime/objects/media_storage.py` | `DiskBackedStorage` 实现 |
| `core/runtime/host/service.py` | `save_state` / `load_state` 含 media cache |
| `core/runtime/interpreter/llm_except_frame.py` | `__snapshot__` / `__restore__` 兼容 media |

---

## 八、与现有机制的交互分析

### 8.1 与 `llmexcept` 的交互

`llmexcept` 机制依赖 `__snapshot__` / `__restore__` 协议进行状态回滚：

- `IbAudio` / `IbImage` / `IbVideo` 需实现 `__snapshot__`：返回 `{path: str}` 引用（磁盘卸载后天然支持）
- `__restore__`：通过路径重新加载 `MediaStorage`
- **不会造成额外深拷贝开销**：大媒体数据存储在磁盘上，snapshot 仅需保存路径引用

### 8.2 与 `dispatch_eager` 并发调度的交互

当前 `dispatch_eager` (`handlers.py:691-754`) 在 LLM 调用可独立调度时走后台线程：

- 多模态 payload 构建必须在 dispatch 时完成（intent snapshot 同理）
- `__payload_prompt__()` 的 base64 编码可能耗时 → 应在 dispatch 时一并完成
- **建议**：对于 `dispatch_eligible=True` 的多模态 behavior，在 dispatch 时刻完成 payload 编码

### 8.3 与 intent 系统的交互

意图系统（`@` / `@!`）通过 `IntentResolver.resolve()` 产生文本列表注入系统提示词：

- **正交关系**：intent 注入到 `sys_prompt`；多模态数据注入到 `user content`
- **无冲突**：两者在不同位置组装，互不干扰
- 意图仍然是纯文本（描述任务背景/约束）— 不需要变成多模态

### 8.4 与 `for @~...~` 条件驱动循环的交互

`for @~判定...~:` 依赖 LLM 返回 0/1 进行布尔判断：

- 若条件行为表达式含多模态变量，payload 照常构建
- 返回值仍然通过 `from_prompt` 解析为 bool（布尔判定语义不变）
- **无特殊处理需要**

### 8.5 与类型系统的交互

编译期类型检查（`TypeCheckingPass`）：

- `audio` / `image` / `video` / `media` 作为新的基础类型，需要在 `SpecRegistry` 中注册对应 `IbSpec`
- 类型兼容性：`media` 可赋值给 `any`；`audio` 不可赋值给 `str`（显式要求转换）
- `__payload_prompt__` 能力标志在编译期可查（通过 axiom capabilities），但**不在编译期强制检查**（保持 IBCI "运行时为主" 的定位）

---

## 九、`__payload_prompt__` 协议详细设计

### 9.1 协议签名

```python
# 在 core/kernel/axioms/protocols.py 中扩展

class TypeAxiom:
    # --- 现有 ---
    has_from_prompt_cap: bool = False
    has_output_hint_cap: bool = False
    
    def from_prompt(self, raw_response: str, spec=None) -> Tuple[bool, Any]: ...
    def __outputhint_prompt__(self, spec=None) -> str: ...
    
    # --- 新增 ---
    has_payload_prompt_cap: bool = False          # 多模态输入能力标志
    has_multimodal_response_cap: bool = False     # 多模态输出能力标志
    
    def __payload_prompt__(self, value: Any) -> Union[str, Dict[str, Any], List[Dict[str, Any]]]:
        """
        将值转化为 LLM API content block 结构。
        
        返回值：
        - str → 纯文本（与 __to_prompt__ 行为一致）
        - dict → 单个 content block
        - List[dict] → 多个 content block（如一段音频被切分为多个片段）
        
        默认实现回退到 __to_prompt__():
        """
        return self.__to_prompt__(value) if hasattr(self, '__to_prompt__') else str(value)
    
    def from_response(self, response_obj: Any, spec=None) -> Tuple[bool, Any]:
        """
        从完整 API 响应对象中解析多模态结果。
        
        response_obj: 
        - 对于标准 chat.completions → message.content (str)
        - 对于音频输出 → message.audio (包含 data/transcript)
        - 对于图像生成 → data[0].b64_json 或 url
        
        默认实现回退到 from_prompt():
        """
        if isinstance(response_obj, str):
            return self.from_prompt(response_obj, spec)
        return (False, "Unsupported response format")
```

### 9.2 用户自定义类的参与

用户在 IBCI 中定义的类可以通过实现 `__payload_prompt__` 方法参与多模态调用：

```ibci
class MedicalImage:
    str path
    str modality  # "xray", "mri", "ct"
    
    func __init__(self, str path, str modality):
        self.path = path
        self.modality = modality
    
    func __to_prompt__(self) -> str:
        return "Medical " + self.modality + " image at " + self.path
    
    func __payload_prompt__(self) -> dict:
        # 用户实现：读取文件、编码为 base64、构建 content block
        str b64 = file.read_base64(self.path)
        return {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64," + b64}
        }
```

运行时 dispatch 逻辑：
1. `_evaluate_segments_cps` 中检测 `$var` 的类型
2. 优先查找 `__payload_prompt__` 方法（通过 vtable dispatch）
3. 若不存在，回退到 `__to_prompt__`

### 9.3 与 LLM 函数的协作

```ibci
llm 分析图片(image 图片, str 要求) -> str:
__sys__
你是一个视觉分析专家。
__user__
请分析以下图片。要求：$要求
$图片
llmend
```

LLM 函数中的参数插值同样走 `_evaluate_segments_cps`，因此 `$图片` 自动调用 `__payload_prompt__()` 构建结构化 content block — **无需对 LLM 函数定义语法做任何改动**。

---

## 十、AIPlugin 多模型架构

### 10.1 内部模型注册表

```python
class AIPlugin(IbStatefulPlugin):
    def __init__(self):
        # ... 现有 ...
        self._model_registry: Dict[str, ModelConfig] = {}  # 命名模型注册表
        self._clients: Dict[str, Any] = {}                 # OpenAI client 池
    
    def register_model(self, name: str, config: Dict[str, Any]) -> None:
        """注册命名模型配置"""
        self._model_registry[name] = ModelConfig(
            base_url=config["base_url"],
            api_key=config["api_key"],
            model=config["model"],
            modalities=config.get("modalities", ["text"]),
            endpoint=config.get("endpoint", "chat/completions"),
            audio_config=config.get("audio_config"),
        )
    
    def __call__(self, sys_prompt: str, user_prompt: Any, 
                 target_model: str = "", scene: str = "general") -> Any:
        """
        user_prompt 类型变化：
        - str: 传统纯文本（向后兼容）
        - List[Union[str, dict]]: 多模态 content block 列表
        
        返回值类型变化：
        - str: 纯文本响应（向后兼容）
        - dict: 多模态响应（含 text/audio/image 字段）
        """
        config = self._resolve_model_config(target_model)
        client = self._get_or_create_client(config)
        return self._dispatch_call(client, config, sys_prompt, user_prompt, scene)
```

### 10.2 调用分发逻辑

```python
def _dispatch_call(self, client, config, sys_prompt, user_prompt, scene):
    """根据配置和内容类型选择调用方式"""
    
    if config.endpoint == "audio/transcriptions":
        # 转录端点：直接提交音频文件
        return self._call_transcription(client, config, user_prompt)
    
    elif config.endpoint == "images/generations":
        # 图像生成端点
        return self._call_image_generation(client, config, user_prompt)
    
    else:
        # 标准 chat/completions（含多模态）
        messages = self._build_messages(sys_prompt, user_prompt, config)
        return self._call_chat_completions(client, config, messages)

def _build_messages(self, sys_prompt, user_prompt, config):
    """构建 messages 参数"""
    messages = [{"role": "system", "content": sys_prompt}]
    
    if isinstance(user_prompt, str):
        # 纯文本（兼容路径）
        messages.append({"role": "user", "content": user_prompt})
    elif isinstance(user_prompt, list):
        # 多模态 content blocks
        content = []
        for part in user_prompt:
            if isinstance(part, str):
                content.append({"type": "text", "text": part})
            elif isinstance(part, dict):
                content.append(part)  # 已经是结构化 block
        messages.append({"role": "user", "content": content})
    
    return messages
```

---

## 十一、关键设计决策记录

### 决策 D1：`__payload_prompt__` 是可选扩展，不替代 `__to_prompt__`

**理由**：
- 向后兼容性：所有现有类型只实现了 `__to_prompt__`，不能要求它们全部升级
- 能力标志 `has_payload_prompt_cap` 明确区分：具备多模态能力的类型主动声明
- 回退逻辑清晰：无 `__payload_prompt__` → 用 `__to_prompt__()` 结果包装为 `{"type":"text","text":...}`

### 决策 D2：`media` 类型为全模态容器，不是基类

**理由**：
- `audio`、`image`、`video` 各自独立，不继承自 `media`
- `media` 是**组合容器**，类似 `dict` 而非基类
- 这与 IBCI "公理调度 + 单次锁定" 原则一致 — 每个类型有独立的公理，不靠继承传递能力

### 决策 D3：磁盘卸载对用户完全透明

**理由**：
- IBCI 目标用户是"普通人也能无痛构建 Agent"
- 多模态数据的内存管理是底层细节，不应暴露给脚本编写者
- 提供 `.location` 等调试属性满足"运行时可观测性优先"原则

### 决策 D4：`@NAME~` 路由是用户命名，不是 IBCI 预设

**理由**：
- IBCI 不应绑定到具体模型名称（如 "GPT4o"）— 这违反"不依赖具体大模型"原则
- 用户通过 `ai.register_model("MY_MODEL", {...})` 自定义名称
- 默认模型（无 tag）始终通过 `ai.set_config()` 或 `api_config.json` 的 `default_model` 配置

### 决策 D5：元组解包与 `media` 是互补的输出承接方式

**理由**：
- 元组解包 `(str t, audio a) = @~ ... ~` — 当用户**精确知道**输出包含哪些模态时
- `media result = @~ ... ~` — 当输出模态不确定或需要动态探测时
- 两者可以共存，由用户根据场景选择

### 决策 D6：不改变 `_call_llm` 返回值的基本契约

**理由**：
- 当前 `_call_llm` 返回 `str`，所有下游都基于此
- 多模态响应通过**新路径** `_call_llm_multimodal` 返回 `dict`，与原路径并行
- `from_response` 是新协议，不替代 `from_prompt`
- 确保所有只使用文本模型的代码路径完全不受影响

---

## 十二、风险与约束

### 12.1 已识别风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 词法层 tag 仅识别纯字母（`isalpha`），含数字的模型名编译失败 | Phase 1 示例（`@GPT4o~`）不可用 | 将 `isalpha()` 改为 `isalnum()`；需评估是否与现有 token 冲突 |
| 多模态 API 格式碎片化（OpenAI / Anthropic / Google 各不相同）| AIPlugin 实现复杂度上升 | 定义 IBCI 标准 content block 格式，AIPlugin 内部做供应商适配 |
| 大文件 base64 编码导致内存峰值 | 可能超出解释器内存限制 | MediaStorage 的流式编码 + 磁盘卸载 |
| llmexcept retry 时多模态 payload 重复构建 | 性能浪费 | 在 LLMExceptFrame 中缓存已编码的 payload |
| 用户 `__payload_prompt__` 返回非法结构 | 运行时 API 调用失败 | 在 _evaluate_segments 后增加 payload 验证层 |

### 12.2 明确不做的事情

- ❌ **不在编译期做模态兼容性检查** — IBCI 不是静态检查器前置强依赖
- ❌ **不引入 WebSocket/流式连接作为 Phase 1-5 的一部分** — 实时流式属于 L3 协程层依赖项
- ❌ **不为多模态创建新的控制流** — 行为表达式的同步执行语义不变
- ❌ **不创建 media 基类继承树** — 每个模态类型独立公理

---

## 十三、附录：受影响文件清单

### 需要新增的文件

| 文件路径 | 用途 |
|---------|------|
| `core/runtime/objects/media_storage.py` | MediaStorage 存储后端 |
| `core/runtime/objects/media_types.py` | IbAudio, IbImage, IbVideo, IbMedia 运行时类 |
| `tests/e2e/test_e2e_multimodal.py` | 端到端多模态测试 |
| `tests/kernel/test_media_axioms.py` | 公理层单元测试 |

### 需要修改的文件

| 文件路径 | 改动性质 |
|---------|---------|
| `core/kernel/axioms/protocols.py` | 新增协议签名 |
| `core/kernel/axioms/primitives.py` | 新增 Audio/Image/Video/Media Axiom |
| `core/runtime/interpreter/llm_executor.py` | `_evaluate_segments_cps` + `_call_llm` 多模态路径 |
| `core/runtime/interpreter/llm_parsing_strategy.py` | 新增 MultimodalParsingStrategy |
| `core/runtime/vm/handlers.py` | `vm_handle_IbBehaviorExpr` 提取并传递 tag |
| `core/runtime/objects/builtins.py` | 注册新类型实现 |
| `core/runtime/bootstrap/builtin_initializer.py` | 新类型自动注册（通过 axiom 驱动） |
| `ibci_modules/ibci_ai/core.py` | 多模型路由 + 多模态 payload 构建 |
| `core/compiler/lexer/core_scanner.py` | L272: `isalpha()` → `isalnum()`（Phase 1 即需，若要支持含数字 tag）|
| `core/compiler/common/tokens.py` | 对应 TokenType（仅当新增 audio/image/video 关键字时需要）|
| `docs/IBCI_SYNTAX_REFERENCE.md` | 文档更新 |
| `docs/KNOWN_LIMITS.md` | 记录多模态限制 |

### 不需要改动的文件

- `core/kernel/ast.py` — IbBehaviorExpr 已有 tag 字段
- `core/compiler/parser/` — 解析逻辑已正确处理 tag（从 BEHAVIOR_MARKER token value 提取）
- `core/compiler/serialization/` — 通用 dataclass 序列化自动处理所有字段
- `core/compiler/semantic/` — 类型声明通过已有 SpecRegistry 通路
- `core/runtime/interpreter/llm_except_frame.py` — media 类型自带 snapshot 协议

---

*本文档记录设计分析与规划，不代表最终实现细节。实施时应以代码中的实际架构为准。*

---

## 附录 B：事实核验记录（2026-05-27）

> 本节记录对文档中关键声明的交叉核验结果，供实施者确认哪些前提仍然有效。

### 已验证为正确的声明

| 声明 | 核验方式 | 结果 |
|------|---------|------|
| `IbBehaviorExpr.tag` 字段存在于 AST | `core/kernel/ast.py:398` 实查 | ✅ `tag: str = ""` |
| `vm_handle_IbBehaviorExpr` 不读取 tag | `handlers.py:1446-1496` 全文扫描 | ✅ 无 `tag` 引用 |
| `LLMExecutorImpl.execute_behavior_expression` 不接收 target_model | `llm_executor.py:467` 签名检查 | ✅ 无该参数 |
| `AIPlugin.__call__` 签名无 target_model | `ibci_modules/ibci_ai/core.py:278` | ✅ 签名为 `(sys_prompt, user_prompt, scene)` |
| `_evaluate_segments_cps` 只调用 `__to_prompt__()` 返回 `str` | `llm_executor.py:270-271` | ✅ 确认 |
| `_call_llm` 返回 `str`，签名接收 `str` | `llm_executor.py:881` | ✅ 确认 |
| `dispatch_eager` 机制存在且在赋值上下文触发 | `handlers.py:691-760` | ✅ 完整实现存在 |
| `BehaviorDependencyPass` 写入 `llm_deps`/`dispatch_eligible` | 实测 AST 节点字段确认 | ✅ |
| 测试基线：790 passed, 2 skipped | 2026-05-27 实跑 pytest | ✅ |

### 发现的事实偏差

| 原文声明 | 实际情况 | 影响 |
|---------|---------|------|
| "tag 字段正确序列化进不可变 JSON artifact" | 序列化器无特殊 tag 处理逻辑，但通过 dataclass 通用路径确实传入 `CompilationResult.module_ast`，运行时 `get_node_data` 可访问 | 影响极低——序列化是正确的，但机制描述不够精确 |
| "正确扫描 `@[a-zA-Z]*~` 格式" | 词法层使用 `isalpha()` 循环：**只识别纯字母 tag**；含数字（如 `GPT4o`）会编译失败 | **Phase 1 关键障碍**——文档示例 `@GPT4o~` 当前不可编译 |
| "零 lexer/parser 改动" 的结论 | 如果使用含数字的模型名（业界常用，如 GPT4、GPT4o、Claude3），需改 lexer | 需修正为"需一行 lexer 改动" |
| §五代码影响面分析引用 `llm_executor.py:268-275` | 实际为 `llm_executor.py:270-276`（CPS 生成器路径）| 偏差 2 行，影响不大 |

### 设计可行性评估

| 维度 | 评分 | 备注 |
|------|------|------|
| 与现有架构的契合度 | ⭐⭐⭐⭐⭐ | 完全利用已有 tag 基础设施 + 公理系统扩展点 |
| Phase 1 实施风险 | ⭐（低）| 仅需 3-4 个文件改动，影响面可控 |
| Phase 2-3 实施复杂度 | ⭐⭐⭐（中）| `_evaluate_segments_cps` CPS 路径需谨慎处理混合 content |
| 向后兼容性 | ⭐⭐⭐⭐⭐ | 纯文本路径完全不变，新协议为可选扩展 |
| 文档中的设计决策质量 | ⭐⭐⭐⭐ | D1-D6 决策合理；D6（不改 `_call_llm` 返回契约）可能在 Phase 4 时被挑战 |

### 建议的后续行动

1. **立即可做**：将 `core_scanner.py:272` 的 `isalpha()` 改为 `isalnum()`（或 `isalnum() or c == '_'`），使 `@GPT4o~` 语法可用。这是 Phase 1 的最小前置条件。
2. **Phase 1 实施前**：确认 `isalnum()` 修改不会与现有 token 类型冲突——在 IBCI 中 `@` 后跟数字目前不是合法 token，故冲突风险极低。
3. **重新评估 D6 决策**：`_call_llm` 当前返回 `str`，但 Phase 4 `from_response` 需要访问完整 API 响应对象。建议在 Phase 2 时就预留 `_call_llm_raw` 返回完整响应的通路，避免 Phase 4 大规模重构。
4. **补充 dispatch_eager 交互测试**：文档 §8.2 正确识别了 dispatch_eager + 多模态的交互点，但未提及 `llmexcept` 保护下的 dispatch 禁用逻辑（`handlers.py:720-723`）对多模态的影响——这需要在 Phase 2 测试中覆盖。
