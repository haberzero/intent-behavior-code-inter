# 多模态功能分析结论 — 与现有设计文档的比对归并

> **创建日期**：2026-05-28
> **文档性质**：对 `MULTIMODAL_BEHAVIOR_DESIGN.md`（2026-05-26 创建）进行代码事实核查后的补充分析和归并建议。
> **关联文档**：`MULTIMODAL_BEHAVIOR_DESIGN.md`（原始设计规划）、`COROUTINE_DESIGN_NOTES.md`（协程相关，已独立）
> **⚠️ 归档状态（2026-05-28）**：归并已执行（方案 A）。§六 Semantic 缺陷分析、§七 CPS 缺陷分析、§九 待决策清单已合并入 `MULTIMODAL_BEHAVIOR_DESIGN.md` 附录 C。本文档降级为历史归档，不再维护。**请以 `MULTIMODAL_BEHAVIOR_DESIGN.md` 为权威文档。**

---

## 〇、文档关系说明

| 文档 | 创建时间 | 定位 | 当前状态 |
|------|---------|------|---------|
| `MULTIMODAL_BEHAVIOR_DESIGN.md` | 2026-05-26 | 完整设计规划（Phase 1-5） + 附录 B 事实核验 | Phase 1 ✅ Phase 2 ✅ 已更新 |
| `MULTIMODAL_ANALYSIS_CONCLUSIONS.md`（本文档） | 2026-05-28 | 补充分析：semantic/CPS 缺陷、待决策项、归并建议 | 等待归并决断 |
| `COROUTINE_DESIGN_NOTES.md` | 2026-05-28 | 协程/迭代器相关设计笔记（已独立拆分） | ⏸️ 搁置 |

**归并建议**：本文档中与 `MULTIMODAL_BEHAVIOR_DESIGN.md` 重复的内容（§一~§五）建议合并入原文档对应章节；本文档独有的内容（§六 Semantic 缺陷、§七 CPS 缺陷、§八 待决策汇总）建议作为原文档新附录或独立保留。

---

## 一、多媒体相关载体（Carrier Types）

### 1.1 现状

- 当前 IBCI 无内置多媒体类型。所有变量在行为表达式中参与 `$var` 插值时，仅通过 `__to_prompt__()` 返回纯文本 `str`。
- `__payload_prompt__` 协议已在公理层声明（`core/kernel/axioms/protocols.py:88`、`primitives.py:119`），但尚无具体的多媒体 Axiom 实现它。

### 1.2 设计结论

| 载体类型 | 公理名 | 内部数据 | 设计定位 |
|---------|--------|---------|---------|
| `audio` | `AudioAxiom` | 音频二进制数据 + mime/format 元信息 | 语言级关键字类型，与 `str`/`int` 同级 |
| `image` | `ImageAxiom` | 图像二进制数据 + mime 元信息 | 语言级关键字类型 |
| `video` | `VideoAxiom` | 视频二进制数据 + mime 元信息 | 语言级关键字类型 |
| `media` | `MediaAxiom` | 全模态复合容器（text + audio + image） | 语言级关键字类型，作为多模态输出承接器 |

### 1.3 待决策项

1. **关键字 vs 类名**：设计文档建议作为关键字（加入 KEYWORDS 表），需改动 lexer。如果作为普通类名则无需改 lexer，但丧失语言级一等公民地位。**建议：关键字。**
2. **`MediaStorage` 内存策略**：Phase 3 先采用纯内存方案；Phase 5 再引入磁盘卸载。阈值建议 10MB。
3. **文件 I/O 来源**：`file.read_audio()` / `file.read_image()` 等作为内置模块方法提供，还是独立顶层函数？**建议：模块方法（`import file`）。**

---

## 二、多模态调用模式（Invocation Patterns）

### 2.1 现有调用路径（已实现 Phase 1 + Phase 2）

```
行为表达式 @NAME~ ... $var ... ~
  → vm_handle_IbBehaviorExpr 提取 tag → 传 target_model
  → _evaluate_segments_cps 对 $var 调用 _obj_to_payload()
    → 优先 __payload_prompt__（返回 dict/list）
    → 回退 __to_prompt__（返回 str）
  → 若 content_parts 含 dict → 走多模态 payload 路径
  → AIPlugin.__call__(sys_prompt, user_prompt: List, target_model=tag)
    → _dispatch_call 根据 endpoint/modalities 分发
```

### 2.2 三种调用模式

