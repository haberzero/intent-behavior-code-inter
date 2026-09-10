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
//!   `4.0`；list `[e, e]`；dict `{"k": v}`；str 原样）。KB 语料面（knowledge()
//!   宿主服务）= 后续增量（需宿主环境）。
//!
//! 差分门：数据面（Rust 执行 print 输出）== Python 执行 print 输出（非 KB 语料）。

use crate::parser::{ConstVal, Expr, Module, Stmt};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString, PyTuple};
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
    /// 宿主对象（Python 对象引用——KB 服务经 host service 桥接委托）。
    Host(Py<PyAny>),
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
            IbValue::Host(_) => true,
        }
    }
    fn as_num(&self) -> Option<(f64, bool)> {
        match self {
            IbValue::Int(i) => Some((*i as f64, true)),
            IbValue::Float(f) => Some((*f, false)),
            _ => None,
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
#[derive(Debug, Clone)]
pub struct Environment {
    vars: HashMap<String, IbValue>,
    functions: HashMap<String, Function>,
    parent: Option<Box<Environment>>,
}

#[derive(Debug, Clone)]
pub struct Function {
    pub name: String,
    pub params: Vec<String>,
    pub body: Vec<Stmt>,
}

impl Environment {
    fn new(parent: Option<Box<Environment>>) -> Environment {
        Environment {
            vars: HashMap::new(),
            functions: HashMap::new(),
            parent,
        }
    }
    /// 全局环境（作用域链根）。
    fn global(&self) -> &Environment {
        match &self.parent {
            Some(p) => p.global(),
            None => self,
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
            Some(p) => p.get(name),
            None => None,
        }
    }
    fn define_function(&mut self, f: Function) {
        self.functions.insert(f.name.clone(), f);
    }
    fn get_function(&self, name: &str) -> Option<Function> {
        if let Some(f) = self.functions.get(name) {
            return Some(f.clone());
        }
        match &self.parent {
            Some(p) => p.get_function(name),
            None => None,
        }
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
    pub fn run_module(&self, module: &Module) -> Vec<String> {
        let mut output: Vec<String> = Vec::new();
        let global = Environment::new(None);
        let mut env = global;
        for stmt in &module.body {
            let flow = self.exec_stmt(&mut env, stmt, &mut output);
            if !matches!(flow, Flow::Next) {
                break;
            }
        }
        output
    }

    fn exec_stmt(
        &self,
        env: &mut Environment,
        stmt: &Stmt,
        output: &mut Vec<String>,
    ) -> Flow {
        match stmt {
            Stmt::Assign { targets, value, .. } => {
                let v = value.as_ref().map(|e| self.eval_expr(env, e, output));
                if let Some(target) = targets.first() {
                    match target {
                        Expr::Name { id, .. } => {
                            if let Some(val) = &v {
                                env.set(id, val.clone());
                            }
                        }
                        Expr::Subscript { value, slice, .. } => {
                            let base = self.eval_expr(env, value, output);
                            let key = self.eval_expr(env, slice, output);
                            if let Some(val) = &v {
                                assign_subscript(&base, &key, val.clone());
                            }
                        }
                        _ => {}
                    }
                }
                Flow::Next
            }
            Stmt::ExprStmt { value, .. } => {
                self.eval_expr(env, value, output);
                Flow::Next
            }
            Stmt::If { test, body, orelse, .. } => {
                let cond = self.eval_expr(env, test, output).truthy();
                if cond {
                    self.exec_body(env, body, output)
                } else {
                    self.exec_body(env, orelse, output)
                }
            }
            Stmt::For { target, iter, body, orelse, .. } => {
                let items = self.eval_iter(env, iter, output);
                let mut ran_else = false;
                for item in items {
                    let name = match target {
                        Expr::Name { id, .. } => id.clone(),
                        _ => continue,
                    };
                    env.set(&name, item);
                    match self.exec_body(env, body, output) {
                        Flow::Break => {
                            ran_else = false;
                            break;
                        }
                        Flow::Return(v) => return Flow::Return(v),
                        _ => {}
                    }
                }
                if !ran_else && !orelse.is_empty() {
                    self.exec_body(env, orelse, output)
                } else {
                    Flow::Next
                }
            }
            Stmt::While { test, body, orelse, .. } => {
                let mut ran_else = false;
                while self.eval_expr(env, test, output).truthy() {
                    match self.exec_body(env, body, output) {
                        Flow::Break => {
                            ran_else = false;
                            break;
                        }
                        Flow::Continue => continue,
                        Flow::Return(v) => return Flow::Return(v),
                        _ => {}
                    }
                }
                if !ran_else && !orelse.is_empty() {
                    self.exec_body(env, orelse, output)
                } else {
                    Flow::Next
                }
            }
            Stmt::FunctionDef { name, args, body, .. } => {
                let params: Vec<String> = args.iter().map(|a| a.arg.clone()).collect();
                env.define_function(Function {
                    name: name.clone(),
                    params,
                    body: body.clone(),
                });
                Flow::Next
            }
            Stmt::Return { value, .. } => {
                let v = match value {
                    Some(e) => self.eval_expr(env, e, output),
                    None => IbValue::None_,
                };
                Flow::Return(v)
            }
            Stmt::Break { .. } => Flow::Break,
            Stmt::Continue { .. } => Flow::Continue,
            Stmt::Pass { .. } => Flow::Next,
            Stmt::Try { body, .. } | Stmt::ClassDef { body, .. } => {
                self.exec_body(env, body, output)
            }
        }
    }

    fn exec_body(
        &self,
        env: &mut Environment,
        body: &[Stmt],
        output: &mut Vec<String>,
    ) -> Flow {
        for s in body {
            let flow = self.exec_stmt(env, s, output);
            if !matches!(flow, Flow::Next) {
                return flow;
            }
        }
        Flow::Next
    }

    fn eval_expr(&self, env: &mut Environment, expr: &Expr, output: &mut Vec<String>) -> IbValue {
        match expr {
            Expr::Constant { value, .. } => const_to_value(value),
            Expr::Name { id, .. } => match env.get(id) {
                Some(v) => v,
                None => IbValue::None_,
            },
            Expr::BinOp { left, op, right, .. } => {
                let l = self.eval_expr(env, left, output);
                let r = self.eval_expr(env, right, output);
                self.binop(&l, op, &r)
            }
            Expr::UnaryOp { op, operand, .. } => {
                let v = self.eval_expr(env, operand, output);
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
                        let x = self.eval_expr(env, v, output);
                        if !x.truthy() {
                            return x; // 短路：返回第一个假值
                        }
                        result = x;
                    }
                    result
                } else {
                    let mut result = IbValue::Bool(false);
                    for v in values {
                        let x = self.eval_expr(env, v, output);
                        if x.truthy() {
                            return x; // 短路：返回第一个真值
                        }
                        result = x;
                    }
                    result
                }
            }
            Expr::Compare { left, ops, comparators, .. } => {
                let l = self.eval_expr(env, left, output);
                if let (Some(op), Some(r)) = (ops.first(), comparators.first()) {
                    let rv = self.eval_expr(env, r, output);
                    self.compare(&l, op, &rv)
                } else {
                    IbValue::Bool(false)
                }
            }
            Expr::Call { func, args, .. } => {
                // func: &Box<Expr> → as_ref() 得 &Expr
                match func.as_ref() {
                    Expr::Attribute { value, attr, .. } => {
                        let obj = self.eval_expr(env, value, output);
                        let attr = attr.clone();
                        let arg_vals: Vec<IbValue> =
                            args.iter().map(|a| self.eval_expr(env, a, output)).collect();
                        self.call_method(&obj, &attr, arg_vals)
                    }
                    _ => {
                        let func_name = match func.as_ref() {
                            Expr::Name { id, .. } => id.clone(),
                            _ => String::new(),
                        };
                        let arg_vals: Vec<IbValue> =
                            args.iter().map(|a| self.eval_expr(env, a, output)).collect();
                        self.call_function(env, &func_name, arg_vals, output)
                    }
                }
            }
            Expr::List { elts, .. } => {
                let items: Vec<IbValue> =
                    elts.iter().map(|e| self.eval_expr(env, e, output)).collect();
                IbValue::list_new(items)
            }
            Expr::Dict { keys, values, .. } => {
                let pairs: Vec<(IbValue, IbValue)> = keys
                    .iter()
                    .zip(values.iter())
                    .map(|(k, v)| {
                        (self.eval_expr(env, k, output), self.eval_expr(env, v, output))
                    })
                    .collect();
                IbValue::dict_new(pairs)
            }
            Expr::Attribute { value, .. } => self.eval_expr(env, value, output),
            Expr::Subscript { value, slice, .. } => {
                let base = self.eval_expr(env, value, output);
                let key = self.eval_expr(env, slice, output);
                subscript_get(&base, &key)
            }
            Expr::IfExp { test, body, orelse, .. } => {
                let cond = self.eval_expr(env, test, output).truthy();
                if cond {
                    self.eval_expr(env, body, output)
                } else {
                    self.eval_expr(env, orelse, output)
                }
            }
            Expr::Lambda { .. } => IbValue::None_,
        }
    }

    fn eval_iter(
        &self,
        env: &mut Environment,
        iter: &Expr,
        output: &mut Vec<String>,
    ) -> Vec<IbValue> {
        let v = self.eval_expr(env, iter, output);
        match v {
            IbValue::List(l) => l.borrow().clone(),
            _ => Vec::new(),
        }
    }

    fn binop(&self, l: &IbValue, op: &str, r: &IbValue) -> IbValue {
        if let (IbValue::Str(a), IbValue::Str(b)) = (l, r) {
            if op == "+" {
                return IbValue::Str(format!("{}{}", a, b));
            }
        }
        if let (IbValue::List(a), IbValue::List(b)) = (l, r) {
            if op == "+" {
                let mut merged = a.borrow().clone();
                merged.extend(b.borrow().clone());
                return IbValue::list_new(merged);
            }
        }
        match op {
            "+" => num_result(l, r, |a, b| a + b),
            "-" => num_result(l, r, |a, b| a - b),
            "*" => num_result(l, r, |a, b| a * b),
            "/" => floor_div(l, r),
            "//" => floor_div(l, r),
            "%" => modulo(l, r),
            "**" => pow_op(l, r),
            _ => IbValue::None_,
        }
    }

    fn compare(&self, l: &IbValue, op: &str, r: &IbValue) -> IbValue {
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
        IbValue::Bool(b)
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
                (IbValue::Str(a), IbValue::Str(b)) => {
                    a.partial_cmp(b).map(|o| o as i64).unwrap_or(0)
                }
                (IbValue::Bool(a), IbValue::Bool(b)) => (*a as i64) - (*b as i64),
                _ => 0,
            },
        }
    }

    fn call_function(
        &self,
        env: &mut Environment,
        name: &str,
        args: Vec<IbValue>,
        output: &mut Vec<String>,
    ) -> IbValue {
        match name {
            "print" => {
                if let Some(v) = args.first() {
                    output.push(v.repr());
                }
                IbValue::None_
            }
            "len" => match args.first() {
                Some(IbValue::List(l)) => IbValue::Int(l.borrow().len() as i64),
                Some(IbValue::Str(s)) => IbValue::Int(s.len() as i64),
                Some(IbValue::Dict(d)) => IbValue::Int(d.borrow().len() as i64),
                _ => IbValue::Int(0),
            },
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
            _ => {
                if let Some(f) = env.get_function(name) {
                    // 全局环境（函数定义处——使函数体可访问全局函数[递归]）
                    let global = env.global().clone();
                    self.call_user_function(&f, args, output, &global)
                } else {
                    IbValue::None_
                }
            }
        }
    }

    /// knowledge() → 经 host service 桥接创建 Python knowledge 对象。
    fn call_knowledge(&self) -> IbValue {
        let bridge = match &self.bridge {
            Some(b) => b.clone(),
            None => return IbValue::None_,
        };
        Python::with_gil(|py| -> PyResult<IbValue> {
            let b = bridge.bind(py);
            let kb = b.call_method0("create_knowledge")?;
            Ok(IbValue::Host(kb.unbind()))
        })
        .unwrap_or(IbValue::None_)
    }

    fn call_user_function(
        &self,
        f: &Function,
        args: Vec<IbValue>,
        output: &mut Vec<String>,
        global: &Environment,
    ) -> IbValue {
        // 新作用域（父 = 全局环境，使函数体内可访问全局函数[递归]）
        let mut call_env = Environment::new(Some(Box::new(global.clone())));
        for (i, arg) in args.iter().enumerate() {
            if let Some(param) = f.params.get(i) {
                call_env.set(param, arg.clone());
            }
        }
        let flow = self.exec_body(&mut call_env, &f.body, output);
        match flow {
            Flow::Return(v) => v,
            _ => IbValue::None_,
        }
    }

    fn call_method(&self, obj: &IbValue, method: &str, args: Vec<IbValue>) -> IbValue {
        match obj {
            // 宿主对象（KB 服务）——委托 Python 对象方法（host service 桥接）
            IbValue::Host(pyobj) => self.call_host_method(pyobj, method, args),
            IbValue::List(l) => match method {
                "append" => {
                    if let Some(v) = args.first() {
                        l.borrow_mut().push(v.clone());
                    }
                    IbValue::None_
                }
                "len" => IbValue::Int(l.borrow().len() as i64),
                _ => IbValue::None_,
            },
            IbValue::Str(s) => {
                let r = match method {
                    "upper" => s.to_uppercase(),
                    "lower" => s.to_lowercase(),
                    "strip" => s.trim().to_string(),
                    _ => s.clone(),
                };
                IbValue::Str(r)
            }
            _ => IbValue::None_,
        }
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

fn floor_div(l: &IbValue, r: &IbValue) -> IbValue {
    match (l.as_num(), r.as_num()) {
        (Some((a, ai)), Some((b, bi))) => {
            if b == 0.0 {
                return IbValue::None_;
            }
            let res = (a / b).floor();
            if ai && bi {
                IbValue::Int(res as i64)
            } else {
                IbValue::Float(res)
            }
        }
        _ => IbValue::None_,
    }
}

fn modulo(l: &IbValue, r: &IbValue) -> IbValue {
    match (l.as_num(), r.as_num()) {
        (Some((a, ai)), Some((b, bi))) => {
            if b == 0.0 {
                return IbValue::None_;
            }
            let res = a.rem_euclid(b);
            if ai && bi {
                IbValue::Int(res as i64)
            } else {
                IbValue::Float(res)
            }
        }
        _ => IbValue::None_,
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

fn subscript_get(base: &IbValue, key: &IbValue) -> IbValue {
    match (base, key) {
        (IbValue::List(l), IbValue::Int(i)) => {
            l.borrow().get(*i as usize).cloned().unwrap_or(IbValue::None_)
        }
        (IbValue::Dict(d), k) => d
            .borrow()
            .iter()
            .find(|(dk, _)| dk == k)
            .map(|(_, v)| v.clone())
            .unwrap_or(IbValue::None_),
        (IbValue::Str(s), IbValue::Int(i)) => s
            .chars()
            .nth(*i as usize)
            .map(|c| IbValue::Str(c.to_string()))
            .unwrap_or(IbValue::None_),
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
pub fn run_artifact(artifact_json: &str, bridge: Option<Py<PyAny>>) -> Vec<String> {
    let module = match deserialize_module(artifact_json) {
        Some(m) => m,
        None => return Vec::new(),
    };
    let interp = match bridge {
        Some(b) => Interpreter::with_bridge(b),
        None => Interpreter::new(),
    };
    interp.run_module(&module)
}
