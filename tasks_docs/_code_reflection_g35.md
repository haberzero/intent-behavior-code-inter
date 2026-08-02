# 反射规避架构缺陷修复 — 组 3/5：异常探测 + 静默兜底（临时任务文档）

> 临时任务文档，Phase 5 完成后经用户确认删除。
> **状态**：组 3 全部完成；组 5 完成 7/9（5.4/5.7 待定）。

## 组 3：用异常做能力探测 ✅ 全部完成

- **3.1** `control_flow.py:284-291`：`except (AttributeError, InterpreterError)` → `except AttributeError`（仅"无 __iter__ 方法"是能力缺失信号，用户实现体内真实错误传播）
- **3.2** `scheduler.py:324`：`"Security Error" in str(e)` 字符串嗅探 → `ModuleResolveError` 加结构化 `code` 字段，resolver 传 `DEP_SECURITY_ERROR`，scheduler 用 `getattr(e, 'code')` 分派
- **3.3** `runtime_context.py:304`：`SymbolViewImpl.has` try/except 探测 → `is not None`（get_symbol 返回 None 不抛）

## 组 5：静默兜底掩盖错误 ✅ 完成 7/9

- **5.1** `_shared.py:306`：吞导入失败 → fail-fast raise（与 user_functions.py 一致），消除"module 名已切、scope 未切"的错误上下文执行
- **5.2** `_shared.py:684`：宽捕获降级 redefine → `get_symbol(name) is not None` 显式存在性检查，const/类型不匹配错误传播
- **5.3** `ib_class.py:131`：字段初始化失败静默置 None → fail-fast raise（interpreter.py:606 preeval 容忍保留，那是缓存优化）
- **5.4** `runtime_serializer.py:55/68/247`：与组 4 序列化问题交织，**合并处理**
- **5.5** `scheduler.py:100`：解析异常降级模块未找到 → 安全错误（DEP_SECURITY_ERROR）传播，普通未找到返回 None
- **5.6** `file_impl.py:151`：exists() 权限拒绝降级不存在 → 只捕获 OSError/ValueError，InterpreterError（权限）传播
- **5.7** `artifact_loader.py:91`：ValueError 语义不精确（父未注册→重试 vs 类已存在→忽略 vs spec 损坏），实为重试链非静默吞——**低优先设计注意点**
- **5.8** `config.py:42`：损坏 JSON 静默空 → JSONDecodeError 抛 ValueError（fail-fast），OSError 容忍；更新测试断言
- **5.9** `base_pass.py:54`：safe_run 编程错误转诊断 → re-raise（fail-fast 暴露 pass bug），带 traceback

## 验证
- 全量 pytest：1265 passed / 4 skipped