| 模式 | 语法示例 | 路由方式 | 输出类型 |
|------|---------|---------|---------|
| 纯文本（默认） | `str x = @~ 翻译 $text ~` | 无 tag → default_model; chat/completions | `str` |
| 多模态输入 | `str desc = @GPT4o~ 描述 $image ~` | tag 路由命名模型; multimodal content blocks | `str` |
| 全模态输出 | `media r = @GPT4o~ 朗读 $text ~` | tag 路由; modalities=[text,audio] | `media` 容器 |

### 2.3 LLM 函数中的多模态

```ibci
llm 分析图片(image 图片, str 要求) -> str:
__sys__
你是一个视觉分析专家。
__user__
请分析以下图片。要求：$要求
$图片
llmend
```

LLM 函数的参数插值复用 `_evaluate_segments_cps`，多模态变量自动通过 `__payload_prompt__()` 构建结构化 content block——**无需对 LLM 函数定义语法做任何改动**。

### 2.4 结论

- 调用模式设计合理且与现有架构正交
- `@NAME~` 路由已端到端实现（Phase 1 ✅）
- `_obj_to_payload` 分发已实现（Phase 2 ✅）
- 缺失：具体多媒体 Axiom 的 `__payload_prompt__` 实现（Phase 3 待做）

---

## 三、多模态 Payload 设计

### 3.1 输入侧：`__payload_prompt__` 协议

**协议签名**（已在 `protocols.py:88` 定义）：

```python
def __payload_prompt__(self, value: Any, spec: Optional["IbSpec"] = None
) -> Union[str, Dict[str, Any], List[Dict[str, Any]]]
```

**返回值语义**：
- `str` → 纯文本（退化为 `__to_prompt__` 行为）
- `dict` → 单个 content block（如 `{"type": "image_url", "image_url": {"url": "data:..."}}`）
- `List[dict]` → 多个 content block（如音频切分为多片段）

**调度逻辑**（已在 `llm_executor.py:136-168` 实现）：
1. 优先通过 `receive('__payload_prompt__', [])` 分发
2. 结果若为 dict/list → 多模态结构化内容
3. 否则回退到 `_obj_to_prompt_str()` → 纯文本

### 3.2 输出侧：`from_response` 协议（待实现）

**问题**：当前 `_call_llm` 返回 `str`，无法承载 API 返回的音频/图像二进制流。

**设计方案**：
- 新增 `has_multimodal_response_cap: bool` 能力标志
- 新增 `from_response(response_obj) -> (bool, Any)` 方法
- 新增 `_call_llm_multimodal` 路径，返回完整 API response 对象
- `MediaAxiom.from_response()` 从响应中提取 text/audio/image 构建 `IbMedia`

### 3.3 待决策项

1. **D6 决策再评估**：设计文档中 D6 决定"不改 `_call_llm` 返回契约"，但 Phase 4 需要完整 response。建议在 Phase 3 就预留 `_call_llm_raw` 接口。
2. **Payload 验证**：用户自定义 `__payload_prompt__` 返回非法结构时如何处理？建议在 `_evaluate_segments_cps` 后增加验证层（Phase 3+ 课题）。
3. **供应商适配**：OpenAI / Anthropic / Google 的 content block 格式不同。IBCI 应定义标准格式，AIPlugin 内部做适配。

---

## 四、承接器设计（Output Receivers）

### 4.1 单模态承接

```ibci
str text = @~ 描述这张图 $img ~        # 承接文本
audio speech = @GPT4o~ 朗读 $text ~     # 承接音频
image art = @DALLE~ 画一只猫 ~           # 承接图像
```

类型声明决定输出模态：
- 赋值目标类型 → `__outputhint_prompt__()` 注入系统提示词约束 LLM 输出格式
- 响应解析时根据目标类型选择 `from_prompt`（文本）或 `from_response`（多模态）

### 4.2 全模态承接器 `media`

```ibci
media result = @GPT4o~ 朗读并分析这张图片 $img ~
result.text   # str: 文本部分
result.audio  # audio: 音频部分
result.image  # image: 图像部分（如有）
```

**`media` 是组合容器，不是基类**（决策 D2）：
- `audio`、`image`、`video` 各自独立，不继承自 `media`
- `media` 类似 struct/dict，动态持有各模态字段
- 未返回的模态字段为 `None`（Optional 语义）

### 4.3 元组解包承接

```ibci
(str text, audio speech) = @GPT4o~ 朗读这段话 $content ~
```

当用户精确知道输出模态时，可用元组解包直接获取各模态数据。

### 4.4 结论

