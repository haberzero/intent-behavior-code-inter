//! ibci-ext Rust 执行核心——反序列化 AST → 执行 → 数据面（print 输出）。
//!
//! 移植范围（本增量）：非 KB 语料面执行——
//!   语句：Assign[Name/Subscript target] / ExprStmt / If[elif 链] / For / While /
//!         FunctionDef / Return / Break / Continue / Pass
//!   表达式：Constant / Name / BinOp[+ - * / // % **] / UnaryOp / Compare / Call /
//!           List / Dict / Attribute[方法] / Subscript / IfExp
//!   内建：print / len / range；方法：list.append / str 方法（upper 等）
//! 对象模型（IbValue）：Int / Float / Str / Bool / None / List / Dict——
//!   List/Dict 经 Rc<RefCell>（共享可变——append/dict 下标赋值原地修改，clean
//!   Rust 方式，避免 tricky 特判）。数据面 repr 对齐 Python print（float 整数值 =
//!   `4.0`；list `[e, e]`；dict `{"k": v}`；str 原样）。KB 语料面（knowledge()）
//!   = Rust 原生 KB 值（kb::KbState——治理词表 + 事实日志 + active 索引，去
//!   Host 化）。quoted/meta 函数面 = 原生（Quoted/MetaFn 变体 + call_meta_fn）。
//!
//! 差分门：数据面（Rust 执行 print 输出）== Python 执行 print 输出（全语料
//! 无桥接——宿主桥接仅余 LLM/意图 IO 边界）。

use crate::kb::KbState;
use crate::parser::{ConstVal, Expr, Module, Stmt};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};
use std::cell::RefCell;
use std::collections::HashMap;
use std::rc::Rc;

// --------------------------------------------------------------------------- //
// 对象模型（IbValue——IBC 运行时值；List/Dict 共享可变；Host = Python 宿主对象）
// --------------------------------------------------------------------------- //
pub enum IbValue {
    Int(i64),
    Float(f64),
    Str(String),
    Bool(bool),
    None_,
    List(Rc<RefCell<Vec<IbValue>>>),
    Dict(Rc<RefCell<Vec<(IbValue, IbValue)>>>),
    /// quoted 值（meta.quote 冻结的表达式源串——不可变，逐字节精确对比；
    /// 字段 source = 完整源串，经 q.source 属性访问）。
    Quoted { source: String },
    /// 原生 meta 函数引用（from meta import quote/eval 的绑定值——去 Host 化；
    /// 调用经 call_meta_fn 原生分发）。
    MetaFn(&'static str),
    /// Rust 原生 KB 值（knowledge() 返回——世界模型知识图谱执行面；治理词表 +
    /// append-only 事实日志 + active 索引，方法经 kb::dispatch 原生分发）。
    Knowledge(Rc<RefCell<KbState>>),
    /// vector 值（词嵌入向量——不可变 float 元素面；值语义相等；显示面 =
    /// 截断摘要 vector[<dim>](前 8 维 %.6g, ...)——同 __to_prompt__）。
    Vector(Vec<f64>),
    /// 宿主对象（Python 对象引用——host service 桥接委托面）。
    /// 函数值（一等值——值域可赋值/别名/传参；Rc 共享 = 同一函数对象身份；
    /// 显示面 = source 形态 `func <name>(<param types>) -> <ret>`）。
    Function(Rc<Function>),
    Host(Py<PyAny>),
    /// 异常对象值（Exception/LLMError/ThreadError 家族实例——class + message；
    /// 显示面 = `<class>: <message>`[无 message = 仅类名]）。
    Error { class: String, message: String },
}

/// 手动 Clone（Py<PyAny> 不实现 Clone——经 clone_ref 增引用）。
impl Clone for IbValue {
    fn clone(&self) -> Self {
        match self {
            IbValue::Int(i) => IbValue::Int(*i),
            IbValue::Float(f) => IbValue::Float(*f),
            IbValue::Str(s) => IbValue::Str(s.clone()),
            IbValue::Bool(b) => IbValue::Bool(*b),
            IbValue::None_ => IbValue::None_,
            IbValue::List(l) => IbValue::List(l.clone()),
            IbValue::Dict(d) => IbValue::Dict(d.clone()),
            IbValue::Quoted { source } => IbValue::Quoted {
                source: source.clone(),
            },
            IbValue::MetaFn(n) => IbValue::MetaFn(*n),
            // 共享可变容器（同 List/Dict——Rc clone = 共享引用）
            IbValue::Knowledge(k) => IbValue::Knowledge(k.clone()),
            IbValue::Vector(v) => IbValue::Vector(v.clone()),
            // 函数值 = Rc 共享（同一函数对象）
            IbValue::Function(f) => IbValue::Function(f.clone()),
            IbValue::Error { class, message } => IbValue::Error {
                class: class.clone(),
                message: message.clone(),
            },
            IbValue::Host(h) => {
                // clone_ref 需 GIL（执行期 GIL 已持有，with_gil 可重入）
                let cloned = Python::with_gil(|py| h.clone_ref(py));
                IbValue::Host(cloned)
            }
        }
    }
}

impl std::fmt::Debug for IbValue {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            IbValue::Int(i) => write!(f, "Int({i})"),
            IbValue::Float(v) => write!(f, "Float({v})"),
            IbValue::Str(s) => write!(f, "Str({s:?})"),
            IbValue::Bool(b) => write!(f, "Bool({b})"),
            IbValue::None_ => write!(f, "None_"),
            IbValue::Quoted { source } => write!(f, "Quoted({source:?})"),
            IbValue::MetaFn(n) => write!(f, "MetaFn({n:?})"),
            IbValue::Knowledge(_) => write!(f, "Knowledge(..)"),
            IbValue::Vector(v) => write!(f, "Vector({v:?})"),
            IbValue::Function(fn_val) => write!(f, "Function({})", fn_val.name),
            IbValue::Error { class, .. } => write!(f, "Error({class})"),
            IbValue::List(_) => write!(f, "List(..)"),
            IbValue::Dict(_) => write!(f, "Dict(..)"),
            IbValue::Host(_) => write!(f, "Host(<py object>)"),
        }
    }
}

/// 逻辑值相等（dict 键查找/比较；非 Rc 身份）。
impl PartialEq for IbValue {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (IbValue::Int(a), IbValue::Int(b)) => a == b,
            (IbValue::Float(a), IbValue::Float(b)) => a == b,
            (IbValue::Int(a), IbValue::Float(b)) => (*a as f64) == *b,
            (IbValue::Float(a), IbValue::Int(b)) => *a == (*b as f64),
            (IbValue::Str(a), IbValue::Str(b)) => a == b,
            (IbValue::Bool(a), IbValue::Bool(b)) => a == b,
            (IbValue::None_, IbValue::None_) => true,
            (IbValue::List(a), IbValue::List(b)) => {
                let (av, bv) = (a.borrow(), b.borrow());
                av.len() == bv.len() && av.iter().zip(bv.iter()).all(|(x, y)| x == y)
            }
            (IbValue::Dict(a), IbValue::Dict(b)) => {
                let (av, bv) = (a.borrow(), b.borrow());
                av.len() == bv.len() && av.iter().zip(bv.iter()).all(|((k1, v1), (k2, v2))| {
                    k1 == k2 && v1 == v2
                })
            }
            // quoted 值相等 = 源串逐字节精确对比（公理：可精确对比逐字节）
            (IbValue::Quoted { source: a }, IbValue::Quoted { source: b }) => a == b,
            // KB 对象相等 = 身份（共享引用——同宿主对象身份语义）
            (IbValue::Knowledge(a), IbValue::Knowledge(b)) => Rc::ptr_eq(a, b),
            // vector 相等 = 元素逐位值语义（公理：payload 元组相等）
            (IbValue::Vector(a), IbValue::Vector(b)) => a == b,
            // 函数值相等 = 对象身份（Rc 共享——同一函数定义）
            (IbValue::Function(a), IbValue::Function(b)) => Rc::ptr_eq(a, b),
            // 异常对象相等 = 值语义（class + message）
            (IbValue::Error { class: a, message: ma }, IbValue::Error { class: b, message: mb }) => {
                a == b && ma == mb
            }
            (IbValue::Host(a), IbValue::Host(b)) => {
                // 宿主对象身份相等（同一 Python 对象指针）
                a.as_ptr() == b.as_ptr()
            }
            _ => false,
        }
    }
}

impl IbValue {
    pub fn list_new(items: Vec<IbValue>) -> IbValue {
        IbValue::List(Rc::new(RefCell::new(items)))
    }
    pub fn dict_new(pairs: Vec<(IbValue, IbValue)>) -> IbValue {
        IbValue::Dict(Rc::new(RefCell::new(pairs)))
    }
    /// 数据面 repr（对齐 Python print 的值表示）。
    pub fn repr(&self) -> String {
        match self {
            IbValue::Int(i) => i.to_string(),
            IbValue::Float(f) => {
                let fv = *f;
                if fv.fract() == 0.0 {
                    format!("{}.0", fv as i64)
                } else {
                    format!("{}", fv)
                }
            }
            IbValue::Str(s) => s.clone(),
            IbValue::Bool(b) => if *b { "True".into() } else { "False".into() },
            IbValue::None_ => "None".into(),
            IbValue::List(l) => {
                let items: Vec<String> = l.borrow().iter().map(|v| v.repr()).collect();
                format!("[{}]", items.join(", "))
            }
            IbValue::Dict(d) => {
                let items: Vec<String> = d
                    .borrow()
                    .iter()
                    .map(|(k, v)| format!("{}: {}", dict_key_repr(k), v.repr()))
                    .collect();
                format!("{{{}}}", items.join(", "))
            }
            // 数据面忠实呈现 = 完整源串（同 __to_prompt__——无截断）
            IbValue::Quoted { source } => source.clone(),
            IbValue::MetaFn(n) => format!("meta.{n}"),
            IbValue::Knowledge(_) => "<knowledge>".into(),
            // vector 显示面 = 截断摘要（dim + 前 8 维 %.6g——同 __to_prompt__；
            // 全量维度进提示词 = 污染风险，截断即纪律）
            IbValue::Vector(v) => vector_repr(v),
            // 函数值显示面 = source 形态（Python 实证：func f(int) -> str——
            // 参数面仅类型名不含参数名；无返回类型 = 省略 -> 段）
            IbValue::Function(f) => {
                let mut s = format!("func {}({})", f.name, f.param_types.join(", "));
                if let Some(r) = &f.ret {
                    s.push_str(&format!(" -> {r}"));
                }
                s
            }
            // 异常对象显示面 = `<class>: <message>`（无 message = 仅类名——
            // Python IbException.__to_prompt__ 契约）
            IbValue::Error { class, message } => {
                if message.is_empty() {
                    class.clone()
                } else {
                    format!("{class}: {message}")
                }
            }
            IbValue::Host(_) => "<host>".into(),
        }
    }
    fn truthy(&self) -> bool {
        match self {
            IbValue::Bool(b) => *b,
            IbValue::None_ => false,
            IbValue::Int(i) => *i != 0,
            IbValue::Float(f) => *f != 0.0,
            IbValue::Str(s) => !s.is_empty(),
            IbValue::List(l) => !l.borrow().is_empty(),
            IbValue::Dict(d) => !d.borrow().is_empty(),
            IbValue::Quoted { .. } => true,
            IbValue::MetaFn(_) => true,
            IbValue::Knowledge(_) => true,
            IbValue::Vector(v) => !v.is_empty(),
            IbValue::Function(_) => true,
            IbValue::Error { .. } => true,
            IbValue::Host(_) => true,
        }
    }
    fn as_num(&self) -> Option<(f64, bool)> {
        match self {
            IbValue::Int(i) => Some((*i as f64, true)),
            IbValue::Float(f) => Some((*f, false)),
            // bool 参与整数算术按 0/1 数值（Python 契约：True + 1 = 2；
            // int 形态——bool 是 int 的子类）
            IbValue::Bool(b) => Some((if *b { 1.0 } else { 0.0 }, true)),
            _ => None,
        }
    }
}

