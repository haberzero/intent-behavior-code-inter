//! IBC-Inter 插件 SDK（架构 v2 R6 ④层——回答"外部人员书写 Rust"）。
//!
//! 外部 Rust 插件 = 独立 crate（依赖本 SDK）编译为 **cdylib**，导出
//! `ibci_plugin_register` 入口；内核经 libloading 加载、调用注册（C-ABI——
//! 与编译器/版本解耦），插件函数注册进内核插件注册表，IBCI 侧经 `plugins`
//! 宿主模块调用。
//!
//! **值模型（C-ABI）**：`PluginValue`（repr(C)）——插件函数接收**借用**实参
//! 切片、写出**自有标量**结果（Int/Float/Bool/None 无分配；Str/List 结果 =
//! 后续增量[所有权纪律]）。内核构造实参、持有生命周期；插件只读不持有。
//!
//! **职责边界**：插件 = 纯函数面（数据进 → 数据出）；不触碰内核内部、不触
//! 碰 Python/GIL（内核 GIL-free 执行不受影响）。

use std::ffi::c_void;

/// 插件值（repr(C) C-ABI——跨动态库边界稳定布局）。
///
/// 实参 = 借用（内核构造，插件调用期内有效）；结果 = 自有标量（插件写
/// `out`；Str/List 结果 = 后续增量——所有权/分配器纪律未定前不开放）。
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub enum PluginValue {
    None_,
    Bool(bool),
    Int(i64),
    Float(f64),
    /// 借用字节串（len 界定，不要求 NUL 结尾）。
    Str(*const u8, usize),
    /// 借用值切片（元素 = PluginValue）。
    List(*const PluginValue, usize),
}

impl PluginValue {
    /// 安全读取借用 Str（越界 = None——防 UB 的最小守卫）。
    pub fn as_str(&self) -> Option<&str> {
        match self {
            PluginValue::Str(ptr, len) if !ptr.is_null() => {
                // SAFETY: 内核构造时保证 ptr+len 在实参生命周期内有效
                unsafe { std::str::from_utf8(std::slice::from_raw_parts(*ptr, *len)).ok() }
            }
            _ => None,
        }
    }

    /// 安全读取借用 List 元素（越界 = None）。
    pub fn as_list(&self) -> Option<&[PluginValue]> {
        match self {
            PluginValue::List(ptr, len) if !ptr.is_null() => {
                // SAFETY: 同上——内核保证有效
                Some(unsafe { std::slice::from_raw_parts(*ptr, *len) })
            }
            _ => None,
        }
    }

    pub fn as_int(&self) -> Option<i64> {
        match self {
            PluginValue::Int(v) => Some(*v),
            _ => None,
        }
    }

    pub fn as_float(&self) -> Option<f64> {
        match self {
            PluginValue::Float(v) => Some(*v),
            _ => None,
        }
    }

    pub fn as_bool(&self) -> Option<bool> {
        match self {
            PluginValue::Bool(v) => Some(*v),
            _ => None,
        }
    }
}

/// 插件函数签名（C-ABI）：实参借用切片 + 结果写出（`out`）。
pub type PluginFunc = extern "C" fn(
    args: *const PluginValue,
    n: usize,
    out: *mut PluginValue,
) -> i32;

/// 内核回调 API（repr(C)——插件经此注册函数/日志）。
#[repr(C)]
pub struct PluginApi {
    pub register_function: extern "C" fn(
        name: *const u8,
        name_len: usize,
        func: PluginFunc,
        ctx: *mut c_void,
    ) -> i32,
    pub log: extern "C" fn(level: i32, msg: *const u8, len: usize),
}

/// 插件注册入口（内核经 libloading 查找此符号并调用）。
///
/// 插件实现经 `ibci_sdk::register_plugin!` 宏生成（默认实现 = 遍历宏注册表）。
#[no_mangle]
pub extern "C" fn ibci_plugin_register(_api: *const PluginApi, _ctx: *mut c_void) -> i32 {
    // 默认无注册（宏重写此函数体——见 register_plugin!）
    0
}

/// 插件注册表（宏展开用——static 注册表，入口遍历注册）。
pub struct Registry {
    pub entries: &'static [(&'static str, PluginFunc)],
}

/// 注册插件宏：`register_plugin! { "sum" => sum_fn, "mul" => mul_fn }`。
///
/// 生成 `ibci_plugin_register` 入口：遍历注册表，经内核 `PluginApi.register_
/// function` 注册每个函数。
#[macro_export]
macro_rules! register_plugin {
    ($($name:literal => $func:ident),* $(,)?) => {
        pub static PLUGIN_ENTRIES: &[(&str, $crate::PluginFunc)] = &[
            $(($name, $func),)*
        ];

        #[no_mangle]
        pub extern "C" fn ibci_plugin_register(api: *const $crate::PluginApi, ctx: *mut std::ffi::c_void) -> i32 {
            if api.is_null() {
                return -1;
            }
            // SAFETY: 内核传入有效 PluginApi（调用期内存活）
            let api = unsafe { &*api };
            for (name, func) in PLUGIN_ENTRIES {
                let rc = (api.register_function)(name.as_ptr(), name.len(), *func, ctx);
                if rc != 0 {
                    return rc;
                }
            }
            0
        }
    };
}