- 承接器设计与现有类型系统兼容
- `media` 容器的属性访问需要在运行时对象 `IbMedia` 上实现 `.text` / `.audio` / `.image` 属性
- 元组解包需要确认 `TypeCheckingPass` 对 behavior 返回类型的推断逻辑（可能需要扩展）

---

## 五、相关内置变量

### 5.1 多模态类型对象作为内置变量

注册路径：`core/runtime/bootstrap/builtin_initializer.py` 通过 axiom 驱动自动注册。

| 内置变量 | 说明 |
|---------|------|
| `audio` | AudioAxiom 对应的 IbClass 对象 |
| `image` | ImageAxiom 对应的 IbClass 对象 |
| `video` | VideoAxiom 对应的 IbClass 对象 |
| `media` | MediaAxiom 对应的 IbClass 对象 |

### 5.2 文件 I/O 相关

| 内置方法 | 说明 |
|---------|------|
| `file.read_audio(path)` → `audio` | 读取音频文件 |
| `file.read_image(path)` → `image` | 读取图像文件 |
| `file.read_video(path)` → `video` | 读取视频文件 |
| `file.save_audio(audio, path)` | 保存音频到文件 |
| `file.save_image(image, path)` | 保存图像到文件 |

### 5.3 `MediaStorage` 相关属性

| 属性 | 说明 |
|------|------|
| `.data` → `bytes` | 二进制数据（透明访问，用户无需知道在内存还是磁盘） |
| `.mime_type` → `str` | MIME 类型 |
| `.format` → `str` | 格式标识（wav, png, mp4 等） |
| `.size` → `int` | 数据大小（字节） |
| `.location` → `str` | 调试用：`"memory"` 或 `"disk:/path"`（运行时可观测性） |

---

## 六、Semantic 相关的设计缺陷/不完善

### 6.1 TypeCheckingPass 对多模态类型的盲区

**现状**：`TypeCheckingPass`（`type_checking_pass.py`）对 `IbBehaviorExpr` 的类型处理已有特殊路径（L257-260, L314-315），但完全基于"行为表达式返回值类型 = 赋值目标类型"的假设。

**问题**：
1. **无多模态类型兼容性检查**：`audio x = @~ 你好 ~` — 若模型不支持音频输出，编译期无法发出 warning
2. **`media` 解包推断缺失**：`(str t, audio a) = @GPT4o~ ... ~` — 当前元组解包的类型检查路径不覆盖 behavior 返回值的模态分解
3. **`__payload_prompt__` 能力不参与编译期检查**：设计文档明确说"不在编译期强制检查"（§8.5），但即使作为 warning 级别的提示也未实现

**结论**：根据 IBCI "运行时为主" 的定位，这不是 bug 而是 by-design。但可以考虑在 `IntegrityCheckPass` 中增加 optional warning 级别提示。

### 6.2 BehaviorDependencyPass 对多模态的影响

**现状**：`BehaviorDependencyPass`（`behavior_dependency_pass.py`）计算 `llm_deps` / `dispatch_eligible`，驱动 `dispatch_eager` 并行调度。

**问题**：
- 多模态变量（`audio`/`image`）的 `__payload_prompt__()` 涉及 base64 编码，可能耗时
- 当前 `dispatch_eligible` 判定不考虑多模态 payload 构建的时间成本
- `dispatch_eager` + 多模态的交互尚无专项测试

**结论**：暂不改动 `BehaviorDependencyPass` 逻辑；多模态 payload 构建在 dispatch 时刻一并完成（设计文档 §8.2 建议一致）。

### 6.3 SymbolResolutionPass 对多模态类型的注册

**现状**：`SymbolResolutionPass` 通过 `SpecRegistry` 解析类型名。新增 `audio`/`image`/`video`/`media` 类型需要在 registry 中注册对应 `IbSpec`。

**影响路径**：
- 若作为关键字：需 lexer 添加 token → parser 识别类型声明 → `SymbolCollectionPass` 正确处理
- 若作为类名：仅需在 `builtin_initializer` 中注册 → `SpecRegistry` 自动可见

**结论**：无论哪种方式，`SymbolResolutionPass` 本身无需修改——它通过 registry 查询类型名，新类型注册后自动可见。

---

## 七、CPS 生成器相关的设计缺陷/不完善

### 7.1 `_evaluate_segments_cps` 的多模态路径

**现状**：已实现（`llm_executor.py:335-419`），支持混合 content blocks 返回。

**已知问题**：
1. **llmexcept retry 时多模态 payload 重复构建**：每次 retry 会重新执行 `_evaluate_segments_cps`，对大文件做重复 base64 编码。建议在 `LLMExceptFrame` 中缓存已编码的 payload。
2. **`dispatch_eager` + 多模态交互无测试**：`handlers.py:720-723` 的 dispatch 禁用逻辑对多模态的影响未验证。