/// 异常类名集合（可构造异常对象的 intrinsic 类——CLASS_PARENTS 异常家族 +
/// Exception 基类）。
fn is_exception_class(name: &str) -> bool {
    matches!(
        name,
        "Exception"
            | "LLMError"
            | "LLMCallError"
            | "LLMParseError"
            | "LLMRetryExhaustedError"
            | "ThreadError"
            | "ThreadCancelled"
            | "ThreadFailed"
    )
}

/// 值 → JSON（状态导出面：原生数据值 = 原生 JSON 形态[int/float/str/
/// bool/null/list/dict]；非数据值[Function/MetaFn/Knowledge/Quoted/Error/
/// Vector/Host] = 显示形态字符串[repr 契约]——数据面源最终状态无 Host
/// 值；初始 Host 残差值回导 = "<host>" 标记字符串）。
pub(crate) fn ibvalue_to_json(v: &IbValue) -> serde_json::Value {
    match v {
        IbValue::Int(i) => serde_json::Value::Number(serde_json::Number::from(*i)),
        IbValue::Float(f) => serde_json::Number::from_f64(*f)
            .map(serde_json::Value::Number)
            .unwrap_or(serde_json::Value::Null),
        IbValue::Str(s) => serde_json::Value::String(s.clone()),
        IbValue::Bool(b) => serde_json::Value::Bool(*b),
        IbValue::None_ => serde_json::Value::Null,
        IbValue::List(items) => {
            let arr: Vec<serde_json::Value> =
                items.borrow().iter().map(ibvalue_to_json).collect();
            serde_json::Value::Array(arr)
        }
        IbValue::Dict(pairs) => {
            let mut obj = serde_json::Map::new();
            for (k, val) in pairs.borrow().iter() {
                // JSON 对象键 = 字符串：str 键原生，其余键 = 显示形态
                let key = match k {
                    IbValue::Str(s) => s.clone(),
                    other => other.repr(),
                };
                obj.insert(key, ibvalue_to_json(val));
            }
            serde_json::Value::Object(obj)
        }
        IbValue::Vector(v) => {
            let arr: Vec<serde_json::Value> = v
                .iter()
                .map(|f| {
                    serde_json::Number::from_f64(*f)
                        .map(serde_json::Value::Number)
                        .unwrap_or(serde_json::Value::Null)
                })
                .collect();
            serde_json::Value::Array(arr)
        }
        // 非数据值 = 显示形态（repr 契约）
        other => serde_json::Value::String(other.repr()),
    }
}

/// 赋值语义（nonlocal 重定向：nonlocal 名 = 最近外层作用域改写[含该名的
/// 最近 env，或该 env 亦非 nonlocal 持有者——Python nonlocal 契约]；普通名
/// = 本地遮蔽）。
fn assign_env(
    env: &Rc<RefCell<Environment>>,
    name: &str,
    value: IbValue,
) {
    let b = env.borrow();
    let is_nonlocal = b.nonlocals.contains(name);
    let parent = b.parent.clone();
    drop(b);
    if is_nonlocal {
        match &parent {
            Some(p) => {
                let pb = p.borrow();
                let has = pb.vars.contains_key(name);
                let also_nl = pb.nonlocals.contains(name);
                drop(pb);
                if has || !also_nl {
                    p.borrow_mut().set(name, value);
                } else {
                    assign_env(p, name, value);
                }
            }
            None => env.borrow_mut().set(name, value),
        }
    } else {
        env.borrow_mut().set(name, value);
    }
}

/// 全局绑定（parent 链顶——异常变量语义：Python runtime_context 全局面，
/// 越 try 块可见[实证]）。
fn set_global_env(env: &Rc<RefCell<Environment>>, name: &str, value: IbValue) {
    let b = env.borrow();
    match &b.parent {
        Some(p) => set_global_env(p, name, value),
        None => {
            drop(b);
            env.borrow_mut().set(name, value);
        }
    }
}

/// 值类型名（异常匹配面：raise 值 → 类型名）。
fn value_type_name(v: &IbValue) -> &str {
    match v {
        IbValue::Int(_) => "int",
        IbValue::Float(_) => "float",
        IbValue::Str(_) => "str",
        IbValue::Bool(_) => "bool",
        IbValue::None_ => "none",
        IbValue::List(_) => "list",
        IbValue::Dict(_) => "dict",
        IbValue::Quoted { .. } => "quoted",
        IbValue::MetaFn(_) => "meta",
        IbValue::Knowledge(_) => "knowledge",
        IbValue::Vector(_) => "vector",
        IbValue::Function(_) => "function",
        IbValue::Error { class, .. } => class.as_str(),
        IbValue::Host(_) => "host",
    }
}

/// 异常可赋性（except handler 匹配：handler 类型 = 值类型名，或 handler 在值
/// 类型继承链上——CLASS_PARENTS 传递闭包；原语类型不继承 Exception[Python
/// 实证：raise 5 不被 except Exception 捕获]）。
fn exception_assignable(value: &IbValue, handler_type: &str) -> bool {
    let vt = value_type_name(value);
    if vt == handler_type {
        return true;
    }
    // 继承链：vt → parent → ...
    let mut cur = String::from(vt);
    for _ in 0..16 {
        match crate::intrinsic_symbols::class_parent(&cur) {
            Some(p) if p == handler_type => return true,
            Some(p) => cur = p,
            None => return false,
        }
    }
    false
}

/// vector 显示面 = 截断摘要（dim + 前 8 维 %.6g——同 __to_prompt__/_string_
/// repr：全量维度进提示词 = 污染风险，截断即纪律）。
fn vector_repr(v: &[f64]) -> String {
    let head: Vec<String> = v.iter().take(8).map(|x| format_g6(*x)).collect();
    let ellipsis = if v.len() > 8 { ", ..." } else { "" };
    format!("vector[{}]({}{})", v.len(), head.join(", "), ellipsis)
}

/// Python `%.6g` 等价（C %g 语义：6 位有效数字；-4 ≤ 指数 < 6 用定点 +
/// 尾零截断，否则科学计数法[e±两位指数]）——vector 显示面/摘要渲染单一
/// 权威源（截断摘要即纪律）。非有限值 = Rust Display（语料面不可达——
/// vector 构造期封死 NaN/Inf）。
fn format_g6(x: f64) -> String {
    if !x.is_finite() {
        return format!("{}", x);
    }
    if x == 0.0 {
        return "0".to_string();
    }
    let s = format!("{:.5e}", x);
    let (mant, exp_s) = s.split_once('e').unwrap();
    let exp: i32 = exp_s.parse().unwrap();
    let neg = mant.starts_with('-');
    let mant = mant.trim_start_matches('-');
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    if exp < -4 || exp >= 6 {
        // 科学计数法：d.ddddd（尾零截断） e±<两位指数>
        let (ip, fp) = digits.split_at(1);
        let fp = fp.trim_end_matches('0');
        let mant_out = if fp.is_empty() {
            ip.to_string()
        } else {
            format!("{}.{}", ip, fp)
        };
        let exp_str = if exp >= 0 {
            format!("e+{exp:02}")
        } else {
            format!("e-{:-02}", -exp)
        };
        if neg {
            format!("-{}{}", mant_out, exp_str)
        } else {
            format!("{}{}", mant_out, exp_str)
        }
    } else {
        // 定点：按指数置小数点 + 尾零截断
        let (int_part, frac_part) = if exp >= 0 {
            let n = (exp + 1) as usize;
            if n >= digits.len() {
                (digits.clone(), "0".repeat(n - digits.len()))
            } else {
                (digits[..n].to_string(), digits[n..].to_string())
            }
        } else {
            let n = (-exp) as usize;
            ("0".to_string(), format!("{}{}", "0".repeat(n - 1), digits))
        };
        let frac = frac_part.trim_end_matches('0').to_string();
        if frac.is_empty() {
            if neg {
                format!("-{}", int_part)
            } else {
                int_part
            }
        } else if neg {
            format!("-{}.{}", int_part, frac)
        } else {
            format!("{}.{}", int_part, frac)
        }
    }
}

fn dict_key_repr(k: &IbValue) -> String {
    match k {
        IbValue::Str(s) => format!("\"{}\"", s),
        other => other.repr(),
    }
}

fn num_result(a: &IbValue, b: &IbValue, f: fn(f64, f64) -> f64) -> IbValue {
    // 非数值 → None_（不静默数值默认——类型错误由语义层捕获；执行核心假设良型输入）
    match (a.as_num(), b.as_num()) {
        (Some((av, ai)), Some((bv, bi))) => {
            let r = f(av, bv);
            if ai && bi && r.fract() == 0.0 {
                IbValue::Int(r as i64)
            } else {
                IbValue::Float(r)
            }
        }
        _ => IbValue::None_,
    }
}

// --------------------------------------------------------------------------- //
// 环境（变量绑定 + 函数定义 + 作用域链）
// --------------------------------------------------------------------------- //
/// 用户函数调用深度（thread_local——Rust 原生调用栈无 Python 递归限检查；
/// 深度超限 = RecursionError 环境限制异常[Python 契约：根因原样传播，不
/// 被语义错误包装掩盖]；守卫经 RAII 深度恢复，零签名变更）。
std::thread_local! {
    static CALL_DEPTH: std::cell::Cell<u32> = std::cell::Cell::new(0);
}

/// 递归深度上限（= Python 宿主递归深度序[1000]——f(5000) 超限触发
/// RecursionError[测试契约]；正常数据面源远低于此序）。
const RECURSION_LIMIT: u32 = 1000;

struct DepthGuard(u32);
impl Drop for DepthGuard {
    fn drop(&mut self) {
        CALL_DEPTH.with(|c| c.set(self.0));
    }
}

/// 抛出的异常值（raise 传播面——Rust 解释器异常机制；try/except 捕获面）。
/// 值 = 被 raise 的任意 IbValue（IBCI 语义：raise 不做类型检查，匹配在
/// except 处理器面——类可赋性）。
#[derive(Debug, Clone)]
pub struct Thrown {
    pub value: IbValue,
    /// 错误现场位置（源 line/col——engine 边界构造诊断位置；
    /// 表达式级错误[类型/下标/递归]携带其表达式 pos）
    pub pos: Option<(i64, i64)>,
}

/// 运行时环境错误（Python 内建异常类名契约——engine 边界映射诊断码：
/// ZeroDivisionError→RUN_DIVISION_BY_ZERO / IndexError|KeyError→
/// RUN_INDEX_ERROR / AttributeError→RUN_ATTRIBUTE_ERROR）。
fn runtime_error(class: &str, message: &str) -> Thrown {
    Thrown {
        value: IbValue::Error {
            class: class.to_string(),
            message: message.to_string(),
        },
        pos: None,
    }
}

