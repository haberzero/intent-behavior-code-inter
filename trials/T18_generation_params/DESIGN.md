# T18 · 生成参数面与采样姿态审计试用套件

## 范围

生成参数面（N1 思考模型支持 + N4 finish_reason 暴露）的语言面行为基线：
标准生成参数（temperature/top_p/top_k/seed）+ extra_body vendor 透传口子 +
配置未知字段严格性 + call_info 采样姿态审计闭环（finish_reason/generation）。

## 用例矩阵

| 用例 | 面 | LLM |
|------|-----|-----|
| T18-G-L1 | 真实 call_info 审计（finish_reason + generation 采样姿态） | 是 |
| T18-G-L2 | 命名模型变体参数（register_model temperature/seed + @NAME~ 路由） | 是 |
| T18-G-M1 | 配置未知字段 fail-fast（CFG_CONFIG_UNKNOWN_FIELD——静默丢弃不再允许） | 否 |
| T18-G-M2 | 运行时参数范围 fail-fast（temperature 越界 RUN_TYPE_MISMATCH） | 否 |
| T18-G-M3 | 语言面未知参数编译期拦截（SEM_UNKNOWN_KEYWORD——不静默吞参） | 否 |

## 断言纪律

- 真实用例（L1/L2）断言审计性质（finish_reason 非空 = 标准结束原因值；
  generation 含声明的 max_tokens/temperature 有效值），不断言 LLM 输出内容
  （相对测量纪律）；
- call_info 观测契约：**变量读点（触发 resolve）之后**读取（eager dispatch
  的 dispatch 时刻快照仅含请求面；resolve 点补全 response/finish_reason/
  generation）；
- mock 面用例（M1-M3）确定性（配置校验/编译检查/运行时 fail-fast——零 LLM）。
