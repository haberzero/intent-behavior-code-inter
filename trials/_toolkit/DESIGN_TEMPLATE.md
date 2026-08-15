# DESIGN — <试用名>

> 生成方式：复制本模板，替换占位符。规范见 `_toolkit/CLASSIFICATION.md`。
> 日期：<YYYY-MM-DD> ｜ 主题：<一句话目标>

## 一、目标

<本试用地基要验证/检测什么。例如：真实 LLM 全语法遍历 / 泛型修复回归 / 某特性压力试用>

## 二、检测矩阵（维度 → 用例组）

| 维度 | 覆盖内容 | 用例组 |
|------|----------|--------|
| D1 | <基础语义> | <cases 前缀，如 D1-*> |
| D2 | <交叉/正交压力> | D2-* |
| D3 | <批判/恶意挑刺> | D3-* |

> 交叉：特性×特性；正交：独立维度组合；多层次：嵌套/递归；多可能性：边界值/遮蔽；
> 多文件：import/插件/隔离。具体维度按主题裁剪，不必全用。

## 三、硬约束（用户强制）

1. **死循环保护**：所有用例经 `_toolkit/run_one.py`（进程组 SIGKILL +
   LLM 调用超时），`--timeout` 必填，零遗漏。
2. 记录优先（record-first）：`logs/<case>.log` + `logs/register.jsonl` 机械字段由
   harness 写入，人工填 classification/severity/note。
3. 技术手册为主要信息来源；非必要不读内核代码。手册问题记为 `DOC_ISSUE`。

## 四、分类与级别

见 `_toolkit/CLASSIFICATION.md`。登记前分诊闸门强制：非 PASS 先对照
KNOWN_LIMITS/docs，命中限制 ≠ 免罪（进待修候选池）。

## 五、产出

- `logs/` + `register.jsonl`
- `REGISTER.md`（模板：`_toolkit/REGISTER_TEMPLATE.md`）
- 缺陷登记同步 PENDING_TASKS（编号规范见 CLASSIFICATION §三）