pub struct Environment {
    vars: HashMap<String, IbValue>,
    functions: HashMap<String, Function>,
    parent: Option<Rc<RefCell<Environment>>>,
    /// nonlocal 绑定名（闭包语义：非局部名赋值 = 最近外层作用域改写，
    /// 非本地遮蔽——Python nonlocal 契约）。
    nonlocals: std::collections::BTreeSet<String>,
}

/// 函数（含闭包捕获的 enclosing 环境——嵌套函数可访问 outer 局部变量）。
pub struct Function {
    pub name: String,
    pub params: Vec<String>,
    /// 参数类型串（显示面 source 形态：`func f(int, str) -> int`——Python 实证
    /// 参数面仅类型名，不含参数名）。
    pub param_types: Vec<String>,
    /// 返回类型串（显示面 `-> <ret>`；无 = 省略）。
    pub ret: Option<String>,
    pub body: Vec<Stmt>,
    /// 定义处的环境（闭包捕获——调用时 call_env 的 parent = 此环境）。
    pub enclosing: Option<Rc<RefCell<Environment>>>,
    /// nonlocal 声明名（body 顶层 Nonlocal 语句——赋值重定向外层作用域）。
    pub nonlocals: Vec<String>,
}

impl Clone for Function {
    fn clone(&self) -> Self {
        Function {
            name: self.name.clone(),
            params: self.params.clone(),
            param_types: self.param_types.clone(),
            ret: self.ret.clone(),
            body: self.body.clone(),
            // enclosing = Rc 共享（闭包捕获同一环境）
            enclosing: self.enclosing.clone(),
            nonlocals: self.nonlocals.clone(),
        }
    }
}

impl std::fmt::Debug for Function {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Function")
            .field("name", &self.name)
            .field("params", &self.params)
            .field("body_len", &self.body.len())
            .finish()
    }
}

impl Environment {
    fn new(parent: Option<Rc<RefCell<Environment>>>) -> Environment {
        Environment {
            vars: HashMap::new(),
            functions: HashMap::new(),
            parent,
            nonlocals: std::collections::BTreeSet::new(),
        }
    }
    fn set(&mut self, name: &str, value: IbValue) {
        self.vars.insert(name.to_string(), value);
    }



    fn get(&self, name: &str) -> Option<IbValue> {
        if let Some(v) = self.vars.get(name) {
            return Some(v.clone());
        }
        match &self.parent {
            Some(p) => p.borrow().get(name),
            None => None,
        }
    }
    fn define_function(&mut self, f: Function) {
        // 函数 = 一等值（值域可赋值/别名/传参——Python 语义：f() 可经任意名字
        // 调用）：functions 表（按名查找）+ vars 表（值通道）双写
        let rc = Rc::new(f.clone());
        let name = f.name.clone();
        self.functions.insert(name.clone(), f);
        self.vars.insert(name, IbValue::Function(rc));
    }
    fn get_function(&self, name: &str) -> Option<Function> {
        if let Some(f) = self.functions.get(name) {
            return Some(f.clone());
        }
        match &self.parent {
            Some(p) => p.borrow().get_function(name),
            None => None,
        }
    }
}

/// 全局环境（作用域链根）的 Rc——短借用走链（不跨递归持借用）。
fn global_rc(env: &Rc<RefCell<Environment>>) -> Rc<RefCell<Environment>> {
    let parent = env.borrow().parent.clone();
    match parent {
        Some(p) => global_rc(&p),
        None => env.clone(),
    }
}

enum Flow {
    Next,
    Return(IbValue),
    Break,
    Continue,
}

// --------------------------------------------------------------------------- //
// 解释器（tree-walking；&self + output 参数——避免双可变借用）
// --------------------------------------------------------------------------- //
pub struct Interpreter {
    /// host service 桥接（Python 对象——KB 操作经此委托；None = 无宿主服务）。
    bridge: Option<Py<PyAny>>,
}

impl Interpreter {
    pub fn new() -> Interpreter {
        Interpreter { bridge: None }
    }
    /// 带 host service 桥接（KB 操作经此委托给 Python knowledge 对象）。
    pub fn with_bridge(bridge: Py<PyAny>) -> Interpreter {
        Interpreter {
            bridge: Some(bridge),
        }
    }

    /// 执行模块（返回数据面 print 输出）。
    pub fn run_module(&self, module: &Module) -> Result<Vec<String>, Thrown> {
        self.run_module_with_state(module, &[]).map(|(output, _)| output)
    }

    /// 执行模块（带初始变量注入 + 最终状态导出——⑦ 切换门变量面契约：
    /// 初始变量 = 模块顶层环境预置；最终状态 = 顶层环境全条目
    /// [vars 表——函数经双写亦在 vars]）。
    pub fn run_module_with_state(
        &self,
        module: &Module,
        initial: &[(String, IbValue)],
    ) -> Result<(Vec<String>, Vec<(String, IbValue)>), Thrown> {
        let mut output: Vec<String> = Vec::new();
        let mut env = Environment::new(None);
        for (name, value) in initial {
            env.set(name, value.clone());
        }
        let env = Rc::new(RefCell::new(env));
        for stmt in &module.body {
            let flow = self.exec_stmt(&env, stmt, &mut output)?;
            if !matches!(flow, Flow::Next) {
                break;
            }
        }
        let state: Vec<(String, IbValue)> =
            env.borrow().vars.iter().map(|(k, v)| (k.clone(), v.clone())).collect();
        Ok((output, state))
    }

