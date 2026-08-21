# DESIGN — T14 fs 模块 + Optional/容器 + 值语义（五大地基新特性试用地基）

> **目标**：对五大地基重构后 **fs 模块**（原 file→fs 迁移后全部接口 + 只读语义 + 沙箱限制）、
> **Optional[T] 值模型**、**值语义**（复合别名 vs 原语拷贝）全面试用。全部 mock/无 LLM 依赖。
> 参考规范：`_toolkit/CLASSIFICATION.md` / `_toolkit/CONTRACT_FORMAT.md`。

## 覆盖矩阵（mock 层已建）

| 维度 | 覆盖特性 | 语法章节 | 用例组 | 覆盖状态 |
|------|----------|----------|--------|----------|
| FS-M1 | fs.write(overwrite) + open + read（handle/path 双入口）+ remove | 11 §11.7 | FS-M1 | ✅ PASS |
| FS-M2 | write(new) 副本 vs write(overwrite) 就地覆盖共享 backing | 11 §11.7 | FS-M2 | ✅ PASS |
| FS-M3 | fs.exists / fs.remove 生命周期 | 11 §11.7 | FS-M3 | ✅ PASS |
| FS-M4 | file_handle.read_bytes 字节读取 | 11 §11.7 | FS-M4 | ✅ PASS |
| FS-G1 | file_handle 只读语义（无 write 方法，捕获确认） | 11 §11.7 | FS-G1 | ✅ PASS |
| FS-M5 | 沙箱限制：越出 project_root 的写入被拒（RUN_PERMISSION_ERROR） | 11 §11.7 + KNOWN_LIMITS §11.7 | FS-M5 | ✅ GUARD |
| OPT-M1 | Optional[T] 值模型（is_some/unwrap/or_else/None 接受） | 01 §1.3.1 | OPT-M1 | ✅ PASS |
| OPT-M2 | Optional 容器元素（Optional[list[int]]） | 01 §1.3.1 | OPT-M2 | ✅ PASS |
| VS-M1 | 值语义：复合对象赋值别名 vs 不可变原语赋值复制 | 02 §2.8 | VS-M1 | ✅ PASS |

> 注：fs 相对路径从 `cases/` 解析，`../` 仅回到套件根（= project_root）不越界；沙箱越界
> 用例必须用 `../../`（真到 project_root 之外）或绝对路径——FS-M5 用 `../../` 实测
> `RUN_PERMISSION_ERROR` 守卫生效，**沙箱无漏洞**。

## 硬约束

- 每用例 `--timeout` 必填（run_batch 默认 60s，OS 级 SIGKILL 死循环保护）。
- 用例写文件用唯一文件名 + 用例内 fs.remove 清理（套件目录共享，避免跨用例污染）。
- 用例头部断言必填；注释只保留功能说明 + `# doc:` 引用。

## 分类与记录

- 分类规范：PASS / GUARD / KERNEL_ISSUE / BOUNDARY / DOC_ISSUE / LLM_BEHAVIOR / LIMIT / HARNESS。
- 缺陷登记：`trials/INDEX.md` 生命周期状态机 + REGISTER.md。
- 只记录不修复优先；不为规避缺陷改套件。
