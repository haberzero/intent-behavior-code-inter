//! IBC-Inter 示例 Rust 插件（架构 v2 R6 ④层）。
//!
//! 演示外部 Rust 如何写插件：依赖 `ibci-sdk`，实现纯函数（数据进 → 数据出），
//! `register_plugin!` 宏生成 C-ABI 入口；内核 `plugins.load` 加载后，IBCI 侧
//! `plugins.call("sum", [...])` 调用。

use ibci_sdk::{register_plugin, PluginValue};

/// sum(list) -> Int：求和（数值元素；非数值 = 跳过保守）。
extern "C" fn sum(args: *const PluginValue, n: usize, out: *mut PluginValue) -> i32 {
    // SAFETY: 内核保证 args/out 有效
    let args = unsafe { std::slice::from_raw_parts(args, n) };
    let mut total: i64 = 0;
    let mut any = false;
    for a in args {
        match a {
            PluginValue::Int(v) => {
                total += *v;
                any = true;
            }
            PluginValue::Float(v) => {
                // 整数面演示：浮点 → 截断求和
                total += *v as i64;
                any = true;
            }
            _ => {}
        }
    }
    let result = if any { PluginValue::Int(total) } else { PluginValue::None_ };
    // SAFETY: out 由内核提供（结果槽）
    unsafe { std::ptr::write(out, result) };
    0
}

/// mul(a, b) -> Int：整数乘法。
extern "C" fn mul(args: *const PluginValue, n: usize, out: *mut PluginValue) -> i32 {
    // SAFETY: 同上
    let args = unsafe { std::slice::from_raw_parts(args, n) };
    let a = args.first().and_then(|v| v.as_int()).unwrap_or(0);
    let b = args.get(1).and_then(|v| v.as_int()).unwrap_or(0);
    // SAFETY: out 由内核提供
    unsafe { std::ptr::write(out, PluginValue::Int(a * b)) };
    0
}

register_plugin! {
    "sum" => sum,
    "mul" => mul,
}