    fn exec_stmt(
        &self,
        env: &Rc<RefCell<Environment>>,
        stmt: &Stmt,
        output: &mut Vec<String>,
    ) -> Result<Flow, Thrown> {
        Ok(match stmt {
            Stmt::Assign { targets, value, .. } => {
                let v: Option<IbValue> = match value {
                    Some(e) => Some(self.eval_expr(env, e, output)?),
                    None => None,
                };
                if let Some(target) = targets.first() {
                    // 声明面 target（TypeAnnotatedExpr）= 运行时纯赋值——注解仅
                    // 类型/编译期语义（值域不消费）
                    let effective = match target {
                        Expr::TypeAnnotatedExpr { target: inner, .. } => inner.as_ref(),
                        other => other,
                    };
                    match effective {
                        Expr::Name { id, .. } => {
                            if let Some(val) = &v {
                                assign_env(env, id, val.clone());
                            }
                        }
                        // 元组解包声明（Store target）：值 = List → 逐元素赋值
                        // （分量 = annotated 内层名字；长度不符 = 错误面静默）
                        Expr::Tuple { elts, .. } => {
                            if let Some(IbValue::List(items)) = &v {
                                let elems = items.borrow();
                                for (i, e) in elts.iter().enumerate() {
                                    let name = match e {
                                        Expr::TypeAnnotatedExpr { target: inner, .. } => {
                                            match inner.as_ref() {
                                                Expr::Name { id, .. } => Some(id.clone()),
                                                _ => None,
                                            }
                                        }
                                        Expr::Name { id, .. } => Some(id.clone()),
                                        _ => None,
                                    };
                                    if let (Some(id), Some(val)) = (name, elems.get(i)) {
                                        env.borrow_mut().set(&id, val.clone());
                                    }
                                }
                            }
                        }
                        Expr::Subscript { value, slice, .. } => {
                            let base = self.eval_expr(env, value, output)?;
                            let key = self.eval_expr(env, slice, output)?;
                            if let Some(val) = &v {
                                assign_subscript(&base, &key, val.clone());
                            }
                        }
                        _ => {}
                    }
                }
                Flow::Next
            }
            Stmt::AugAssign { target, op, value, .. } => {
                // x op= v → x = x op v（load x，应用 op，store）
                if let Expr::Name { id, .. } = target {
                    let cur = env.borrow().get(id).unwrap_or(IbValue::Int(0));
                    let rhs = self.eval_expr(env, value, output)?;
                    // 复合算子映射（"+=" → "+"，"*=" → "*"，...）
                    let base_op: &str = match op.as_str() {
                        "+=" => "+",
                        "-=" => "-",
                        "*=" => "*",
                        "/=" => "/",
                        "//=" => "//",
                        "%=" => "%",
                        "**=" => "**",
                        _ => op.as_str(),
                    };
                    let result = self.binop(&cur, base_op, &rhs)?;
                    assign_env(env, id, result);
                }
                Flow::Next
            }
            Stmt::ExprStmt { value, .. } => {
                self.eval_expr(env, value, output)?;
                Flow::Next
            }
            Stmt::If { test, body, orelse, .. } => {
                let cond = self.eval_expr(env, test, output)?.truthy();
                if cond {
                    self.exec_body(env, body, output)?
                } else {
                    self.exec_body(env, orelse, output)?
                }
            }
            Stmt::For { target, iter, body, orelse, .. } => {
                let items = self.eval_iter(env, iter, output)?;
                let mut ran_else = false;
                // 目标名：裸名 / 声明形态内层名（typed for 目标——声明面语义，
                // 运行时 = 纯赋值）；元组目标 = 逐元素解包绑定
                let target_name: Option<String> = match target {
                    Expr::Name { id, .. } => Some(id.clone()),
                    Expr::TypeAnnotatedExpr { target: inner, .. } => match inner.as_ref() {
                        Expr::Name { id, .. } => Some(id.clone()),
                        _ => None,
                    },
                    _ => None,
                };
                let target_tuple: Option<Vec<String>> = match target {
                    Expr::Tuple { elts, .. } => {
                        let mut names = Vec::new();
                        for e in elts {
                            let n = match e {
                                Expr::Name { id, .. } => Some(id.clone()),
                                Expr::TypeAnnotatedExpr { target: inner, .. } => {
                                    match inner.as_ref() {
                                        Expr::Name { id, .. } => Some(id.clone()),
                                        _ => None,
                                    }
                                }
                                _ => None,
                            };
                            match n {
                                Some(x) => names.push(x),
                                None => {
                                    names.clear();
                                    break;
                                }
                            }
                        }
                        Some(names)
                    }
                    _ => None,
                };
                for item in items {
                    if let Some(names) = &target_tuple {
                        let list = match item {
                            IbValue::List(l) => l.borrow().clone(),
                            _ => continue,
                        };
                        for (n, v) in names.iter().zip(list.iter()) {
                            env.borrow_mut().set(n, v.clone());
                        }
                        match self.exec_body(env, body, output)? {
                            Flow::Break => {
                                ran_else = true;
                                break;
                            }
                            Flow::Return(v) => return Ok(Flow::Return(v)),
                            Flow::Next | Flow::Continue => {}
                        }
                        continue;
                    }
                    let name = match &target_name {
                        Some(n) => n.clone(),
                        None => continue,
                    };
                    env.borrow_mut().set(&name, item);
                    match self.exec_body(env, body, output)? {
                        Flow::Break => {
                            ran_else = false;
                            break;
                        }
                        Flow::Return(v) => return Ok(Flow::Return(v)),
                        _ => {}
                    }
                }
                if !ran_else && !orelse.is_empty() {
                    self.exec_body(env, orelse, output)?
                } else {
                    Flow::Next
                }
            }
            Stmt::While { test, body, orelse, .. } => {
                let mut ran_else = false;
                while self.eval_expr(env, test, output)?.truthy() {
                    match self.exec_body(env, body, output)? {
                        Flow::Break => {
                            ran_else = false;
                            break;
                        }
                        Flow::Continue => continue,
                        Flow::Return(v) => return Ok(Flow::Return(v)),
                        _ => {}
                    }
                }
                if !ran_else && !orelse.is_empty() {
                    self.exec_body(env, orelse, output)?
                } else {
                    Flow::Next
                }
            }
            Stmt::FunctionDef { name, args, body, returns, .. } => {
                let params: Vec<String> = args.iter().map(|a| a.arg.clone()).collect();
                // 显示面 source 形态分量（参数类型串 + 返回类型串——Python 实证
                // `func f(int) -> str`）
                let param_types: Vec<String> = args
                    .iter()
                    .filter_map(|a| a.annotation.as_ref())
                    .map(|ann| crate::node_serializer::annotation_type_str(ann))
                    .collect();
                let ret = returns
                    .as_ref()
                    .map(|r| crate::node_serializer::annotation_type_str(r));
                // enclosing = 当前环境（闭包捕获——嵌套函数可访问 outer 局部变量）
                let enclosing = Some(env.clone());
                // nonlocal 声明名（body 顶层 Nonlocal 语句——赋值重定向外层）
                let nonlocals: Vec<String> = body
                    .iter()
                    .filter_map(|s| match s {
                        Stmt::Nonlocal { names, .. } => Some(names.clone()),
                        _ => None,
                    })
                    .flatten()
                    .collect();
                env.borrow_mut().define_function(Function {
                    name: name.clone(),
                    params,
                    param_types,
                    ret,
                    body: body.clone(),
                    enclosing,
                    nonlocals,
                });
                Flow::Next
            }
            Stmt::Return { value, .. } => {
                let v = match value {
                    Some(e) => self.eval_expr(env, e, output)?,
                    None => IbValue::None_,
                };
                Flow::Return(v)
            }
            Stmt::Break { .. } => Flow::Break,
            Stmt::Continue { .. } => Flow::Continue,
            Stmt::Pass { .. } => Flow::Next,
            Stmt::Import { names, .. } => {
                // import X [as Y]：绑定名 = asname 或 X；经桥接解析为宿主模块
                // （host object）绑定到环境；未知模块 = no-op（宿主环境处理）
                for alias in names {
                    let binding = alias
                        .asname
                        .clone()
                        .unwrap_or_else(|| alias.name.clone());
                    if let Some(host) = self.get_host_module(&binding) {
                        env.borrow_mut().set(&binding, host);
                    }
                }
                Flow::Next
            }
            Stmt::FromImport { module, names, .. } => {
                // from X import Y [as Z]：绑定名 = asname 或 Y；Y = X 的宿主属性
                // （经桥接 host_getattr 解析）；未知模块/属性 = no-op。meta 的
                // quote/eval = 原生函数引用（去 Host 化——call_meta_fn 分发）。
                for alias in names {
                    let src = alias.name.clone();
                    let binding = alias
                        .asname
                        .clone()
                        .unwrap_or_else(|| src.clone());
                    if module == "meta" && (src == "quote" || src == "eval") {
                        env.borrow_mut().set(
                            &binding,
                            IbValue::MetaFn(if src == "quote" { "quote" } else { "eval" }),
                        );
                        continue;
                    }
                    if let Some(mod_host) = self.get_host_module(module) {
                        if let IbValue::Host(h) = &mod_host {
                            let val = self.get_host_attribute(h, &src);
                            env.borrow_mut().set(&binding, val);
                        }
                    }
                }
                Flow::Next
            }
            // global/nonlocal：编译期语义——运行时无操作（语义效果在编译期经
            // 符号解析完成；运行期赋值经作用域链自然穿透）
            Stmt::Global { .. } | Stmt::Nonlocal { .. } => Flow::Next,
            // raise：异常对象求值后抛出（异常传播机制——try/except 捕获面；
            // IBCI 语义：raise 不做类型检查，匹配在 except 处理器面[类可赋性]；
            // 裸 raise = 编译错误[Python 实证]，exc 必在）
            Stmt::Raise { exc, .. } => {
                let value = match exc {
                    Some(e) => self.eval_expr(env, e, output)?,
                    None => IbValue::None_,
                };
                return Err(Thrown { value, pos: None });
            }
            // switch：匹配后自动跳出（无 fall-through）；case 内 break = no-op
            // （C 习惯，接受为退出 case）；Return 透传、Continue 透传外层循环
            // （switch 本身不是循环）
            Stmt::Switch { test, cases, .. } => {
                let tv = self.eval_expr(env, test, output)?;
                for case in cases {
                    let matched = match &case.pattern {
                        None => true, // default case
                        Some(p) => {
                            let pv = self.eval_expr(env, p, output)?;
                            &tv == &pv
                        }
                    };
                    if !matched {
                        continue;
                    }
                    for s in &case.body {
                        match self.exec_stmt(env, s, output)? {
                            Flow::Return(v) => return Ok(Flow::Return(v)),
                            Flow::Continue => return Ok(Flow::Continue),
                            // break = no-op（匹配后自动跳出——退出 case）
                            Flow::Break => break,
                            Flow::Next => {}
                        }
                    }
                    break; // 自动跳出（无 fall-through）
                }
                Flow::Next
            }
            // try/except/else/finally（异常传播捕获面——Python VM IbTry 语义
            // 转录：body 抛异常 = 逐 handler 匹配[类可赋性：handler 类型 = 值
            // 类型名或在值类型继承链上]；handler 变量 = 全局绑定[Python 实证：
            // runtime_context.define_variable——越 try 块可见]；else 仅无异常
            // 无 signal 时执行；finally 所有路径执行且 signal 覆盖 pending；
            // 无匹配 handler = finally 后 re-raise）
            Stmt::Try { body, handlers, orelse, finalbody, .. } => {
                let mut pending: Option<Flow> = None;
                let mut raised: Option<Thrown> = None;
                match self.exec_body(env, body, output) {
                    Ok(Flow::Next) => {}
                    Ok(sig) => pending = Some(sig),
                    Err(t) => raised = Some(t),
                }
                if let Some(t) = &raised {
                    let exc_value = t.value.clone();
                    let mut handled = false;
                    for h in handlers {
                        let matched = match &h.exc_type {
                            Some(Expr::Name { id, .. }) => {
                                exception_assignable(&exc_value, id)
                            }
                            _ => false,
                        };
                        if !matched {
                            continue;
                        }
                        if let Some(name) = &h.name {
                            // 异常变量 = 全局绑定（越 try 块可见——Python 实证）
                            set_global_env(env, name, exc_value.clone());
                        }
                        match self.exec_body(env, &h.body, output) {
                            Ok(Flow::Next) => {}
                            Ok(sig) => pending = Some(sig),
                            Err(t2) => {
                                // handler 内再抛 = 未处理（finally 后 re-raise）
                                raised = Some(t2);
                                continue;
                            }
                        }
                        handled = true;
                        break;
                    }
                    if !handled {
                        // 无匹配：finally 后 re-raise
                        match self.exec_body(env, finalbody, output) {
                            Ok(Flow::Next) => {}
                            Ok(sig) => return Ok(sig), // finally signal 覆盖
                            Err(t2) => return Err(t2),
                        }
                        return Err(Thrown { value: exc_value, pos: None });
                    }
                    // 已处理 = 异常消解（不 re-raise）
                    raised = None;
                } else if pending.is_none() {
                    // 无异常且 body 无 signal：else
                    match self.exec_body(env, orelse, output) {
                        Ok(Flow::Next) => {}
                        Ok(sig) => pending = Some(sig),
                        Err(t) => raised = Some(t),
                    }
                }
                // finally：所有路径执行（signal 覆盖 pending）
                match self.exec_body(env, finalbody, output) {
                    Ok(Flow::Next) => {}
                    Ok(sig) => pending = Some(sig),
                    Err(t) => return Err(t),
                }
                if let Some(t) = &raised {
                    return Err(t.clone());
                }
                pending.unwrap_or(Flow::Next)
            }
            Stmt::ClassDef { body, .. } => self.exec_body(env, body, output)?
        })
    }

    /// 宿主对象属性访问（如 q.source）——委托桥接 host_getattr（IBC 宿主值类型
    /// 经运行时属性分发，非纯 getattr）。
    fn get_host_attribute(&self, pyobj: &Py<PyAny>, attr: &str) -> IbValue {
        let bridge = match &self.bridge {
            Some(b) => b,
            None => return IbValue::None_,
        };
        Python::with_gil(|py| -> PyResult<IbValue> {
            let b = bridge.bind(py);
            let obj_ref = pyobj.bind(py);
            let res = b.call_method("host_getattr", (obj_ref, attr), None)?;
            Ok(from_py(py, &res))
        })
        .unwrap_or(IbValue::None_)
    }

    /// 经 host service 桥接取宿主模块（如 meta）——None = 未知模块。
    fn get_host_module(&self, name: &str) -> Option<IbValue> {
        let bridge = match &self.bridge {
            Some(b) => b,
            None => return None,
        };
        Python::with_gil(|py| -> PyResult<Option<IbValue>> {
            let b = bridge.bind(py);
            let obj = b.call_method("get_host_module", (name,), None)?;
            if obj.is_none() {
                Ok(None)
            } else {
                Ok(Some(IbValue::Host(obj.unbind())))
            }
        })
        .ok()
        .flatten()
    }

    fn exec_body(
        &self,
        env: &Rc<RefCell<Environment>>,
        body: &[Stmt],
        output: &mut Vec<String>,
    ) -> Result<Flow, Thrown> {
        for s in body {
            let flow = self.exec_stmt(env, s, output)?;
            if !matches!(flow, Flow::Next) {
                return Ok(flow);
            }
        }
        Ok(Flow::Next)
    }

