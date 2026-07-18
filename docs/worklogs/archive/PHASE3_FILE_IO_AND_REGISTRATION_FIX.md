# 工作日志：Phase 3 多模态文件 I/O + 注册缺口修复

> **日期**：2026-06-25
> **分支**：unsafe-vibe-dev
> **基线**：1011 passed → **1021 passed, 5 skipped, 0 failed**
>
> **⚠️ 归档状态（2026-07-17）**：本文档记录 Phase 3 旧实现（`ibci_modules/ibci_file/` 插件 + `MediaStorage` 纯内存方案）。该插件与存储模型**已被整体淘汰**：`ibci_modules/ibci_file/` 目录已物理删除，`MediaStorage` 已删除，媒体构造入口已改为 `audio.from_file(path)` / `image.from_file(path)` / `video.from_file(path)`，统一走 `IbFileHandle` 磁盘型 handle。当前 API 与实现请参考 `docs/decisions/ADR-014-media-storage-handle-backing.md`、`docs/decisions/ADR-016-variable-storage-model.md`、`docs/decisions/ADR-020-kernel-native-vs-plugin-boundary.md` 与 `docs/IBCI_SYNTAX_REFERENCE.md` §11.7。

---

## 背景

承接 2026-06-24 的 Phase 3 多模态基础（公理 + 运行时类）。NEXT_STEPS P0 要求完成
`file.read_audio/image/video` 插件扩展 + e2e 测试。声称"完整注册路径已完成"。

## 完成项

### 1. file 插件多模态扩展
- `_spec.py`：vtable 注册 `read_audio`/`read_image`/`read_video`（return_type: audio/image/video）
- `core.py`：三个方法实现——读字节 → `MediaStorage` → `kernel_registry.get_class()` 装箱
- 关键设计：插件直接构造 `IbAudio` 返回（因 `MediaStorage` 无 boxer，原生返回会被误装箱为 `IbNativeObject`）

### 2. e2e 测试暴露的三处注册断链（关键）

e2e 测试 `audio x = file.read_audio(...)` 编译失败，顺藤摸瓜发现 Phase 3 "注册已完成"的声称不实：

| # | 缺口 | 现象 | 根因 | 修复 |
|---|------|------|------|------|
| 1 | IbSpec 缺失 | `resolve("audio")=None`、`get_class("audio")=None`、编译报"未知类型" | axiom 已注册但 spec 原型元组（`_runtime.py`）漏了 media；`builtin_initializer:110` `if not desc: continue` 静默跳过 IbClass 创建 | `specs.py` 补 `AUDIO/IMAGE/VIDEO_SPEC` + `_runtime.py` 元组 + `__init__.py` 导出 |
| 2 | `__payload_prompt__` 未注册 | `receive("__payload_prompt__")` 抛 AttributeError | `builtin_initializer` 媒体块把 IbSpec 直接传给 `AxiomRegistry.get_axiom`（期望字符串名）→ 永远 None | 改用 `SpecRegistry.get_axiom(spec)`（内部 `spec.get_base_name()`） |
| 3 | 闭包晚绑定 | 三种类型 `__to_prompt__` 全显示 "video"、`__payload_prompt__` 全用 VideoAxiom | 循环变量 `_media_type_name`/`_axiom_ref` lambda 晚绑定到最后值 | 默认参数 `tn=_type_name`/`ax=_axiom_ref` 定义时绑定 |

### 3. 测试（共 +10）
- `tests/e2e/test_e2e_multimodal_file_io.py`（4 个）：MOCK 模式端到端（含 NEXT_STEPS 示例）
- `tests/runtime/test_runtime_multimodal_dispatch.py`（6 个）：真实媒体对象 `_obj_to_payload` 分发 + base64 round-trip + `__to_prompt__` 类型名回归

### 4. 分层合规修正
- 初版把 `_obj_to_payload` 测试放在 e2e/，触发 `tests/meta/test_layering.py` 红线（e2e 禁导入解释器内部）→ 拆分到 `tests/runtime/`

---

## 经验教训

1. **"已完成"声称必须用测试佐证**：Phase 3 注册路径声称完成但无端到端测试，三处断链潜伏。e2e 测试一次暴露全部。
2. **静默跳过是陷阱**：`if not desc: continue` 让 IbSpec 缺口无声无息。
3. **闭包晚绑定**：循环内定义 lambda 引用循环变量是经典 Python 陷阱，此类代码需默认参数绑定。
4. **工时高估**：原估"3-5 天"，实际 ~7 小时（含 bug 排查）。

## 基线进展

| 阶段 | passed | skipped | failed |
|------|--------|---------|--------|
| 本轮开始前（2026-06-24） | 1011 | 5 | 0 |
| 本轮完成后（2026-06-25） | 1021 | 5 | 0 |
