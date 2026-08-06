# _code_debt7 — PT-DEBT-7 删除 is_nullable 字段

> 临时任务文档（Phase 5 汇报后删除）。

## 根因

`TypeDef.is_nullable` 是死字段：可空性判断由 `Optional[T].wrapped_type` 承载
（`core/kernel/spec/registry/_assignability.py` L47-52），`is_assignable` 不读 `is_nullable`。
唯一读取点是 `serializer.py:162` 序列化写出，而反序列化（`artifact_rehydrator.py`）重建 spec
时不读该字段。属演进残留死字段。

## 破坏面（已核实）

- `core/kernel/spec/base.py:94`：字段定义（删除）
- `core/kernel/spec/specs.py`：~45 处构造参数（删除）
- `core/kernel/spec/registry/factory.py`：~16 处构造参数 + `create_primitive(name, is_nullable)` 签名（删除）
- `core/compiler/serialization/serializer.py:162`：序列化写出（删除）
- `tests/compiler/test_type_annotations.py`：8 处序列化断言（删除字段）
- `docs/architecture/03_type_system.md`：L81 字段表、L163 factory 签名（删除）
- 无运行时读取 → 无兼容性/序列化格式兼容问题（反序列化不消费该字段）

## 方案

纯字段删除（死代码清理），不做机制迁移——Optional[T] 机制已存在且是唯一可空性载体。

## 修改单元

1. base.py 删字段
2. specs.py 删全部构造参数
3. factory.py 删参数 + create_primitive 签名
4. serializer.py 删写出
5. test_type_annotations.py 删断言
6. 03_type_system.md 删描述
7. 全量 pytest