    fn eval_expr(&self, env: &Rc<RefCell<Environment>>, expr: &Expr, output: &mut Vec<String>) -> Result<IbValue, Thrown> {
        Ok(match expr {
            Expr::Constant { value, .. } => const_to_value(value),
            Expr::Name { id, .. } => match env.borrow().get(id) {
                Some(v) => v,
                None => IbValue::None_,
            },
            Expr::BinOp { pos, left, op, right, .. } => {
                let l = self.eval_expr(env, left, output)?;
                let r = self.eval_expr(env, right, output)?;
                // 类型错误现场 = 表达式位置（诊断位置契约）
                self.binop(&l, op, &r)
                    .map_err(|t| Thrown {
                        pos: Some((pos.lineno, pos.col_offset)),
                        value: t.value,
                    })?
            }
            Expr::UnaryOp { op, operand, .. } => {
                let v = self.eval_expr(env, operand, output)?;
                match op.as_str() {
                    "-" => match v {
                        IbValue::Int(i) => IbValue::Int(-i),
                        IbValue::Float(f) => IbValue::Float(-f),
                        _ => v,
                    },
                    "not" => IbValue::Bool(!v.truthy()),
                    _ => v,
                }
            }
            Expr::BoolOp { op, values, .. } => {
                // and / or（短路求值）
                if op == "and" {
                    let mut result = IbValue::Bool(true);
                    for v in values {
                        let x = self.eval_expr(env, v, output)?;
                        if !x.truthy() {
                            return Ok(x); // 短路：返回第一个假值
                        }
                        result = x;
                    }
                    result
                } else {
                    let mut result = IbValue::Bool(false);
                    for v in values {
                        let x = self.eval_expr(env, v, output)?;
                        if x.truthy() {
                            return Ok(x); // 短路：返回第一个真值
                        }
                        result = x;
                    }
                    result
                }
            }
            Expr::Compare { pos, left, ops, comparators, .. } => {
                // 链式比较（a < b < c）——左到右，全部成立
                let mut cur = self.eval_expr(env, left, output)?;
                let mut result = true;
                for (op, r) in ops.iter().zip(comparators.iter()) {
                    let rv = self.eval_expr(env, r, output)?;
                    let cv = self.compare(&cur, op, &rv)
                        .map_err(|t| Thrown {
                            pos: Some((pos.lineno, pos.col_offset)),
                            value: t.value,
                        })?;
                    if !cv.truthy() {
                        result = false;
                        break;
                    }
                    cur = rv; // 链：当前比较的右值 = 下一比较的左值
                }
                IbValue::Bool(result)
            }
            Expr::Call { func, args, .. } => {
                // func: &Box<Expr> → as_ref() 得 &Expr
                match func.as_ref() {
                    Expr::Attribute { value, attr, .. } => {
                        // 原生 meta 函数面（meta.quote / meta.eval——去 Host 化：
                        // 验证门 + 隔离执行，经 call_meta_fn 原生分发）
                        if let Expr::Name { id, .. } = value.as_ref() {
                            if id == "meta" && (attr == "quote" || attr == "eval") {
                                let arg_vals: Vec<IbValue> = args
                                    .iter()
                                    .map(|a| self.eval_expr(env, a, output))
                                    .collect::<Result<Vec<IbValue>, _>>()?;
                                return Ok(self.call_meta_fn(attr, arg_vals, output));
                            }
                        }
                        let obj = self.eval_expr(env, value, output)?;
                        let attr = attr.clone();
                        let arg_vals: Vec<IbValue> =
                            args.iter().map(|a| self.eval_expr(env, a, output)).collect::<Result<Vec<IbValue>, _>>()?;
                        self.call_method(&obj, &attr, arg_vals)?
                    }
                    _ => {
                        let func_name = match func.as_ref() {
                            Expr::Name { id, .. } => id.clone(),
                            _ => String::new(),
                        };
                        let arg_vals: Vec<IbValue> =
                            args.iter().map(|a| self.eval_expr(env, a, output)).collect::<Result<Vec<IbValue>, _>>()?;
                        // 原生 meta 函数绑定（from meta import quote/eval）——
                        // 值克隆出借用语境（env Ref 不得贯穿调用体——Re-entrant
                        // 赋值[nonlocal]于调用内对同一 env 取独占借）
                        let binding = env.borrow().get(&func_name); // 自有值（Ref 语句末释放——不贯穿调用体）
                        match binding {
                            Some(IbValue::MetaFn(n)) => {
                                self.call_meta_fn(&n, arg_vals, output)
                            }
                            // 函数值（一等值别名——fn f = g / x = g）→ 按值调用
                            Some(IbValue::Function(f)) => {
                                let global = global_rc(env);
                                self.call_user_function(&f, arg_vals, output, &global)?
                            }
                            // 函数为宿主对象 → 调宿主函数
                            Some(IbValue::Host(h)) => {
                                self.call_host_function(&h, arg_vals)
                            }
                            _ => {
                                self.call_function(env, &func_name, arg_vals, output)?
                            }
                        }
                    }
                }
            }
            Expr::List { elts, .. } => {
                let items: Vec<IbValue> = elts
                    .iter()
                    .map(|e| self.eval_expr(env, e, output))
                    .collect::<Result<Vec<IbValue>, _>>()?;
                IbValue::list_new(items)
            }
            Expr::Tuple { elts, .. } => {
                // 元组：IBC 数据面 = 列表（同 List）
                let items: Vec<IbValue> = elts
                    .iter()
                    .map(|e| self.eval_expr(env, e, output))
                    .collect::<Result<Vec<IbValue>, _>>()?;
                IbValue::list_new(items)
            }
            // 切片仅在 Subscript 内有意义（x[1:3]）——独立求值无定义 = None_
            Expr::Slice { .. } => IbValue::None_,
            Expr::Dict { keys, values, .. } => {
                let pairs: Vec<(IbValue, IbValue)> = keys
                    .iter()
                    .zip(values.iter())
                    .map(|(k, v)| {
                        let kv = self.eval_expr(env, k, output)?;
                        let vv = self.eval_expr(env, v, output)?;
                        Ok((kv, vv))
                    })
                    .collect::<Result<Vec<(IbValue, IbValue)>, _>>()?;
                IbValue::dict_new(pairs)
            }
            Expr::Attribute { value, attr, .. } => {
                let obj = self.eval_expr(env, value, output)?;
                match obj {
                    // quoted 的 source 字段（原生——完整源串）
                    IbValue::Quoted { ref source } if attr == "source" => {
                        IbValue::Str(source.clone())
                    }
                    // 宿主对象属性访问——委托 Python
                    IbValue::Host(h) => self.get_host_attribute(&h, attr),
                    other => other,
                }
            }
            Expr::Subscript { value, slice, .. } => {
                let base = self.eval_expr(env, value, output)?;
                match slice.as_ref() {
                    // 切片：x[lower:upper]
                    Expr::Slice { lower, upper, step, .. } => {
                        let lo = match lower.as_ref() {
                            Some(e) => Some(self.eval_expr(env, e, output)?),
                            None => None,
                        };
                        let hi = match upper.as_ref() {
                            Some(e) => Some(self.eval_expr(env, e, output)?),
                            None => None,
                        };
                        let st = match step.as_ref() {
                            Some(e) => Some(self.eval_expr(env, e, output)?),
                            None => None,
                        };
                        subscript_slice(&base, lo.as_ref(), hi.as_ref(), st.as_ref())
                    }
                    // 单表达式下标：x[1]
                    _ => {
                        let key = self.eval_expr(env, slice, output)?;
                        subscript_get(&base, &key)?
                    }
                }
            }
            Expr::IfExp { test, body, orelse, .. } => {
                let cond = self.eval_expr(env, test, output)?.truthy();
                if cond {
                    self.eval_expr(env, body, output)?
                } else {
                    self.eval_expr(env, orelse, output)?
                }
            }
            Expr::TypeAnnotatedExpr { target, .. } => {
                // 声明面 target 表达式位置（防御臂——声明 target 仅经 Assign 消费；
                // 若被求值 = 内层名字值）
                self.eval_expr(env, target, output)?
            }
            Expr::Lambda { .. } => IbValue::None_,
        })
    }

    fn eval_iter(
        &self,
        env: &Rc<RefCell<Environment>>,
        iter: &Expr,
        output: &mut Vec<String>,
    ) -> Result<Vec<IbValue>, Thrown> {
        let v = self.eval_expr(env, iter, output)?;
        match v {
            IbValue::List(l) => Ok(l.borrow().clone()),
            // 空 Optional 迭代 = 属性错误（Python 契约：空包装无迭代面）
            IbValue::None_ => Err(runtime_error(
                "AttributeError",
                "iteration over empty optional",
            )),
            // 非可迭代值静默（登记角——Python TypeError 面未移植）
            _ => Ok(Vec::new()),
        }
    }

    fn binop(&self, l: &IbValue, op: &str, r: &IbValue) -> Result<IbValue, Thrown> {
        // 类型错误面（Python 契约实证：str 混合运算 = TypeError——str+str
        // 连接 / str*int 重复合法；其余 str 混合[含 str*str] = 类型错误；
        // str 与数值混合 + 亦错）
        if matches!(l, IbValue::Str(_)) || matches!(r, IbValue::Str(_)) {
            return match (l, r, op) {
                (IbValue::Str(a), IbValue::Str(b), "+") => {
                    Ok(IbValue::Str(format!("{}{}", a, b)))
                }
                (IbValue::Str(a), IbValue::Int(n), "*")
                | (IbValue::Int(n), IbValue::Str(a), "*") => {
                    let k = (*n).max(0) as usize;
                    Ok(IbValue::Str(a.repeat(k)))
                }
                _ => {
                    let msg = format!("unsupported operand type(s) for {}", op);
                    Err(runtime_error("TypeError", &msg))
                }
            };
        }
        if let (IbValue::List(a), IbValue::List(b)) = (l, r) {
            if op == "+" {
                let mut merged = a.borrow().clone();
                merged.extend(b.borrow().clone());
                return Ok(IbValue::list_new(merged));
            }
        }
        Ok(match op {
            "+" => num_result(l, r, |a, b| a + b),
            "-" => num_result(l, r, |a, b| a - b),
            "*" => num_result(l, r, |a, b| a * b),
            "/" => floor_div(l, r)?,
            "//" => floor_div(l, r)?,
            "%" => modulo(l, r)?,
            "**" => pow_op(l, r),
            // 位运算（int/bool——Python 契约：bool 位运算 = bool 结果
            // [True | False = True]；int 位运算 = int）
            "|" | "&" | "^" => bitwise(l, op, r),
            _ => IbValue::None_,
        })
    }

    fn compare(&self, l: &IbValue, op: &str, r: &IbValue) -> Result<IbValue, Thrown> {
        // is / is not = 同一性（IBC 实证契约：None 同一性 + 数值按值相等；
        // 非数值[str/list 等] = 对象同一性——异对象恒 False）
        if op == "is" || op == "is not" {
            let identity = match (l, r) {
                (IbValue::None_, IbValue::None_) => true,
                _ => {
                    matches!((l.as_num(), r.as_num()), (Some(_), Some(_)))
                        && self.cmp(l, r) == 0
                }
            };
            return Ok(IbValue::Bool(if op == "is" { identity } else { !identity }));
        }
        // 关系运算类型面（Python 契约实证：跨族[数值 vs str]关系比较 =
        // TypeError；==/!= 跨族 = 不相等[非错误]）
        if op != "==" && op != "!=" {
            let fam = |v: &IbValue| match v {
                IbValue::Str(_) => 1,
                IbValue::None_ => 2,
                _ if v.as_num().is_some() => 0,
                _ => 3,
            };
            if fam(l) != fam(r) {
                let msg = format!("unsupported operand type(s) for {}", op);
                return Err(runtime_error("TypeError", &msg));
            }
        }
        let c = self.cmp(l, r);
        let b = match op {
            ">" => c > 0,
            "<" => c < 0,
            ">=" => c >= 0,
            "<=" => c <= 0,
            "==" => c == 0,
            "!=" => c != 0,
            _ => false,
        };
        Ok(IbValue::Bool(b))
    }

    fn cmp(&self, l: &IbValue, r: &IbValue) -> i64 {
        match (l.as_num(), r.as_num()) {
            (Some((a, _)), Some((b, _))) => {
                if a < b {
                    -1
                } else if a > b {
                    1
                } else {
                    0
                }
            }
            _ => match (l, r) {
                // None 相等性（None == None / None == 空 Optional 对称——
                // 空 Optional 值面 = None_；Python 契约：is/== 同真）
                (IbValue::None_, IbValue::None_) => 0,
                (IbValue::Str(a), IbValue::Str(b)) => {
                    a.partial_cmp(b).map(|o| o as i64).unwrap_or(2)
                }
                (IbValue::Bool(a), IbValue::Bool(b)) => (*a as i64) - (*b as i64),
                // 跨族[数值 vs str 等] = 不相等（== 面；关系面已前置 TypeError）
                _ => 2,
            },
        }
    }

