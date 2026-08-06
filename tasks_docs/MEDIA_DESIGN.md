# MEDIA_DESIGN — 多模态 Phase 4 设计（封存）

> 原 `docs/backup/02_multimodal_behavior.md` 设计要点（2026-08-06 迁入）。media Phase 4 已封存
> （`PENDING_TASKS.md` §九 PT-SEALED-1），解封需显式重估。本文保留解封所需设计要点。
> **状态**：代码层零启动；`__payload_prompt__` 协议已落地（见 `docs/syntax/07_behavior_expressions.md` §7.6
> 与 `docs/subsystems/02_file_container.md`），其余（from_response / 多模态模型注册 / 非聊天端点）未实现。

---

## 一、设计目标

在行为表达式 `@~...~` / `@NAME~...~` 中，用户以自然语言描述涉及多模态数据（音频/图像/视频）的任务，无需了解底层 API payload 结构：

```ibci
import file

audio recording = audio.from_file("interview.wav")
str transcript = @WHISPER~ 识别 $recording 里的内容并转化为中文 ~
```

用户只需知道：`$recording` 引用音频变量、赋值目标声明期望输出、行为表达式描述任务。不需要知道 OpenAI payload/base64/multipart 细节。

对齐原则：易用（多模态作普通变量）、可控（内省 payload）、可复用（命名模型路由）、显式优于隐式（类型声明驱动输出模态）。

## 二、核心机制：`__payload_prompt__` 双层协议

多模态模型 API 的 payload 是**结构化内容块列表**而非纯文本。核心矛盾：`__to_prompt__()` 返回 `str`，无法携带 content block。

**方案**：`__payload_prompt__` 是 `__to_prompt__` 的多模态增强版本：

- 返回 `str` → 纯文本内容（退化为 `__to_prompt__` 行为）
- 返回 `dict` → 结构化 content block（如 `{"type":"image_url","image_url":{...}}`、`{"type":"input_audio","input_audio":{...}}`）

**调度**：插值处理优先调用 `__payload_prompt__`；content_parts 全为 str → 传统文本路径，含 dict → 多模态 payload 路径。

**兼容性**：基础类型无变化走纯文本；audio/image/video 自动切多模态；只实现 `__to_prompt__` 的类不受影响。

> 该机制已落地：`audio`/`image`/`video` 内置类型与用户类 `__payload_prompt__` 均支持，见语法层文档。

## 三、输出侧：`__from_response__` 协议（未实现）

对应模型返回非文本数据（audio output / generated image），扩展结果解析：

- `from_response(response_obj)` 接收完整 API response 对象（非仅 text content），提取目标模态数据。
- 能力标志 `has_multimodal_response_cap`。
- 接入点：`_call_llm` 返回完整响应对象后按目标类型能力分发。

> **未实现**（PENDING_TASKS §九 解封项 3）。

## 四、全模态承接类型

引入内置类型作为多模态数据一等公民：`audio`/`image`/`video`（磁盘引用身份，`MediaBacking` 承载），经 `file` 模块 `exported_types` 注入。三者继承 `file_handle`，覆写 `__payload_prompt__` 生成对应模态 content block。

> 已实现部分见 `docs/subsystems/02_file_container.md`。

## 五、命名模型路由（已实现基础）

`ai.register_model(name, url, key, model)` 注册命名模型；`@NAME~` 路由；模型名大小写敏感、字母+数字；客户端缓存。**未实现**：命名模型能力探测、fallback 链、`ai.list_models()` 查询。

## 六、解封条件

解封需实现（`PENDING_TASKS.md` §九）：
1. 多模态模型注册字段（`ai.register_model` 存 modalities/endpoint/audio_config）；
2. 非聊天端点推理绕过（endpoint 字段强制非推理，跳过 reasoning prompt 注入）；
3. 磁盘型响应解析协议（`from_response` 平行协议 + `has_multimodal_response_cap` flag）。

前置（路径统一/内核原生化/磁盘型存储）已完成。已落地协议（`__payload_prompt__`、`audio`/`image`/`video` 类型）不复述，见语法/子系统文档。
