---
name: grilling
description: Interview the user relentlessly about a plan or design. Use when the user wants to stress-test a plan before building, or uses any 'grill' trigger phrases (拷问, 质询我, grill me, 帮我审计划, 反复质疑). One question at a time; walk down each branch of the design tree; explore the codebase for any answerable question; provide a recommended answer with each question.
---

# 拷问（Grilling）

> 对用户的计划或设计持续拷问，直到双方达成共享理解。逐条走设计树的分支，逐个化解决策之间的依赖；每个问题只问一个、给出推荐答案、等用户回应后再继续。

## 执行方式

1. **一次一个问题**：逐个问，等用户反馈再继续。一次抛多个问题只会让人无所适从。
2. **逐分支走设计树**：沿决策依赖顺序推进——先解决被依赖的决策，再解决依赖它的决策。
3. **能查代码就先查**：任何能被代码库、文档或测试回答的问题，先探索代码库回答，不浪费用户的时间。
4. **每个问题附推荐答案**：给出我的推荐与理由，降低用户的决策成本；用户只需确认或推翻。

## 触发

- 用户要求对计划/设计进行压力测试；
- 用户使用任何 'grill' 类触发词（拷问、质询我、grill me、反复质疑、帮我把计划审一遍）。

## 与内向版本的对应

- `self-grill`：本 skill 的内向化——把拷问从"我对用户"转为"我对自己"，仅将无法自主决断的项反馈用户。
- `code-odor`：异味特征定位（质量红旗），不替代本 skill 的完整设计拷问。
- 用户明确要"被拷问"时用本 skill；用户要我"自主推进、少打扰"时，用 `self-grill` 自行消化、仅上报待决断项。