    fn call_function(
        &self,
        env: &Rc<RefCell<Environment>>,
        name: &str,
        args: Vec<IbValue>,
        output: &mut Vec<String>,
    ) -> Result<IbValue, Thrown> {
        Ok(match name {
            "print" => {
                // 多参 = 空格连接（Python print 语义——数据面实证 print(a, b) =
                // "a b"；单参行为不变）
                let parts: Vec<String> = args.iter().map(|a| a.repr()).collect();
                output.push(parts.join(" ")); // 无参 = 空行（Python print() 语义）
                IbValue::None_
            }
            "len" => match args.first() {
                Some(IbValue::List(l)) => IbValue::Int(l.borrow().len() as i64),
                Some(IbValue::Str(s)) => IbValue::Int(s.len() as i64),
                Some(IbValue::Dict(d)) => IbValue::Int(d.borrow().len() as i64),
                // 空 Optional len = 属性错误（Python 契约：空包装无 len 面）
                Some(IbValue::None_) => {
                    return Err(runtime_error(
                        "AttributeError",
                        "len on empty optional",
                    ))
                }
                _ => IbValue::Int(0),
            },
            // 异常对象构造（Exception/LLMError/ThreadError 家族——class +
            // message；显示面 = `<class>: <message>`[无 message = 仅类名]）
            name if is_exception_class(name) => {
                let message = match args.first() {
                    Some(IbValue::Str(s)) => s.clone(),
                    Some(other) => other.repr(),
                    None => String::new(),
                };
                IbValue::Error {
                    class: name.to_string(),
                    message,
                }
            }
            "range" => {
                let items: Vec<IbValue> = if args.len() == 1 {
                    let stop = match &args[0] {
                        IbValue::Int(i) => *i,
                        _ => 0,
                    };
                    (0..stop).map(IbValue::Int).collect()
                } else if args.len() >= 2 {
                    let start = match &args[0] {
                        IbValue::Int(i) => *i,
                        _ => 0,
                    };
                    let stop = match &args[1] {
                        IbValue::Int(i) => *i,
                        _ => 0,
                    };
                    (start..stop).map(IbValue::Int).collect()
                } else {
                    Vec::new()
                };
                IbValue::list_new(items)
            }
            "knowledge" => {
                // KB 宿主服务——经桥接创建 Python knowledge 对象（单点真理）
                self.call_knowledge()
            }
            "vec" => {
                // vector 值构造（元素面校验：数值元素，非数值 = None_[错误面]）
                match args.first() {
                    Some(IbValue::List(items)) => {
                        let mut elems: Vec<f64> = Vec::new();
                        for x in items.borrow().iter() {
                            match x {
                                IbValue::Int(i) => elems.push(*i as f64),
                                IbValue::Float(f) => elems.push(*f),
                                _ => return Ok(IbValue::None_),
                            }
                        }
                        IbValue::Vector(elems)
                    }
                    _ => IbValue::None_,
                }
            }
            _ => {
                if let Some(f) = env.borrow().get_function(name) {
                    // 全局环境（作用域链根——使函数体可访问全局函数[递归]）
                    let global = global_rc(env);
                    self.call_user_function(&f, args, output, &global)?
                } else {
                    IbValue::None_
                }
            }
        })
    }

    /// meta.quote / meta.eval 原生分发（去 Host 化——语义单点真理 =
    /// HostService.quote_expression / eval_quoted 的编译期/执行期契约转录）。
    ///
    /// quote(source: str) → quoted 值：单一验证门（包装体 `__qeval__ = <source>`
    /// 的 compile-only 等价——① 非空 str ② 语法 ③ 表达式性[单表达式语句]
    /// ④ 自包含性[fresh scope：自由名 ⊆ intrinsic 集，无隐式捕获面]）。零 LLM。
    ///
    /// eval(quoted) → 隔离执行取回**值**（命令形态）：quoted 源串经 Rust parser +
    /// interpreter 在 fresh 环境执行（无用户全局——自包含门已保证；stdout 面
    /// 丢弃[同 silent=True]，返回表达式值）。子进程进程级隔离 = 资源治理面，
    /// 数据面语义等价于 fresh scope 隔离（语料零 LLM / 零跨进程状态依赖）。
    fn call_meta_fn(&self, name: &str, args: Vec<IbValue>, output: &mut Vec<String>) -> IbValue {
        match name {
            "quote" => {
                let Some(IbValue::Str(source)) = args.first() else {
                    return IbValue::None_;
                };
                if source.trim().is_empty() {
                    return IbValue::None_;
                }
                let module = crate::parser::parse_to_module(source);
                // 表达式性：单表达式语句（__qeval__ = <source> 可编译 ⟺ source 是表达式）
                let value = match &module.body[..] {
                    [crate::parser::Stmt::ExprStmt { value, .. }] => value.clone(),
                    _ => return IbValue::None_,
                };
                // 自包含性：自由名 ⊆ intrinsic 63 固有集（fresh scope 无用户绑定）
                let mut refs = std::collections::BTreeSet::new();
                crate::node_serializer::collect_refs_expr(&value, &mut refs);
                let intrinsics: std::collections::BTreeSet<String> =
                    crate::intrinsic_symbols::intrinsic_names().into_iter().collect();
                if !refs.is_subset(&intrinsics) {
                    return IbValue::None_;
                }
                IbValue::Quoted { source: source.clone() }
            }
            "eval" => {
                let Some(IbValue::Quoted { source }) = args.first() else {
                    return IbValue::None_;
                };
                let module = crate::parser::parse_to_module(source);
                let value = match &module.body[..] {
                    [crate::parser::Stmt::ExprStmt { value, .. }] => value.clone(),
                    _ => return IbValue::None_,
                };
                // 隔离执行（fresh 环境——与主执行同构：intrinsic 经 call_function
                // 分发；silent stdout 面丢弃）
                let fresh = Rc::new(RefCell::new(Environment::new(None)));
                let mut silent_output: Vec<String> = Vec::new();
                // 隔离执行取回值；执行期 raise = 错误面（None_——meta.eval 语料
                // 面无 raise 探针，跨切面错误面统一后续）
                match self.eval_expr(&fresh, &value, &mut silent_output) {
                    Ok(v) => v,
                    Err(_) => IbValue::None_,
                }
            }
            _ => IbValue::None_,
        }
    }

    /// knowledge() → Rust 原生 KB 值（去 Host 化：治理词表 + 事实日志 + active
    /// 索引——kb::KbState 空白实例；方法面经 kb::dispatch 原生分发）。
    fn call_knowledge(&self) -> IbValue {
        IbValue::Knowledge(Rc::new(RefCell::new(crate::kb::KbState::blank())))
    }

    fn call_user_function(
        &self,
        f: &Function,
        args: Vec<IbValue>,
        output: &mut Vec<String>,
        global: &Rc<RefCell<Environment>>,
    ) -> Result<IbValue, Thrown> {
        // 递归深度守卫（环境限制异常——Python 契约：深递归触底 =
        // RecursionError 根因原样传播）
        let depth = CALL_DEPTH.with(|c| c.get()) + 1;
        if depth > RECURSION_LIMIT {
            return Err(Thrown {
                value: IbValue::Error {
                    class: "RecursionError".to_string(),
                    message: "maximum recursion depth exceeded".to_string(),
                },
                pos: None,
            });
        }
        let _guard = DepthGuard(CALL_DEPTH.with(|c| c.get()));
        CALL_DEPTH.with(|c| c.set(depth));
        // 新作用域：parent = enclosing[闭包捕获，嵌套函数访问 outer 局部] 或
        // global[顶层函数，使函数体可访问全局函数/变量——递归 + 读全局]
        let parent = f.enclosing.clone().unwrap_or_else(|| global.clone());
        let mut call_env = Environment::new(Some(parent));
        // nonlocal 名注入（闭包赋值重定向外层作用域）
        call_env
            .nonlocals
            .extend(f.nonlocals.iter().cloned());
        let call_env = Rc::new(RefCell::new(call_env));
        for (i, arg) in args.iter().enumerate() {
            if let Some(param) = f.params.get(i) {
                call_env.borrow_mut().set(param, arg.clone());
            }
        }
        let flow = self.exec_body(&call_env, &f.body, output)?;
        Ok(match flow {
            Flow::Return(v) => v,
            _ => IbValue::None_,
        })
    }