### 7.2 `_call_llm` 返回值限制

**现状**：`_call_llm` 返回 `str`，所有下游（`LLMResultParser`、`from_prompt`）基于此。

**问题**：Phase 4 `from_response` 需要完整 API response 对象（含 audio/image 二进制）。

**解决方向**：
- 新增 `_call_llm_raw` 或 `_call_llm_multimodal` 返回 `dict`
- 目标类型为 `media`/`audio`/`image` 时走新路径
- 目标类型为 `str`/`int`/`list` 等时保持原路径不变

### 7.3 CPS 生成器与 `from_response` 的接入点

**现状**：`invoke_behavior_cps`（`llm_executor.py:925`）调用 `_evaluate_segments_cps` 后调用 `_call_llm`，结果交给 `LLMResultParser`。

**需要的改动**（Phase 4）：
```
invoke_behavior_cps:
  content = yield from _evaluate_segments_cps(...)
  if target_type has multimodal_response_cap:
      raw_response = _call_llm_multimodal(...)  # 新路径
      result = target_axiom.from_response(raw_response)
  else:
      text_response = _call_llm(...)            # 原路径
      result = LLMResultParser.parse(...)
```

---

## 八、与原设计文档的差异比对

### 8.1 原文档（`MULTIMODAL_BEHAVIOR_DESIGN.md`）已涵盖

| 主题 | 原文档位置 | 本文档重复内容 |
|------|-----------|--------------|
| 载体类型定义（audio/image/video/media） | §四 | §一（完全重叠） |
| `__payload_prompt__` 协议设计 | §三、§九 | §三.1（完全重叠） |
| 调用模式和路由 | §五、§六 | §二（完全重叠） |
| 承接器设计（media 容器 + 元组解包） | §四.2 | §四（完全重叠） |
| 决策 D1-D6 | §十一 | 散布引用 |
| Phase 1-5 实施路线 | §七 | §九"立即可做"部分 |
| 风险与约束 | §十二 | 部分引用 |

### 8.2 本文档的独有贡献（原文档未涵盖）

| 主题 | 本文档位置 | 价值 |
|------|-----------|------|
| **Semantic 层缺陷分析** | §六 | 识别 TypeCheckingPass / BehaviorDependencyPass / SymbolResolutionPass 对多模态的具体影响 |
| **CPS 生成器缺陷分析** | §七 | 识别 retry payload 重复构建、`_call_llm` 返回值限制、`invoke_behavior_cps` 接入点 |
| **汇总的待决策清单** | §九"需要先决策再实施" | 从散落各处的待定项中提取出的统一决策列表 |
| **代码事实核查（2026-05-28）** | §三.1 具体行号引用 | 确认 Phase 2 实现的精确代码位置 |

### 8.3 归并建议

**方案 A（推荐）**：保留原文档为主体设计文档，将本文档 §六、§七 的内容追加为原文档"附录 C：Semantic/CPS 层交互分析"。本文档降级为归档。

**方案 B**：将两份文档完全合并为单一文档。缺点是会使原文档过于冗长（已有 923 行）。

**等待您的决断。**

---

## 九、下一步行动建议

### 立即可做（Phase 3 实施）

1. 在 `KEYWORDS` 表中注册 `audio`、`image`、`video`、`media`
2. 实现 `AudioAxiom`、`ImageAxiom`、`VideoAxiom` + 对应 `IbAudio`、`IbImage`、`IbVideo` 运行时类
3. 实现 `MediaStorage`（纯内存版）
4. 注册到 `builtin_initializer.py`
5. 编写单元 + e2e 测试（MOCK 模式）

### 需要先决策再实施

1. `media` 容器的属性访问模型（固定属性 vs 动态字典）
2. `from_response` 协议的接入点（Phase 4 预留 vs Phase 4 再改）
3. 文件 I/O 模块的 API 形态（`file.read_audio` vs `audio.from_file`）
4. 多模态变量的 `__snapshot__` / `__restore__` 实现策略

### 远期（Phase 4-5）

1. `MediaAxiom` + `from_response` + `_call_llm_multimodal`
2. 磁盘卸载 `DiskBackedStorage`
3. `llmexcept` payload 缓存优化
4. 供应商适配层（Anthropic / Google content block 格式）

---

*本文档记录分析结论，不代表最终实施细节。实施时应以代码中的实际架构为准。*
