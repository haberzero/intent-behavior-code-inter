//! Rust 插件加载（架构 v2 R6 ④层）：外部 Rust 插件 = cdylib（依赖 ibci-sdk），
//! 经 libloading 加载 + 调用 `ibci_plugin_register`（C-ABI）注册纯函数。
//!
//! 注册表 = 进程级（插件库 = 进程级资源，如 dlopen 原生模块）；`Arc<Library>`
//! 保持库存活（函数指针有效期内库不可卸载）。插件函数 = 纯函数面（数据进 →
//! 数据出），不触碰内核内部/Python/GIL（内核 GIL-free 执行不受影响）。

use std::collections::HashMap;
use std::sync::{Arc, LazyLock, Mutex};

use libloading::Library;

use ibci_sdk::{PluginApi, PluginFunc, PluginValue};

/// 已加载插件函数注册表（进程级——name → (函数, 库句柄[保活])）。
static REGISTRY: LazyLock<Mutex<HashMap<String, (PluginFunc, Arc<Library>)>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

extern "C" fn register_function_cb(
    name: *const u8,
    name_len: usize,
    func: PluginFunc,
    _ctx: *mut std::ffi::c_void,
) -> i32 {
    if name.is_null() {
        return -1;
    }
    // SAFETY: 插件传入 name（调用期有效）
    let name = unsafe { std::slice::from_raw_parts(name, name_len) };
    let name = match std::str::from_utf8(name) {
        Ok(s) => s.to_string(),
        Err(_) => return -2,
    };
    // 库保活：注册时从当前加载栈取最近句柄（load 内 push——见 load）
    if let Some(lib) = CURRENT_LIB.with(|c| c.borrow().clone()) {
        REGISTRY.lock().unwrap().insert(name, (func, lib));
        0
    } else {
        -3
    }
}

extern "C" fn log_cb(level: i32, msg: *const u8, len: usize) {
    if msg.is_null() {
        return;
    }
    // SAFETY: 插件传入 msg（调用期有效）
    let msg = unsafe { std::slice::from_raw_parts(msg, len) };
    if let Ok(s) = std::str::from_utf8(msg) {
        eprintln!("[ibci-plugin] (level {level}) {s}");
    }
}

/// 当前加载中的库句柄（thread_local——register_function_cb 取最近加载的库保活）。
thread_local! {
    static CURRENT_LIB: std::cell::RefCell<Option<Arc<Library>>> =
        const { std::cell::RefCell::new(None) };
}

/// 加载插件 cdylib（调用其注册入口，函数入注册表）。返回注册函数数。
pub fn load(path: &str) -> Result<usize, String> {
    // SAFETY: libloading 加载外部库——插件须为可信构建产物（用户显式加载）
    let lib = Arc::new(
        // SAFETY: 外部库加载——插件须为可信构建产物（用户显式 load 加载）
        unsafe { Library::new(path) }
            .map_err(|e| format!("插件加载失败（{path}）: {e}"))?,
    );
    // SAFETY: 查找 C-ABI 注册符号
    let entry: libloading::Symbol<unsafe extern "C" fn(*const PluginApi, *mut std::ffi::c_void) -> i32> =
        unsafe {
            lib.get(b"ibci_plugin_register")
                .map_err(|e| format!("插件无 ibci_plugin_register 入口: {e}"))?
        };
    let api = PluginApi {
        register_function: register_function_cb,
        log: log_cb,
    };
    let before = REGISTRY.lock().unwrap().len();
    // 注册期：CURRENT_LIB = 本库（回调保活）
    let rc = CURRENT_LIB.with(|c| {
        *c.borrow_mut() = Some(lib.clone());
        // SAFETY: entry 有效（库存活）；api 在调用期有效
        let rc = unsafe { entry(&api, std::ptr::null_mut()) };
        *c.borrow_mut() = None;
        rc
    });
    if rc != 0 {
        return Err(format!("插件注册失败（rc={rc}）"));
    }
    Ok(REGISTRY.lock().unwrap().len() - before)
}

/// 调用已注册插件函数（实参 = PluginValue 借用切片；结果写 out）。
pub fn call(name: &str, args: &[PluginValue]) -> Result<PluginValue, String> {
    let (func, lib) = REGISTRY
        .lock()
        .unwrap()
        .get(name)
        .cloned()
        .ok_or_else(|| format!("插件函数未注册: {name}"))?;
    // SAFETY: lib 保活（Arc 副本——调用期内库不卸载）；args 借用调用期有效
    let _keep_alive = lib;
    let mut out = PluginValue::None_;
    let rc = unsafe { func(args.as_ptr(), args.len(), &mut out) };
    if rc != 0 {
        return Err(format!("插件函数执行失败（rc={rc}）: {name}"));
    }
    Ok(out)
}