    fn call_method(&self, obj: &IbValue, method: &str, args: Vec<IbValue>) -> Result<IbValue, Thrown> {
        // Optional 面：is_some/is_none = 任意值的全局方法（值非 None_ = some；
        // Python 契约：Optional 包装幂等——裸值同样可查）
        if method == "is_some" {
            return Ok(IbValue::Bool(!matches!(obj, IbValue::None_)));
        }
        if method == "is_none" {
            return Ok(IbValue::Bool(matches!(obj, IbValue::None_)));
        }
        // unwrap（Optional 面：有值 = 值本身；空值 = 错误[Python 契约：
        // 空 Optional 解包 = 异常]）
        if method == "unwrap" {
            return match obj {
                IbValue::None_ => Err(runtime_error(
                    "AttributeError",
                    "unwrap on empty optional",
                )),
                v => Ok(v.clone()),
            };
        }
        // to_list（Optional 容器解包——值面直返；Python Optional 包装
        // 解包同语义：有值 = 值本身，空值 = 错误）
        if method == "to_list" {
            return match obj {
                IbValue::None_ => Err(runtime_error(
                    "AttributeError",
                    "to_list on empty optional",
                )),
                v => Ok(v.clone()),
            };
        }
        // or_else（Optional 面：有值 = 值；空值 = 默认参——Python 契约）
        if method == "or_else" {
            return match obj {
                IbValue::None_ => match args.first() {
                    Some(d) => Ok(d.clone()),
                    None => Ok(IbValue::None_),
                },
                v => Ok(v.clone()),
            };
        }
        // next（Optional 迭代面：有值 = 值；空值 = 错误
        // [Python 契约：空 Optional next/迭代 = RUN_ATTRIBUTE_ERROR]）
        if method == "next" {
            return match obj {
                IbValue::None_ => Err(runtime_error(
                    "AttributeError",
                    "next on empty optional",
                )),
                v => Ok(v.clone()),
            };
        }
        Ok(match obj {
            // Rust 原生 KB 值——方法面经 kb::dispatch（治理门 + 确定性序）
            IbValue::Knowledge(kb) => crate::kb::dispatch(kb, method, &args),
            // vector 值——方法面（dim/dot/norm/cosine/scale/add/sub/cast_to；
            // 修改操作返回新 vector，不可变值语义）
            IbValue::Vector(v) => match method {
                "dim" => IbValue::Int(v.len() as i64),
                "dot" => {
                    let [IbValue::Vector(o)] = args.as_slice() else {
                        return Ok(IbValue::None_);
                    };
                    if v.len() != o.len() {
                        return Ok(IbValue::None_);
                    }
                    IbValue::Float(v.iter().zip(o.iter()).map(|(a, b)| a * b).sum())
                }
                "norm" => {
                    IbValue::Float(v.iter().map(|x| x * x).sum::<f64>().sqrt())
                }
                "cosine" => {
                    let [IbValue::Vector(o)] = args.as_slice() else {
                        return Ok(IbValue::None_);
                    };
                    if v.len() != o.len() {
                        return Ok(IbValue::None_);
                    }
                    let na: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
                    let nb: f64 = o.iter().map(|x| x * x).sum::<f64>().sqrt();
                    if na == 0.0 || nb == 0.0 {
                        // 零范数 = 余弦未定义（fail-fast 面——错误面登记 = None_）
                        return Ok(IbValue::None_);
                    }
                    IbValue::Float(
                        v.iter().zip(o.iter()).map(|(a, b)| a * b).sum::<f64>()
                            / (na * nb),
                    )
                }
                "scale" => match args.first() {
                    Some(IbValue::Int(k)) => IbValue::Vector(
                        v.iter().map(|x| x * (*k as f64)).collect(),
                    ),
                    Some(IbValue::Float(k)) => {
                        IbValue::Vector(v.iter().map(|x| x * k).collect())
                    }
                    _ => return Err(runtime_error("AttributeError", "attribute not found")),
                },
                "add" | "sub" => {
                    let [IbValue::Vector(o)] = args.as_slice() else {
                        return Ok(IbValue::None_);
                    };
                    if v.len() != o.len() {
                        return Ok(IbValue::None_);
                    }
                    let out: Vec<f64> = if method == "add" {
                        v.iter().zip(o.iter()).map(|(a, b)| a + b).collect()
                    } else {
                        v.iter().zip(o.iter()).map(|(a, b)| a - b).collect()
                    };
                    IbValue::Vector(out)
                }
                // 注：cast_to 目标 = 类对象（`v.cast_to(str)` 的 str 经 VM 类型名
                // 解析为 class——值域无类对象面，执行面不可达 = 3b 类型面职责；
                // 用户调用 cast_to("str") = 非法 IBCI[Python 参考 fail-fast 实证]
                _ => return Err(runtime_error("AttributeError", "attribute not found")),
            },
            // 宿主对象——委托 Python 对象方法（host service 桥接）
            IbValue::Host(pyobj) => self.call_host_method(pyobj, method, args),
            IbValue::List(l) => match method {
                "append" => {
                    if let Some(v) = args.first() {
                        l.borrow_mut().push(v.clone());
                    }
                    IbValue::None_
                }
                "len" => IbValue::Int(l.borrow().len() as i64),
                "index" => {
                    let items = l.borrow().clone();
                    if let Some(v) = args.first() {
                        items
                            .iter()
                            .position(|x| x == v)
                            .map(|i| IbValue::Int(i as i64))
                            .unwrap_or(IbValue::None_)
                    } else {
                        IbValue::None_
                    }
                }
                "pop" => {
                    let mut m = l.borrow_mut();
                    m.pop().unwrap_or(IbValue::None_)
                }
                // insert(index, value)——负索引/越界 = 端点钳制（Python 契约）
                "insert" => {
                    let items = l.borrow().clone();
                    if let (Some(IbValue::Int(i)), Some(v)) = (args.first(), args.get(1)) {
                        let mut m = l.borrow_mut();
                        let len = m.len() as i64;
                        let ix = {
                            let raw = if *i < 0 { (len + i).max(0) } else { *i };
                            (raw as usize).min(m.len())
                        };
                        m.insert(ix, v.clone());
                    }
                    IbValue::None_
                }
                // remove(value)——移除首个相等元素（Python 契约：原地修改，
                // 无返回值；未找到 = ValueError[登记——语料面无探针]）
                "remove" => {
                    if let Some(v) = args.first() {
                        let mut m = l.borrow_mut();
                        if let Some(ix) = m.iter().position(|x| x == v) {
                            m.remove(ix);
                        }
                    }
                    IbValue::None_
                }
                _ => return Err(runtime_error("AttributeError", "attribute not found")),
            },
            IbValue::Dict(d) => match method {
                "get" => {
                    // get(key) / get(key, default)
                    let items = d.borrow().clone();
                    if let Some(k) = args.first() {
                        let found = items.iter().find(|(dk, _)| dk == k).map(|(_, v)| v.clone());
                        match found {
                            Some(v) => v,
                            None => args.get(1).cloned().unwrap_or(IbValue::None_),
                        }
                    } else {
                        IbValue::None_
                    }
                }
                "keys" => {
                    let items = d.borrow().clone();
                    let keys: Vec<IbValue> = items.into_iter().map(|(k, _)| k).collect();
                    IbValue::list_new(keys)
                }
                "values" => {
                    let items = d.borrow().clone();
                    let vals: Vec<IbValue> = items.into_iter().map(|(_, v)| v).collect();
                    IbValue::list_new(vals)
                }
                "len" => IbValue::Int(d.borrow().len() as i64),
                _ => return Err(runtime_error("AttributeError", "attribute not found")),
            },
            IbValue::Str(s) => {
                match method {
                    "split" => {
                        // split(sep)
                        let sep = args
                            .first()
                            .and_then(|a| match a {
                                IbValue::Str(x) => Some(x.clone()),
                                _ => None,
                            })
                            .unwrap_or_default();
                        let parts: Vec<IbValue> = if sep.is_empty() {
                            s.chars().map(|c| IbValue::Str(c.to_string())).collect()
                        } else {
                            s.split(&sep)
                                .map(|p| IbValue::Str(p.to_string()))
                                .collect()
                        };
                        return Ok(IbValue::list_new(parts));
                    }
                    "find" => {
                        let sub = args.first().and_then(|a| match a {
                            IbValue::Str(x) => Some(x.clone()),
                            _ => None,
                        });
                        return Ok(match sub {
                            Some(sub) => match s.find(&sub) {
                                Some(i) => IbValue::Int(i as i64),
                                None => IbValue::Int(-1),
                            },
                            None => IbValue::Int(-1),
                        });
                    }
                    "rfind" => {
                        let sub = args.first().and_then(|a| match a {
                            IbValue::Str(x) => Some(x.clone()),
                            _ => None,
                        });
                        // rfind 从尾部扫描（Python rfind 对等——find 反向遍历）
                        return Ok(match sub {
                            Some(sub) => {
                                if sub.is_empty() {
                                    return Ok(IbValue::Int(s.len() as i64));
                                }
                                let mut i = s.len().saturating_sub(sub.len()) as i64;
                                let mut found = -1;
                                while i >= 0 {
                                    if s[i as usize..].starts_with(&sub) {
                                        found = i;
                                        break;
                                    }
                                    i -= 1;
                                }
                                IbValue::Int(found)
                            }
                            None => IbValue::Int(-1),
                        });
                    }
                    "count" => {
                        let sub = args.first().and_then(|a| match a {
                            IbValue::Str(x) => Some(x.clone()),
                            _ => None,
                        });
                        return Ok(match sub {
                            Some(sub) if !sub.is_empty() => IbValue::Int(
                                s.match_indices(&sub).count() as i64,
                            ),
                            _ => IbValue::Int(0),
                        });
                    }
                    "contains" => {
                        let sub = args.first().and_then(|a| match a {
                            IbValue::Str(x) => Some(x.clone()),
                            _ => None,
                        });
                        return Ok(IbValue::Bool(match sub {
                            Some(sub) => s.contains(&sub),
                            None => false,
                        }));
                    }
                    "is_empty" => {
                        return Ok(IbValue::Bool(s.trim().is_empty()));
                    }
                    "startswith" | "endswith" => {
                        let pre = args.first().and_then(|a| match a {
                            IbValue::Str(x) => Some(x.clone()),
                            _ => None,
                        });
                        return Ok(IbValue::Bool(match pre {
                            Some(pre) => {
                                if method == "startswith" {
                                    s.starts_with(&pre)
                                } else {
                                    s.ends_with(&pre)
                                }
                            }
                            None => false,
                        }));
                    }
                    "replace" => {
                        let old = args.first().and_then(|a| match a {
                            IbValue::Str(x) => Some(x.clone()),
                            _ => None,
                        });
                        let new = args.get(1).and_then(|a| match a {
                            IbValue::Str(x) => Some(x.clone()),
                            _ => None,
                        });
                        return Ok(match (old, new) {
                            (Some(old), Some(new)) => {
                                IbValue::Str(s.replace(&old, &new))
                            }
                            _ => IbValue::Str(s.clone()),
                        });
                    }
                    "join" => {
                        // join(list) = 本串作分隔符连接元素（Python str.join 对等）
                        let parts: Vec<String> = match args.first() {
                            Some(IbValue::List(l)) => {
                                let v = l.borrow();
                                v.iter().map(|x| x.repr()).collect()
                            }
                            _ => Vec::new(),
                        };
                        return Ok(IbValue::Str(parts.join(s.as_str())));
                    }
                    "format" => {
                        // format(arg) = {} 占位符替换（Python str.format 简化对等）
                        let arg = match args.first() {
                            Some(a) => a.repr(),
                            None => String::new(),
                        };
                        let mut out = String::new();
                        let mut rest = s.as_str();
                        while let Some(i) = rest.find("{}") {
                            out.push_str(&rest[..i]);
                            out.push_str(&arg);
                            rest = &rest[i + 2..];
                        }
                        out.push_str(rest);
                        return Ok(IbValue::Str(out));
                    }
                    _ => {}
                }
                let r = match method {
                    "upper" => s.to_uppercase(),
                    "lower" => s.to_lowercase(),
                    "strip" => s.trim().to_string(),
                    _ => return Err(runtime_error("AttributeError", "attribute not found")),
                };
                IbValue::Str(r)
            }
            _ => {
                // 未知对象类型方法 = 环境错误（Python 契约：AttributeError →
                // RUN_ATTRIBUTE_ERROR）
                return Err(runtime_error("AttributeError", "attribute not found"))
            }
        })
    }

    /// 宿主对象方法委托（KB 服务——经 host service 桥接调 Python 对象方法）。
    fn call_host_method(&self, pyobj: &Py<PyAny>, method: &str, args: Vec<IbValue>) -> IbValue {
        Python::with_gil(|py| -> PyResult<IbValue> {
            let obj = pyobj.bind(py);
            // 参数转换（Rust IbValue → Python 对象）
            let py_args: Vec<PyObject> = args.iter().map(|a| to_py(py, a)).collect();
            let tuple = PyTuple::new(py, &py_args)?;
            let res = obj.call_method(method, tuple, None)?;
            // 结果转换（Python 对象 → Rust IbValue）
            Ok(from_py(py, &res))
        })
        .unwrap_or(IbValue::None_)
    }

    /// 调宿主函数对象（如 from meta import quote 的 quote）——委托 Python 调用。
    fn call_host_function(&self, pyobj: &Py<PyAny>, args: Vec<IbValue>) -> IbValue {
        Python::with_gil(|py| -> PyResult<IbValue> {
            let obj = pyobj.bind(py);
            let py_args: Vec<PyObject> = args.iter().map(|a| to_py(py, a)).collect();
            let tuple = PyTuple::new(py, &py_args)?;
            let res = obj.call(tuple, None)?;
            Ok(from_py(py, &res))
        })
        .unwrap_or(IbValue::None_)
    }
}

/// Rust IbValue → Python 对象（host service 桥接参数转换）。
fn to_py(py: Python<'_>, v: &IbValue) -> PyObject {
    use pyo3::IntoPy;
    match v {
        IbValue::Int(i) => (*i).into_py(py),
        IbValue::Float(f) => (*f).into_py(py),
        IbValue::Str(s) => s.clone().into_py(py),
        IbValue::Bool(b) => (*b).into_py(py),
        IbValue::None_ => py.None(),
        IbValue::List(l) => {
            let items: Vec<PyObject> = l.borrow().iter().map(|x| to_py(py, x)).collect();
            PyList::new(py, items).unwrap().into_py(py)
        }
        IbValue::Dict(d) => {
            let dict = PyDict::new(py);
            for (k, val) in d.borrow().iter() {
                let _ = dict.set_item(to_py(py, k), to_py(py, val));
            }
            dict.into_py(py)
        }
        // quoted 值跨边界 = 完整源串（同 to_native 边界拆箱契约）
        IbValue::Quoted { source } => source.clone().into_py(py),
        // 原生 meta 函数引用 / 原生 KB 值 / vector 值 / 函数值不经桥接
        // （vector 是值语义一等类型，不可拆箱——同 to_native 显式违约契约）
        IbValue::MetaFn(_) | IbValue::Knowledge(_) | IbValue::Vector(_)
        | IbValue::Function(_) | IbValue::Error { .. } => py.None(),
        IbValue::Host(h) => h.clone().into_py(py),
    }
}

/// Python 对象 → Rust IbValue（host service 桥接结果转换）。
fn from_py(py: Python<'_>, obj: &Bound<'_, PyAny>) -> IbValue {
    // None
    if obj.is_none() {
        return IbValue::None_;
    }
    // bool（先于 int——bool 是 int 子类）
    if let Ok(b) = obj.extract::<bool>() {
        return IbValue::Bool(b);
    }
    // int
    if let Ok(i) = obj.extract::<i64>() {
        return IbValue::Int(i);
    }
    // float
    if let Ok(f) = obj.extract::<f64>() {
        return IbValue::Float(f);
    }
    // str
    if let Ok(s) = obj.extract::<String>() {
        return IbValue::Str(s);
    }
    // list
    if let Ok(l) = obj.extract::<Vec<PyObject>>() {
        let items: Vec<IbValue> = l
            .iter()
            .map(|x| from_py(py, x.bind(py)))
            .collect();
        return IbValue::list_new(items);
    }
    // dict
    if let Ok(d) = obj.downcast::<PyDict>() {
        let mut pairs = Vec::new();
        for (k, v) in d.iter() {
            pairs.push((from_py(py, &k), from_py(py, &v)));
        }
        return IbValue::dict_new(pairs);
    }
    // 其他（knowledge 对象等）= 宿主对象（克隆 Bound 取所有权）
    IbValue::Host(obj.clone().unbind())
}

fn const_to_value(c: &ConstVal) -> IbValue {
    match c {
        ConstVal::Int(i) => IbValue::Int(*i),
        ConstVal::Float(f) => IbValue::Float(*f),
        ConstVal::Str(s) => IbValue::Str(s.clone()),
        ConstVal::Bool(b) => IbValue::Bool(*b),
        ConstVal::None_ => IbValue::None_,
    }
}

fn floor_div(l: &IbValue, r: &IbValue) -> Result<IbValue, Thrown> {
    match (l.as_num(), r.as_num()) {
        (Some((a, ai)), Some((b, bi))) => {
            if b == 0.0 {
                // 除零 = 环境错误（Python 契约：ZeroDivisionError →
                // RUN_DIVISION_BY_ZERO；int/float 同面）
                return Err(runtime_error("ZeroDivisionError", "division by zero"));
            }
            let res = (a / b).floor();
            if ai && bi {
                Ok(IbValue::Int(res as i64))
            } else {
                Ok(IbValue::Float(res))
            }
        }
        _ => Ok(IbValue::None_),
    }
}

fn modulo(l: &IbValue, r: &IbValue) -> Result<IbValue, Thrown> {
    match (l.as_num(), r.as_num()) {
        (Some((a, ai)), Some((b, bi))) => {
            if b == 0.0 {
                return Err(runtime_error("ZeroDivisionError", "division by zero"));
            }
            let res = a.rem_euclid(b);
            if ai && bi {
                Ok(IbValue::Int(res as i64))
            } else {
                Ok(IbValue::Float(res))
            }
        }
        _ => Ok(IbValue::None_),
    }
}

/// 位运算（int/bool 面：| & ^——操作数须为 int/bool[数值]；bool+bool =
/// bool 结果[Python 契约]，否则 int）。
fn bitwise(l: &IbValue, op: &str, r: &IbValue) -> IbValue {
    let both_bool = matches!(l, IbValue::Bool(_)) && matches!(r, IbValue::Bool(_));
    let (Some((a, _)), Some((b, _))) = (l.as_num(), r.as_num()) else {
        return IbValue::None_;
    };
    let ai = a as i64;
    let bi = b as i64;
    let res = match op {
        "|" => ai | bi,
        "&" => ai & bi,
        "^" => ai ^ bi,
        _ => 0,
    };
    if both_bool {
        IbValue::Bool(res != 0)
    } else {
        IbValue::Int(res)
    }
}

fn pow_op(l: &IbValue, r: &IbValue) -> IbValue {
    match (l.as_num(), r.as_num()) {
        (Some((a, ai)), Some((b, bi))) => {
            let res = a.powf(b);
            if ai && bi && res.fract() == 0.0 {
                IbValue::Int(res as i64)
            } else {
                IbValue::Float(res)
            }
        }
        _ => IbValue::None_,
    }
}

fn subscript_get(base: &IbValue, key: &IbValue) -> Result<IbValue, Thrown> {
    // 负索引归一（Python 契约：l[-1] = 末元素）
    let norm_idx = |v: usize, i: i64| -> Option<usize> {
        if i < 0 {
            Some((v as i64 + i).max(0) as usize)
        } else {
            Some(i as usize)
        }
    };
    match (base, key) {
        (IbValue::List(l), IbValue::Int(i)) => {
            let v = l.borrow();
            match norm_idx(v.len(), *i).and_then(|ix| v.get(ix).cloned()) {
                Some(item) => Ok(item),
                // 越界 = 环境错误（Python 契约：IndexError → RUN_INDEX_ERROR）
                None => Err(runtime_error("IndexError", "index out of range")),
            }
        }
        (IbValue::Dict(d), k) => d
            .borrow()
            .iter()
            .find(|(dk, _)| dk == k)
            .map(|(_, v)| v.clone())
            .ok_or_else(|| runtime_error("KeyError", "key not found")),
        (IbValue::Str(s), IbValue::Int(i)) => {
            let chars: Vec<char> = s.chars().collect();
            match norm_idx(chars.len(), *i).and_then(|ix| chars.get(ix)) {
                Some(c) => Ok(IbValue::Str(c.to_string())),
                None => Err(runtime_error("IndexError", "index out of range")),
            }
        }
        // vector 下标：元素 float（同 __getitem__）
        (IbValue::Vector(v), IbValue::Int(i)) => match norm_idx(v.len(), *i).and_then(|ix| v.get(ix)) {
            Some(f) => Ok(IbValue::Float(*f)),
            None => Err(runtime_error("IndexError", "index out of range")),
        },
        _ => Err(runtime_error("TypeError", "object is not subscriptable")),
    }
}

/// 列表切片 x[lower:upper]（Python 语义：[lower, upper)；lower/upper 缺省 = 端点）。
fn slice_indices(len: i64, lower: Option<&IbValue>, upper: Option<&IbValue>, step: i64) -> Vec<usize> {
    // Python 切片语义（含负索引归一 + 负 step 反向）
    fn norm(i: i64, len: i64) -> i64 {
        if i < 0 {
            (len + i).max(0)
        } else {
            i.min(len)
        }
    }
    let lo = match lower {
        Some(IbValue::Int(i)) => norm(*i, len),
        _ => if step > 0 { 0 } else { len - 1 },
    };
    let hi = match upper {
        Some(IbValue::Int(i)) => norm(*i, len),
        _ => if step > 0 { len } else { -1 },
    };
    let mut idx = Vec::new();
    if step > 0 {
        let mut i = lo;
        while i < hi {
            idx.push(i as usize);
            i += step;
        }
    } else {
        let mut i = lo;
        while i > hi {
            idx.push(i as usize);
            i += step;
        }
    }
    idx
}

fn subscript_slice(
    base: &IbValue,
    lower: Option<&IbValue>,
    upper: Option<&IbValue>,
    step: Option<&IbValue>,
) -> IbValue {
    let step_v = match step {
        Some(IbValue::Int(i)) => *i,
        Some(_) => 1, // 非 int step = 保守 step 1（Python TypeError 角——登记）
        None => 1,
    };
    if step_v == 0 {
        return IbValue::None_; // step 0 = 保守 None（登记角）
    }
    match base {
        // 字符串切片 = 新字符串（Python 契约：str slice returns str）
        IbValue::Str(s) => {
            let chars: Vec<char> = s.chars().collect();
            let idx = slice_indices(chars.len() as i64, lower, upper, step_v);
            let out: String = idx.iter().map(|&i| chars[i]).collect();
            IbValue::Str(out)
        }
        IbValue::List(l) => {
            let v = l.borrow();
            let idx = slice_indices(v.len() as i64, lower, upper, step_v);
            let items: Vec<IbValue> = idx.iter().map(|&i| v[i].clone()).collect();
            drop(v);
            IbValue::list_new(items)
        }
        _ => IbValue::None_,
    }
}

fn assign_subscript(base: &IbValue, key: &IbValue, val: IbValue) {
    if let IbValue::Dict(d) = base {
        let mut m = d.borrow_mut();
        if let Some(pair) = m.iter_mut().find(|(dk, _)| dk == key) {
            pair.1 = val;
        } else {
            m.push((key.clone(), val));
        }
    }
}

// --------------------------------------------------------------------------- //
// 入口：artifact JSON → 执行 → 数据面
// --------------------------------------------------------------------------- //
use crate::deserializer::deserialize_module;

/// artifact JSON → 执行 → 数据面（print 输出列表）。bridge = host service 桥接
///（KB 操作经此委托；None = 无宿主服务，非 KB 语料面）。
pub fn run_artifact(artifact_json: &str, bridge: Option<Py<PyAny>>) -> Result<Vec<String>, String> {
    let module = match deserialize_module(artifact_json) {
        Some(m) => m,
        None => return Ok(Vec::new()),
    };
    let interp = match bridge {
        Some(b) => Interpreter::with_bridge(b),
        None => Interpreter::new(),
    };
    // 未捕获异常 = 执行错误（消息面——跨线程边界 Send 约束：Thrown 含 Rc 非
    // Send，于模块边界降级为消息）
    interp.run_module(&module).map_err(|t| {
        match t.pos {
            Some((line, col)) => format!(
                "IBCI: uncaught exception: {}@{}:{}",
                t.value.repr(),
                line,
                col
            ),
            None => format!("IBCI: uncaught exception: {}", t.value.repr()),
        }
    })
}
