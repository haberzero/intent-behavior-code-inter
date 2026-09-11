//! Rust 原生 KB 值（第四批 增量 2——去 Host 化：世界模型知识图谱执行面）。
//!
//! 转录自 Python 参考内核 `core/runtime/objects/primitives/knowledge.py`（IbKnowledge
//! 治理词表 / 事实面 / 查找面）：单一权威源 = IBCI KB 声明（治理门 fail-fast +
//! append-only 事实日志 + 确定性序）；Python 参考内核 = 迁移期差分安全网。
//! 零 LLM（机器强制治理门，确定性）。
//!
//! 错误面（GAP-vec-kb-failfast 关闭，打破清单 #6）：治理门失败（参数形态 /
//! 词表未注册 / 重复登记 / 去重） = 显式错误[KNW_ 语义码经 Thrown.code 承载]；
//! 未知方法 = AttributeError（旧 catch-all 静默 None_ 清零）。

use std::cell::RefCell;
use std::collections::BTreeMap;
use std::rc::Rc;

use crate::interpreter::{runtime_error, runtime_error_coded, ErrorKind, Thrown};

use crate::interpreter::IbValue;

/// KB 词表面（治理词表——插入序 = 确定性枚举序）。
#[derive(Debug)]
pub struct KbWord {
    pub gloss: String,
    pub is_set: bool,
    pub members: Vec<IbValue>,
    pub entries: Vec<(IbValue, IbValue)>,
}

/// 关系类型记录（transitive = 传递闭包元数据；multi_valued = 矛盾判定元数据）。
#[derive(Debug)]
pub struct KbRelation {
    pub semantics: String,
    pub transitive: bool,
    pub multi_valued: bool,
}

/// 世界记录（size_rank = 尺度秩）。
#[derive(Debug)]
pub struct KbWorld {
    pub description: String,
    pub size_rank: i64,
}

/// 事实事件（add/amend/retract 日志——语料面仅 add）。
#[derive(Debug)]
pub struct KbEvent {
    pub seq: i64,
    pub kind: String,
    pub reason: String,
    pub new_o: Option<String>,
}

/// 事实记录（append-only 日志项——fact_id = str(seq)，确定性）。
#[derive(Debug)]
pub struct KbFact {
    pub id: String,
    pub world: String,
    pub s: String,
    pub r: String,
    pub o: String,
    pub source: String,
    pub status: String,
    pub events: Vec<KbEvent>,
}

/// KB 状态（治理词表 + 事实日志 + active 索引[派生视图——日志是权威]）。
#[derive(Debug)]
pub struct KbState {
    pub words: Vec<(String, KbWord)>,
    pub relations: Vec<(String, KbRelation)>,
    pub worlds: Vec<(String, KbWorld)>,
    /// 事实日志（append-only；seq 序 = 确定性序）
    pub facts: Vec<KbFact>,
    /// active 倒排索引：(s, r) → 事实下标
    pub by_pair: BTreeMap<(String, String), Vec<usize>>,
    /// active 倒排索引：(world, s, r, o) → 事实下标（去重门）
    pub by_triple: BTreeMap<(String, String, String, String), usize>,
    /// 嵌入面（词 → float 向量；插入序——内容信号非判定；维度全一致门由
    /// set_embedding 治理门保证）
    pub embeddings: Vec<(String, Vec<f64>)>,
    /// 事实序号（前置自增——首事实 id = "1"）
    pub seq: i64,
    /// 登记面（entries：键 → 条目——store/get/amend/history/keys/len；
    /// 值 = 深克隆快照，谓词引用 + 审计事件链；单一权威源 = 活 KB）
    pub entries: std::collections::HashMap<String, KbEntry>,
}

/// 登记条目（store 面——值快照 + 谓词引用 + 审计事件链）。
#[derive(Clone, Debug)]
pub struct KbEntry {
    pub value: crate::interpreter::IbValue,
    /// 验证谓词引用（同进程/会话内 amend 再过门复用；序列化恢复后 =
    /// None——amend fail-fast，KNW 边界）
    pub check: Option<crate::interpreter::IbValue>,
    pub check_name: String,
    pub provenance: String,
    pub events: Vec<KbEntryEvent>,
}

/// 登记审计事件（append-only：{seq, kind, value, reason}）。
#[derive(Clone, Debug)]
pub struct KbEntryEvent {
    pub seq: i64,
    pub kind: String,
    pub value: crate::interpreter::IbValue,
    pub reason: String,
}

impl KbState {
    pub fn blank() -> KbState {
        KbState {
            entries: std::collections::HashMap::new(),
            words: Vec::new(),
            relations: Vec::new(),
            worlds: Vec::new(),
            facts: Vec::new(),
            by_pair: BTreeMap::new(),
            by_triple: BTreeMap::new(),
            embeddings: Vec::new(),
            seq: 0,
        }
    }
}

/// IBCI 源码字面量序列化（to_ibci 投影——str 带引号转义；bool = True/False；
/// 容器递归；None = None）。
fn ibci_literal(v: &crate::interpreter::IbValue) -> String {
    use crate::interpreter::IbValue;
    match v {
        IbValue::Str(s) => format!(
            "\"{}\"",
            s.replace('\\', "\\\\").replace('"', "\\\"")
        ),
        IbValue::Bool(b) => if *b { "True".to_string() } else { "False".to_string() },
        IbValue::Int(i) => i.to_string(),
        IbValue::Float(f) => f.to_string(),
        IbValue::None_ => "None".to_string(),
        IbValue::List(l) => {
            let items: Vec<String> = l.borrow().iter().map(ibci_literal).collect();
            format!("[{}]", items.join(", "))
        }
        IbValue::Tuple(t) => {
            let items: Vec<String> = t.iter().map(ibci_literal).collect();
            format!("({})", items.join(", "))
        }
        IbValue::Dict(d) => {
            let items: Vec<String> = d
                .borrow()
                .iter()
                .map(|(k, val)| format!("{}: {}", ibci_literal(k), ibci_literal(val)))
                .collect();
            format!("{{{}}}", items.join(", "))
        }
        other => other.repr(),
    }
}

/// 验证门函数调用（check(value) 引擎求值——经解释器调用用户函数；
/// 谓词引用非函数 = fail-fast）。
fn call_check(
    interp: &crate::interpreter::Interpreter,
    env: &Rc<RefCell<crate::interpreter::Environment>>,
    output: &mut Vec<String>,
    check: &IbValue,
    arg: &IbValue,
) -> Result<bool, Thrown> {
    match check {
        IbValue::Function(f) => {
            let global = crate::interpreter::global_rc(env);
            let res = interp.call_user_function(f, vec![arg.clone()], output, &global)?;
            Ok(res.truthy())
        }
        _ => Err(runtime_error(
            ErrorKind::TypeError,
            "验证谓词须为函数值",
        )),
    }
}

/// 词表名查找（插入序保留；None = 未注册[合法态]）。
fn find_name(list: &[(String, impl std::fmt::Debug)], name: &str) -> bool {
    list.iter().any(|(n, _)| n == name)
}

/// 事实记录 → 数据面 Dict（键序 = Python 事实 dict 插入序：id/world/s/r/o/
/// source/status/events）。
fn fact_value(f: &KbFact) -> IbValue {
    let k = |s: &str| -> IbValue { IbValue::Str(s.to_string()) };
    let events: Vec<IbValue> = f
        .events
        .iter()
        .map(|e| {
            IbValue::dict_new(vec![
                (k("seq"), IbValue::Int(e.seq)),
                (k("kind"), IbValue::Str(e.kind.clone())),
                (k("reason"), IbValue::Str(e.reason.clone())),
                (
                    k("new_o"),
                    e.new_o
                        .clone()
                        .map(IbValue::Str)
                        .unwrap_or(IbValue::None_),
                ),
            ])
        })
        .collect();
    IbValue::dict_new(vec![
        (k("id"), IbValue::Str(f.id.clone())),
        (k("world"), IbValue::Str(f.world.clone())),
        (k("s"), IbValue::Str(f.s.clone())),
        (k("r"), IbValue::Str(f.r.clone())),
        (k("o"), IbValue::Str(f.o.clone())),
        (k("source"), IbValue::Str(f.source.clone())),
        (k("status"), IbValue::Str(f.status.clone())),
        (k("events"), IbValue::List(Rc::new(RefCell::new(events)))),
    ])
}

/// KB 方法分发（语料面 7 方法 + worlds/words 枚举——单点真理性治理门转录）。
///
/// 错误面登记：治理门失败 / 参数形态错误 = None_（同解释器错误惯例；语料无
/// 错误探针）。
pub fn dispatch(
    interp: &crate::interpreter::Interpreter,
    env: &Rc<RefCell<crate::interpreter::Environment>>,
    kb: &Rc<RefCell<KbState>>,
    method: &str,
    args: &[IbValue],
    output: &mut Vec<String>,
) -> Result<IbValue, Thrown> {
    match method {
        // ---- 登记面（store/get/amend/history/keys/len——深克隆快照隔离）----
        "store" => {
            // (key: 非空 str, value, check: 函数, [provenance: str])
            let (k, val, check, prov) = match args {
                [IbValue::Str(k), v, c] => (k.as_str(), v, c, ""),
                [IbValue::Str(k), v, c, IbValue::Str(p)] => (k.as_str(), v, c, p.as_str()),
                _ => {
                    return Err(runtime_error_coded(
                        ErrorKind::ValueError,
                        "store: 参数形态非法",
                        Some("KNW_KEY_EXISTS"),
                    ))
                }
            };
            if k.is_empty() {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "store: 键须为非空 str",
                    Some("KNW_KEY_EXISTS"),
                ));
            }
            let mut st = kb.borrow_mut();
            if st.entries.contains_key(k) {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "store: 键已登记（更正走 amend）",
                    Some("KNW_KEY_EXISTS"),
                ));
            }
            // 验证门：引擎求值 check(value)（假 = 拒绝登记）
            let snapshot = crate::interpreter::deep_clone_value(val);
            let passed = call_check(interp, env, output, check, &snapshot)?;
            if !passed {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "store: 未过验证门 check(value) 为假",
                    Some("KNW_CHECK_REJECTED"),
                ));
            }
            st.seq += 1;
            let seq = st.seq;
            let check_name = match check {
                IbValue::Function(f) => f.name.clone(),
                _ => String::new(),
            };
            st.entries.insert(
                k.to_string(),
                KbEntry {
                    value: snapshot,
                    check: Some(check.clone()),
                    check_name,
                    provenance: prov.to_string(),
                    events: vec![KbEntryEvent {
                        seq,
                        kind: "store".to_string(),
                        value: val.clone(),
                        reason: String::new(),
                    }],
                },
            );
            Ok(IbValue::None_)
        }
        "get" => {
            let [IbValue::Str(k)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            match st.entries.get(k) {
                Some(e) => Ok(crate::interpreter::deep_clone_value(&e.value)),
                None => Ok(IbValue::None_),
            }
        }
        "to_ibci" => {
            // 导出 KB 当前态的确定性 IBCI 代码（派生视图，非存储层——重建等价
            // KB；词汇序 = 插入序，事实序 = seq 序；只读导出无治理违约面）
            let st = kb.borrow();
            let mut lines = vec![
                "# knowledge.to_ibci() 确定性导出（派生视图——KB 当前态的 IBCI 代码 投影；非存储层，单一权威源 = 活 KB / artifact）".to_string(),
                "kb = knowledge()".to_string(),
            ];
            for (name, rec) in &st.worlds {
                lines.push(format!(
                    "kb.register_world({}, {}, {})",
                    ibci_literal(&IbValue::Str(name.clone())),
                    ibci_literal(&IbValue::Str(rec.description.clone())),
                    rec.size_rank
                ));
            }
            for (rtype, rec) in &st.relations {
                lines.push(format!(
                    "kb.register_relation({}, {}, {}, {})",
                    ibci_literal(&IbValue::Str(rtype.clone())),
                    ibci_literal(&IbValue::Str(rec.semantics.clone())),
                    ibci_literal(&IbValue::Bool(rec.transitive)),
                    ibci_literal(&IbValue::Bool(rec.multi_valued))
                ));
            }
            for (lexeme, rec) in &st.words {
                lines.push(format!(
                    "kb.register_word({}, {}, {}, {}, {})",
                    ibci_literal(&IbValue::Str(lexeme.clone())),
                    ibci_literal(&IbValue::Str(rec.gloss.clone())),
                    ibci_literal(&IbValue::Bool(rec.is_set)),
                    ibci_literal(&IbValue::List(Rc::new(RefCell::new(rec.members.clone())))),
                    ibci_literal(&IbValue::Dict(Rc::new(RefCell::new(rec.entries.clone()))))
                ));
            }
            for f in &st.facts {
                lines.push(format!(
                    "kb.add_fact({}, {}, {}, {}, {}, {})",
                    ibci_literal(&IbValue::Str(f.world.clone())),
                    ibci_literal(&IbValue::Str(f.s.clone())),
                    ibci_literal(&IbValue::Str(f.r.clone())),
                    ibci_literal(&IbValue::Str(f.o.clone())),
                    ibci_literal(&IbValue::Str(f.source.clone())),
                    ibci_literal(&IbValue::Str(f.status.clone()))
                ));
            }
            lines.push("kb".to_string());
            Ok(IbValue::Str(lines.join("\n")))
        }
        "export" => {
            // 全注册表导出（dict 容器约定之外的整库检视面）：键 → {value,
            // check_name, provenance, events}——值 = 快照深克隆
            let st = kb.borrow();
            let mut pairs: Vec<(IbValue, IbValue)> = Vec::new();
            let mut keys: Vec<&String> = st.entries.keys().collect();
            keys.sort();
            for k in keys {
                let e = &st.entries[k];
                let events: Vec<IbValue> = e
                    .events
                    .iter()
                    .map(|ev| {
                        IbValue::dict_new(vec![
                            (IbValue::Str("seq".into()), IbValue::Int(ev.seq)),
                            (IbValue::Str("kind".into()), IbValue::Str(ev.kind.clone())),
                            (IbValue::Str("value".into()), crate::interpreter::deep_clone_value(&ev.value)),
                            (IbValue::Str("reason".into()), IbValue::Str(ev.reason.clone())),
                        ])
                    })
                    .collect();
                pairs.push((
                    IbValue::Str(k.clone()),
                    IbValue::dict_new(vec![
                        (IbValue::Str("value".into()), crate::interpreter::deep_clone_value(&e.value)),
                        (IbValue::Str("check_name".into()), IbValue::Str(e.check_name.clone())),
                        (IbValue::Str("provenance".into()), IbValue::Str(e.provenance.clone())),
                        (IbValue::Str("events".into()), IbValue::list_new(events)),
                    ]),
                ));
            }
            Ok(IbValue::Dict(Rc::new(RefCell::new(pairs))))
        }
        "keys" => {
            let st = kb.borrow();
            let mut keys: Vec<IbValue> = st.entries.keys().map(|k| IbValue::Str(k.clone())).collect();
            // 确定性序 = 插入序（HashMap 无序——按 seq 事件序恢复：entries
            // 插入序经 event seq 推导；当前以键名序为确定性回退）
            keys.sort_by(|a, b| a.repr().cmp(&b.repr()));
            Ok(IbValue::list_new(keys))
        }
        "len" => {
            let st = kb.borrow();
            Ok(IbValue::Int(st.entries.len() as i64))
        }
        "amend" => {
            // (key, new_value, reason: 非空 str)
            let [IbValue::Str(k), new_val, IbValue::Str(reason)] = args else {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "amend: 参数形态非法",
                    Some("KNW_REASON_EMPTY"),
                ));
            };
            if reason.trim().is_empty() {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "amend: 理由强制非空",
                    Some("KNW_REASON_EMPTY"),
                ));
            }
            // 借出 check 引用（须在可变借用前克隆——check 调用期释放 st）
            let check = {
                let st = kb.borrow();
                st.entries.get(k).map(|e| e.check.clone()).ok_or_else(|| {
                    runtime_error_coded(
                        ErrorKind::ValueError,
                        "amend: 键未登记（更正仅适用已登记条目）",
                        Some("KNW_REASON_EMPTY"),
                    )
                })?
                .ok_or_else(|| {
                    runtime_error_coded(
                        ErrorKind::ValueError,
                        "amend: 验证谓词引用不可用（恢复后须重新 store）",
                        Some("KNW_CHECK_REJECTED"),
                    )
                })?
            };
            // 新值再过 check 门（防更正通道变无门控写口）
            let snapshot = crate::interpreter::deep_clone_value(new_val);
            let passed = call_check(interp, env, output, &check, &snapshot)?;
            if !passed {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "amend: 新值未过验证门",
                    Some("KNW_CHECK_REJECTED"),
                ));
            }
            let mut st = kb.borrow_mut();
            st.seq += 1;
            let seq = st.seq;
            let entry = st.entries.get_mut(k).unwrap();
            entry.value = snapshot.clone();
            entry.events.push(KbEntryEvent {
                seq,
                kind: "amend".to_string(),
                value: snapshot,
                reason: reason.clone(),
            });
            Ok(IbValue::None_)
        }
        "history" => {
            // (key, [kind]) → list[{seq, kind, value, reason}]
            let k = match args.first() {
                Some(IbValue::Str(k)) => k.as_str(),
                _ => return Ok(IbValue::list_new(Vec::new())),
            };
            let st = kb.borrow();
            let Some(entry) = st.entries.get(k) else {
                return Ok(IbValue::list_new(Vec::new()));
            };
            let kind_filter = match args.get(1) {
                Some(IbValue::Str(kf)) => kf.clone(),
                _ => String::new(),
            };
            let items: Vec<IbValue> = entry
                .events
                .iter()
                .filter(|ev| kind_filter.is_empty() || ev.kind == kind_filter)
                .map(|ev| {
                    IbValue::dict_new(vec![
                        (IbValue::Str("seq".into()), IbValue::Int(ev.seq)),
                        (IbValue::Str("kind".into()), IbValue::Str(ev.kind.clone())),
                        (IbValue::Str("value".into()), crate::interpreter::deep_clone_value(&ev.value)),
                        (IbValue::Str("reason".into()), IbValue::Str(ev.reason.clone())),
                    ])
                })
                .collect();
            Ok(IbValue::list_new(items))
        }
        // 治理词表面（fail-fast 重复登记拒绝 = None_）
        "register_world" => {
            let [IbValue::Str(n), IbValue::Str(d), IbValue::Int(sr)] = args else {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "register_world: 参数形态非法",
                    Some("KNW_VOCAB_MALFORMED"),
                ));
            };
            let mut st = kb.borrow_mut();
            if find_name(&st.worlds, n) {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "register_world: 词表重复登记",
                    Some("KNW_VOCAB_EXISTS"),
                ));
            }
            st.worlds
                .push((n.clone(), KbWorld { description: d.clone(), size_rank: *sr }));
            Ok(IbValue::None_)
        }
        "register_relation" => {
            let [
                IbValue::Str(rt),
                IbValue::Str(sem),
                IbValue::Bool(tr),
                IbValue::Bool(mv),
            ] = args else {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "register_relation: 参数形态非法",
                    Some("KNW_VOCAB_MALFORMED"),
                ));
            };
            if rt.is_empty() {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "register_relation: 参数形态非法",
                    Some("KNW_VOCAB_MALFORMED"),
                ));
            }
            let mut st = kb.borrow_mut();
            if find_name(&st.relations, rt) {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "register_relation: 词表重复登记",
                    Some("KNW_VOCAB_EXISTS"),
                ));
            }
            st.relations.push((
                rt.clone(),
                KbRelation {
                    semantics: sem.clone(),
                    transitive: *tr,
                    multi_valued: *mv,
                },
            ));
            Ok(IbValue::None_)
        }
        "register_word" => {
            // (lexeme: 非空 str, gloss: str, is_set: bool, members: list, entries: dict)
            let (lex, gl, ist, mem, ent) = match args {
                [IbValue::Str(l), IbValue::Str(g), IbValue::Bool(i), IbValue::List(m), IbValue::Dict(d)] => {
                    (l, g, i, m.borrow().clone(), d.borrow().clone())
                }
                [IbValue::Str(l), IbValue::Str(g), IbValue::Bool(i)] => {
                    (l, g, i, Vec::new(), Vec::new())
                }
                _ => {
                    return Err(runtime_error_coded(
                        ErrorKind::ValueError,
                        "register_word: 参数形态非法",
                        Some("KNW_VOCAB_MALFORMED"),
                    ))
                }
            };
            if lex.is_empty() {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "register_word: 参数形态非法",
                    Some("KNW_VOCAB_MALFORMED"),
                ));
            }
            let mut st = kb.borrow_mut();
            if find_name(&st.words, lex) {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "register_word: 词表重复登记",
                    Some("KNW_VOCAB_EXISTS"),
                ));
            }
            st.words.push((
                lex.clone(),
                KbWord {
                    gloss: gl.clone(),
                    is_set: *ist,
                    members: mem,
                    entries: ent,
                },
            ));
            Ok(IbValue::None_)
        }
        // 枚举面（插入序）
        "worlds" => Ok(IbValue::list_new(
            kb.borrow()
                .worlds
                .iter()
                .map(|(n, _)| IbValue::Str(n.clone()))
                .collect(),
        )),
        "words" => Ok(IbValue::list_new(
            kb.borrow()
                .words
                .iter()
                .map(|(n, _)| IbValue::Str(n.clone()))
                .collect(),
        )),
        "relations" => Ok(IbValue::list_new(
            kb.borrow()
                .relations
                .iter()
                .map(|(n, _)| IbValue::Str(n.clone()))
                .collect(),
        )),
        // 事实面（内建治理门：词表 allowlist + 去重机器强制）
        "add_fact" => {
            // (world, s, r, o: 非空 str; source: str 缺省 ""; status: str 缺省 "active")
            let (w, subj, rel, obj, src, stt) = match args {
                [IbValue::Str(w), IbValue::Str(s), IbValue::Str(r), IbValue::Str(o)] => {
                    (w, s, r, o, &"" as &str, "active")
                }
                [
                    IbValue::Str(w),
                    IbValue::Str(s),
                    IbValue::Str(r),
                    IbValue::Str(o),
                    IbValue::Str(src),
                    IbValue::Str(stt),
                ] => (w, s, r, o, src.as_str(), stt.as_str()),
                // 5 参形态（w,s,r,o,source——status 缺省 active）
                [IbValue::Str(w), IbValue::Str(s), IbValue::Str(r), IbValue::Str(o), IbValue::Str(src)] => {
                    (w, s, r, o, src.as_str(), "active")
                }
                _ => {
                    return Err(runtime_error_coded(
                        ErrorKind::ValueError,
                        "add_fact: 参数形态非法",
                        Some("KNW_VOCAB_MALFORMED"),
                    ))
                }
            };
            if w.is_empty() || subj.is_empty() || rel.is_empty() || obj.is_empty() {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "add_fact: 参数形态非法",
                    Some("KNW_VOCAB_MALFORMED"),
                ));
            }
            // source 允许空串（缺省 ""）；status 须非空
            if stt.is_empty() {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "add_fact: 参数形态非法",
                    Some("KNW_VOCAB_MALFORMED"),
                ));
            }
            let mut st = kb.borrow_mut();
            // 治理门：词表 allowlist（确定性，零 LLM）
            if !find_name(&st.worlds, w)
                || !find_name(&st.relations, rel)
                || !find_name(&st.words, subj)
                || !find_name(&st.words, obj)
            {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "add_fact: 引用未注册词表项",
                    Some("KNW_VOCAB_UNREGISTERED"),
                ));
            }
            // 去重门：同 (world,s,r,o) active 事实机器强制唯一
            let triple_key = (w.clone(), subj.clone(), rel.clone(), obj.clone());
            if st.by_triple.contains_key(&triple_key) {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "add_fact: 重复 active 事实",
                    Some("KNW_FACT_DUPLICATE"),
                ));
            }
            st.seq += 1;
            let fid = st.seq.to_string();
            let fact = KbFact {
                id: fid.clone(),
                world: w.clone(),
                s: subj.clone(),
                r: rel.clone(),
                o: obj.clone(),
                source: src.to_string(),
                status: stt.to_string(),
                events: vec![KbEvent {
                    seq: st.seq,
                    kind: "add".to_string(),
                    reason: String::new(),
                    new_o: None,
                }],
            };
            let idx = st.facts.len();
            st.facts.push(fact);
            if stt == "active" {
                st.by_pair
                    .entry((subj.clone(), rel.clone()))
                    .or_default()
                    .push(idx);
                st.by_triple.insert(triple_key, idx);
            }
            Ok(IbValue::Str(fid))
        }
        // 查找面（active 视图）
        "by_subject" => {
            // 关于某词的全部 active 事实（word.relations 的派生替代——根治
            // 双写真相：词关系从不独立存储，只从事实日志派生；seq 序）
            let [IbValue::Str(s)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            let items: Vec<IbValue> = st
                .facts
                .iter()
                .filter(|f| f.status == "active" && &f.s == s)
                .map(fact_value)
                .collect();
            Ok(IbValue::list_new(items))
        }
        "by_source" => {
            // 某来源的全部事实（审计面——全日志视图，含 retracted 墓碑）
            let [IbValue::Str(src)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            let items: Vec<IbValue> = st
                .facts
                .iter()
                .filter(|f| &f.source == src)
                .map(fact_value)
                .collect();
            Ok(IbValue::list_new(items))
        }
        "exists" => {
            let [IbValue::Str(w), IbValue::Str(s), IbValue::Str(r), IbValue::Str(o)] = args
            else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            Ok(IbValue::Bool(
                st.by_triple
                    .contains_key(&(w.clone(), s.clone(), r.clone(), o.clone())),
            ))
        }
        "lookup_pair" => {
            let [IbValue::Str(s), IbValue::Str(r)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            let ids = st.by_pair.get(&(s.clone(), r.clone()));
            let items: Vec<IbValue> = ids
                .map(|v| v.iter().map(|i| fact_value(&st.facts[*i])).collect())
                .unwrap_or_default();
            Ok(IbValue::list_new(items))
        }
        "contradicts" => {
            // 同 (s,r) 已有 active o'≠o 且关系非 multi_valued ⇒ 矛盾
            let [IbValue::Str(s), IbValue::Str(r), IbValue::Str(o)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            let rel_rec = st.relations.iter().find(|(n, _)| n == r);
            let Some((_, rec)) = rel_rec else {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "contradicts: 关系未注册",
                    Some("KNW_VOCAB_UNREGISTERED"),
                ));
            };
            if rec.multi_valued {
                return Ok(IbValue::Bool(false));
            }
            let others = st.by_pair.get(&(s.clone(), r.clone()));
            let conflict = others
                .map(|ids| ids.iter().any(|i| st.facts[*i].o != *o))
                .unwrap_or(false);
            Ok(IbValue::Bool(conflict))
        }
        // ------------------------------------------------------------------ //
        // 词表查询面（未注册 = None[合法态非错误]）
        // ------------------------------------------------------------------ //
        "word" => {
            let [IbValue::Str(lex)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            Ok(match st.words.iter().find(|(n, _)| n == lex) {
                Some((_, w)) => {
                    let mut entries = Vec::new();
                    for (k, v) in &w.entries {
                        entries.push((k.clone(), v.clone()));
                    }
                    IbValue::dict_new(vec![
                        (k("lexeme"), IbValue::Str(lex.clone())),
                        (k("gloss"), IbValue::Str(w.gloss.clone())),
                        (k("is_set"), IbValue::Bool(w.is_set)),
                        (
                            k("members"),
                            IbValue::List(Rc::new(RefCell::new(
                                w.members.clone(),
                            ))),
                        ),
                        (
                            k("entries"),
                            IbValue::Dict(Rc::new(RefCell::new(entries))),
                        ),
                    ])
                }
                None => IbValue::None_,
            })
        }
        "relation" => {
            let [IbValue::Str(rt)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            Ok(match st.relations.iter().find(|(n, _)| n == rt) {
                Some((_, rec)) => IbValue::dict_new(vec![
                    (k("type"), IbValue::Str(rt.clone())),
                    (k("semantics"), IbValue::Str(rec.semantics.clone())),
                    (k("transitive"), IbValue::Bool(rec.transitive)),
                    (k("multi_valued"), IbValue::Bool(rec.multi_valued)),
                ]),
                None => IbValue::None_,
            })
        }
        "world" => {
            let [IbValue::Str(n)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            Ok(match st.worlds.iter().find(|(nm, _)| nm == n) {
                Some((_, w)) => IbValue::dict_new(vec![
                    (k("name"), IbValue::Str(n.clone())),
                    (k("description"), IbValue::Str(w.description.clone())),
                    (k("size_rank"), IbValue::Int(w.size_rank)),
                ]),
                None => IbValue::None_,
            })
        }
        // ------------------------------------------------------------------ //
        // 事实查询面（全日志 = 含 retracted 墓碑；seq 序）
        // ------------------------------------------------------------------ //
        "get_fact" => {
            let [IbValue::Str(fid)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            Ok(st.facts
                .iter()
                .find(|f| &f.id == fid)
                .map(fact_value)
                .unwrap_or(IbValue::None_))
        }
        "facts" => {
            let st = kb.borrow();
            let items: Vec<IbValue> = st.facts.iter().map(fact_value).collect();
            Ok(IbValue::list_new(items))
        }
        "fact_len" => {
            let st = kb.borrow();
            Ok(IbValue::Int(st.facts.len() as i64))
        }
        "all_in_world" => {
            // 某 world 的全部 active 事实（seq 序）
            let [IbValue::Str(w)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            let items: Vec<IbValue> = st
                .facts
                .iter()
                .filter(|f| f.status == "active" && &f.world == w)
                .map(fact_value)
                .collect();
            Ok(IbValue::list_new(items))
        }
        "source" => {
            let [IbValue::Str(fid)] = args else {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "source: 参数形态非法",
                    Some("KNW_FACT_NOT_FOUND"),
                ));
            };
            let st = kb.borrow();
            let f = st.facts.iter().find(|f| &f.id == fid).ok_or_else(|| {
                runtime_error_coded(
                    ErrorKind::ValueError,
                    "source: 未知 fact_id",
                    Some("KNW_FACT_NOT_FOUND"),
                )
            })?;
            Ok(IbValue::Str(f.source.clone()))
        }
        "history_fact" => {
            // 事件链（append-only 全史：{seq, kind, reason, new_o}）
            let [IbValue::Str(fid)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            Ok(match st.facts.iter().find(|f| &f.id == fid) {
                Some(f) => {
                    let items: Vec<IbValue> = f
                        .events
                        .iter()
                        .map(|e| {
                            IbValue::dict_new(vec![
                                (k("seq"), IbValue::Int(e.seq)),
                                (k("kind"), IbValue::Str(e.kind.clone())),
                                (k("reason"), IbValue::Str(e.reason.clone())),
                                (
                                    k("new_o"),
                                    e.new_o
                                        .clone()
                                        .map(IbValue::Str)
                                        .unwrap_or(IbValue::None_),
                                ),
                            ])
                        })
                        .collect();
                    IbValue::list_new(items)
                }
                None => {
                    return Err(runtime_error_coded(
                        ErrorKind::ValueError,
                        "history_fact: 未知 fact_id",
                        Some("KNW_FACT_NOT_FOUND"),
                    ))
                }
            })
        }
        // ------------------------------------------------------------------ //
        // 审计面（墓碑/版本化——append-only 纪律 + reason 强制 + 全史可溯）
        // ------------------------------------------------------------------ //
        "retract" => {
            // 墓碑：status → retracted + 事件链；active 索引即时移除（审计视图
            // 保留全史）；已 retracted 再 retract = None_（墓碑只读）
            let [IbValue::Str(fid), IbValue::Str(reason)] = args else {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "retract: 参数形态非法",
                    Some("KNW_FACT_NOT_FOUND"),
                ));
            };
            if reason.trim().is_empty() {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "retract: 理由强制非空",
                    Some("KNW_REASON_EMPTY"),
                ));
            }
            let mut st = kb.borrow_mut();
            let Some(idx) = st.facts.iter().position(|f| &f.id == fid) else {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "retract: 未知 fact_id",
                    Some("KNW_FACT_NOT_FOUND"),
                ));
            };
            if st.facts[idx].status == "retracted" {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "retract: 已 retracted（墓碑只读）",
                    Some("KNW_FACT_RETRACTED"),
                ));
            }
            let was_active = st.facts[idx].status == "active";
            st.seq += 1;
            let seq = st.seq;
            st.facts[idx].status = "retracted".to_string();
            st.facts[idx].events.push(KbEvent {
                seq,
                kind: "retract".to_string(),
                reason: reason.clone(),
                new_o: None,
            });
            if was_active {
                // 图索引移除（active 视图——事实退出世界模型）
                let triple_key = (
                    st.facts[idx].world.clone(),
                    st.facts[idx].s.clone(),
                    st.facts[idx].r.clone(),
                    st.facts[idx].o.clone(),
                );
                if st
                    .by_triple
                    .get(&triple_key)
                    .is_some_and(|&i| i == idx)
                {
                    st.by_triple.remove(&triple_key);
                }
                let pair_key = (st.facts[idx].s.clone(), st.facts[idx].r.clone());
                if let Some(lst) = st.by_pair.get_mut(&pair_key) {
                    lst.retain(|&i| i != idx);
                }
            }
            Ok(IbValue::None_)
        }
        "amend_fact" => {
            // o 版本化：new_o 替换当前 o（事件链全史可溯）；索引仅在新 o 变更
            // 且 active 时更新；已 retracted 事实 amend = None_
            let [IbValue::Str(fid), IbValue::Str(new_o), IbValue::Str(reason)] = args
            else {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "amend_fact: 参数形态非法",
                    Some("KNW_FACT_NOT_FOUND"),
                ));
            };
            if new_o.is_empty() || reason.trim().is_empty() {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "amend_fact: 参数形态非法",
                    Some("KNW_REASON_EMPTY"),
                ));
            }
            let mut st = kb.borrow_mut();
            let Some(idx) = st.facts.iter().position(|f| &f.id == fid) else {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "amend_fact: 未知 fact_id",
                    Some("KNW_FACT_NOT_FOUND"),
                ));
            };
            if st.facts[idx].status == "retracted" {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "amend_fact: 已 retracted（墓碑只读）",
                    Some("KNW_FACT_RETRACTED"),
                ));
            }
            // 治理门：new_o 须已注册词
            if !find_name(&st.words, new_o) {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "amend_fact: 新 o 未注册",
                    Some("KNW_VOCAB_UNREGISTERED"),
                ));
            }
            let old_o = st.facts[idx].o.clone();
            st.seq += 1;
            let seq = st.seq;
            st.facts[idx].events.push(KbEvent {
                seq,
                kind: "amend".to_string(),
                reason: reason.clone(),
                new_o: Some(new_o.clone()),
            });
            st.facts[idx].o = new_o.clone();
            if old_o != *new_o && st.facts[idx].status == "active" {
                // by_triple 切换（同 (w,s,r) 的 o 键）
                let old_triple = (
                    st.facts[idx].world.clone(),
                    st.facts[idx].s.clone(),
                    st.facts[idx].r.clone(),
                    old_o,
                );
                if st
                    .by_triple
                    .get(&old_triple)
                    .is_some_and(|&i| i == idx)
                {
                    st.by_triple.remove(&old_triple);
                }
                let new_triple = (
                    st.facts[idx].world.clone(),
                    st.facts[idx].s.clone(),
                    st.facts[idx].r.clone(),
                    new_o.clone(),
                );
                st.by_triple.insert(new_triple, idx);
            }
            // by_pair 不变（(s,r) 未变）
            Ok(IbValue::None_)
        }
        // ------------------------------------------------------------------ //
        // 查找面（传递闭包——BFS 防环，确定性发现序）
        // ------------------------------------------------------------------ //
        "transitive" => {
            // 沿 active by_pair 链展开 transitive 关系 r 的可达集（含直接；
            // 每项 {s, r, o, via}——via = 中间对象链）；非传递关系 = 空 list
            let [IbValue::Str(subj), IbValue::Str(rel)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            let rel_rec = st.relations.iter().find(|(n, _)| n == rel);
            let Some((_, rec)) = rel_rec else {
                return Err(runtime_error_coded(
                    ErrorKind::ValueError,
                    "transitive: 关系未注册",
                    Some("KNW_VOCAB_UNREGISTERED"),
                ));
            };
            if !rec.transitive {
                return Ok(IbValue::list_new(Vec::new()));
            }
            // BFS（确定性发现序 = 队列序；via = 中间节点链[不含端点]）
            let mut paths: Vec<(String, Vec<String>)> = vec![(subj.clone(), Vec::new())];
            let mut head = 0usize;
            while head < paths.len() {
                let cur = paths[head].0.clone();
                let cur_via = paths[head].1.clone();
                head += 1;
                let ids = st.by_pair.get(&(cur.clone(), rel.clone())).cloned();
                if let Some(ids) = ids {
                    for &fi in &ids {
                        let to = st.facts[fi].o.clone();
                        if !paths.iter().any(|(n, _)| n == &to) {
                            let via = if cur == *subj {
                                cur_via.clone()
                            } else {
                                let mut v = cur_via.clone();
                                v.push(cur.clone());
                                v
                            };
                            paths.push((to, via));
                        }
                    }
                }
            }
            let items: Vec<IbValue> = paths
                .iter()
                .skip(1)
                .map(|(o, via)| {
                    IbValue::dict_new(vec![
                        (k("s"), IbValue::Str(subj.clone())),
                        (k("r"), IbValue::Str(rel.clone())),
                        (k("o"), IbValue::Str(o.clone())),
                        (
                            k("via"),
                            IbValue::list_new(
                                via.iter().map(|v| IbValue::Str(v.clone())).collect(),
                            ),
                        ),
                    ])
                })
                .collect();
            Ok(IbValue::list_new(items))
        }
        // ------------------------------------------------------------------ //
        // 对比/展开面（纯派生不存展开态——确定性复现）
        // ------------------------------------------------------------------ //
        // ------------------------------------------------------------------ //
        // 向量面（词嵌入——内容信号非判定；维度全一致治理门）
        // ------------------------------------------------------------------ //
        "set_embedding" => {
            // 挂/换嵌入：word 须已注册 + vec 须数值向量 + 维度与既有嵌入一致
            // （首个嵌入定维度）
            let [IbValue::Str(w), vec_arg] = args else {
                return Ok(IbValue::None_);
            };
            let Some(elems) = numeric_vec(vec_arg) else {
                return Ok(IbValue::None_);
            };
            let mut st = kb.borrow_mut();
            if !find_name(&st.words, w) {
                return Ok(IbValue::None_);
            }
            let dim = elems.len();
            if st.embeddings.iter().any(|(_, e)| e.len() != dim) {
                return Ok(IbValue::None_);
            }
            // 挂/换（同词重设 = 替换）
            if let Some(slot) = st.embeddings.iter_mut().find(|(n, _)| n == w) {
                slot.1 = elems;
            } else {
                st.embeddings.push((w.clone(), elems));
            }
            Ok(IbValue::None_)
        }
        "embedding" => {
            // 取词嵌入（未挂 = None_[fail-fast 面——错误面登记]）
            let [IbValue::Str(w)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            if !find_name(&st.words, w) {
                return Ok(IbValue::None_);
            }
            Ok(st.embeddings
                .iter()
                .find(|(n, _)| n == w)
                .map(|(_, e)| IbValue::Tensor(crate::interpreter::TensorValue::from_1d(e.clone())))
                .unwrap_or(IbValue::None_))
        }
        "has_embedding" => {
            let [IbValue::Str(w)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            Ok(IbValue::Bool(st.embeddings.iter().any(|(n, _)| n == w)))
        }
        "embedding_dim" => {
            // 嵌入维度（嵌入面维度全一致，取任一即全维度；无嵌入 = None_）
            let st = kb.borrow();
            Ok(match st.embeddings.first() {
                Some((_, e)) => IbValue::Int(e.len() as i64),
                None => IbValue::None_,
            })
        }
        "embed_search" => {
            // 全嵌入词暴力 cosine 取前 k（排序键 (−score, word)——score 降序 +
            // 平手按词名确定性 tie-break；k 超嵌入词数 = 返回全部）
            let [IbValue::Tensor(q), IbValue::Int(kk)] = args else {
                return Ok(IbValue::None_);
            };
            // 查询须为 1D tensor（vector）；2D = 不可比（合法拒绝）
            let qv = match q.to_1d() {
                Some(v) => v,
                None => return Ok(IbValue::None_),
            };
            if *kk < 1 {
                return Ok(IbValue::None_);
            }
            let st = kb.borrow();
            if st.embeddings.is_empty() {
                return Ok(IbValue::None_);
            }
            let mut scored: Vec<(f64, String)> = st
                .embeddings
                .iter()
                .filter(|(_, e)| e.len() == qv.len()) // 维度不符 = 不可比（跳过）
                .map(|(w, e)| (kb_cosine(qv, e), w.clone()))
                .collect();
            scored.sort_by(|a, b| {
                // (−score, word) 升序 = score 降序 + 词名升序
                b.0.partial_cmp(&a.0)
                    .unwrap_or(std::cmp::Ordering::Equal)
                    .then_with(|| a.1.cmp(&b.1))
            });
            let items: Vec<IbValue> = scored
                .into_iter()
                .take(*kk as usize)
                .map(|(score, w)| {
                    IbValue::dict_new(vec![
                        (k("word"), IbValue::Str(w)),
                        (k("score"), IbValue::Float(score)),
                    ])
                })
                .collect();
            Ok(IbValue::list_new(items))
        }
        "same_word" => {
            // 词同一性：a == b 且均为已注册词（未注册 = false 非错误）
            let [IbValue::Str(a), IbValue::Str(b)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            let same = a == b && find_name(&st.words, a);
            Ok(IbValue::Bool(same))
        }
        "compare" => {
            // {exact/contradiction/scale/same_word}（确定性 4 层）
            let [IbValue::Str(a), IbValue::Str(b)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            let (fa, fb) = match (
                st.facts.iter().find(|f| &f.id == a),
                st.facts.iter().find(|f| &f.id == b),
            ) {
                (Some(fa), Some(fb)) => (fa, fb),
                _ => {
                    return Err(runtime_error_coded(
                        ErrorKind::ValueError,
                        "compare: 未知 fact_id",
                        Some("KNW_FACT_NOT_FOUND"),
                    ))
                }
            };
            let rel_rec = if fa.r == fb.r {
                st.relations.iter().find(|(n, _)| n == &fa.r).map(|(_, r)| r)
            } else {
                None
            };
            let exact = fa.world == fb.world && fa.s == fb.s && fa.r == fb.r && fa.o == fb.o;
            let contradiction = fa.s == fb.s
                && fa.r == fb.r
                && fa.o != fb.o
                && rel_rec.is_some_and(|r| !r.multi_valued);
            let scale = if fa.world == fb.world { "same" } else { "cross" };
            let same_word = fa.s == fb.s && find_name(&st.words, &fa.s);
            Ok(IbValue::dict_new(vec![
                (k("exact"), IbValue::Bool(exact)),
                (k("contradiction"), IbValue::Bool(contradiction)),
                (k("scale"), IbValue::Str(scale.to_string())),
                (k("same_word"), IbValue::Bool(same_word)),
            ]))
        }
        "expand" => {
            // 事实 + 主语/对象词记录 + 关系语义 + 世界上下文（纯派生）
            let [IbValue::Str(fid)] = args else {
                return Ok(IbValue::None_);
            };
            let st = kb.borrow();
            let f = match st.facts.iter().find(|f| &f.id == fid) {
                Some(f) => f,
                None => {
                    return Err(runtime_error_coded(
                        ErrorKind::ValueError,
                        "expand: 未知 fact_id",
                        Some("KNW_FACT_NOT_FOUND"),
                    ))
                }
            };
            let word_value = |st_: &KbState, name: &str| -> IbValue {
                match st_.words.iter().find(|(n, _)| n == name) {
                    Some((_, w)) => {
                        let mut entries = Vec::new();
                        for (ek, ev) in &w.entries {
                            entries.push((ek.clone(), ev.clone()));
                        }
                        IbValue::dict_new(vec![
                            (k("lexeme"), IbValue::Str(name.to_string())),
                            (k("gloss"), IbValue::Str(w.gloss.clone())),
                            (k("is_set"), IbValue::Bool(w.is_set)),
                            (
                                k("members"),
                                IbValue::List(Rc::new(RefCell::new(
                                    w.members.clone(),
                                ))),
                            ),
                            (k("entries"), IbValue::Dict(Rc::new(RefCell::new(entries)))),
                        ])
                    }
                    None => IbValue::None_,
                }
            };
            let subject_form = w_entries_form(&st.words, &f.s, &f.world);
            let object_form = w_entries_form(&st.words, &f.o, &f.world);
            Ok(IbValue::dict_new(vec![
                (k("id"), IbValue::Str(f.id.clone())),
                (k("world"), IbValue::Str(f.world.clone())),
                (k("s"), IbValue::Str(f.s.clone())),
                (k("r"), IbValue::Str(f.r.clone())),
                (k("o"), IbValue::Str(f.o.clone())),
                (k("source"), IbValue::Str(f.source.clone())),
                (k("status"), IbValue::Str(f.status.clone())),
                (k("subject"), word_value(&st, &f.s)),
                (k("object"), word_value(&st, &f.o)),
                (k("subject_form"), subject_form),
                (k("object_form"), object_form),
                (
                    k("relation"),
                    st.relations
                        .iter()
                        .find(|(n, _)| n == &f.r)
                        .map(|(_, rec)| {
                            IbValue::dict_new(vec![
                                (k("type"), IbValue::Str(f.r.clone())),
                                (k("semantics"), IbValue::Str(rec.semantics.clone())),
                                (k("transitive"), IbValue::Bool(rec.transitive)),
                                (k("multi_valued"), IbValue::Bool(rec.multi_valued)),
                            ])
                        })
                        .unwrap_or(IbValue::None_),
                ),
                (
                    k("world_ctx"),
                    st.worlds
                        .iter()
                        .find(|(n, _)| n == &f.world)
                        .map(|(_, w)| {
                            IbValue::dict_new(vec![
                                (k("name"), IbValue::Str(f.world.clone())),
                                (k("description"), IbValue::Str(w.description.clone())),
                                (k("size_rank"), IbValue::Int(w.size_rank)),
                            ])
                        })
                        .unwrap_or(IbValue::None_),
                ),
            ]))
        }
        // 未知方法 = 显式错误（打破清单 #6：旧 catch-all 静默 None_）
        _ => Err(runtime_error(ErrorKind::AttributeError, "attribute not found")),
    }
}

/// 词条目 entries 面查询（{world: {form, self_ref}} 跨世界词形；未登记 = 空
/// dict[合法态——Python entries.get(world, {}) 语义]）。
fn w_entries_form(
    words: &[(String, KbWord)],
    lex: &str,
    world: &str,
) -> IbValue {
    match words.iter().find(|(n, _)| n == lex) {
        Some((_, w)) => match w.entries.iter().find(|(ek, _)| ek == &IbValue::Str(world.to_string())) {
            Some((_, ev)) => ev.clone(),
            None => IbValue::Dict(Rc::new(RefCell::new(Vec::new()))),
        },
        None => IbValue::Dict(Rc::new(RefCell::new(Vec::new()))),
    }
}

/// dict 键助手（局部闭包面——dispatch 各分支复用）。
fn k(s: &str) -> IbValue {
    IbValue::Str(s.to_string())
}

/// 余弦相似度（KB 嵌入面内部——内容信号非判定；零范数 = -inf 由调用方
/// fail-fast 面处理[同 Python KB._cosine 契约；mock 契约保证非零范数]）。
fn kb_cosine(a: &[f64], b: &[f64]) -> f64 {
    let mut dot = 0.0;
    let mut na = 0.0;
    let mut nb = 0.0;
    for i in 0..a.len() {
        dot += a[i] * b[i];
        na += a[i] * a[i];
        nb += b[i] * b[i];
    }
    let denom = (na.sqrt()) * (nb.sqrt());
    if denom == 0.0 {
        return f64::NEG_INFINITY;
    }
    dot / denom
}

/// 数值向量提取（vector 值或数值 List——set_embedding 参数面）。
fn numeric_vec(v: &IbValue) -> Option<Vec<f64>> {
    match v {
        IbValue::Tensor(t) => t.to_1d().map(|v| v.to_vec()),
        IbValue::List(items) => {
            let mut out = Vec::new();
            for x in items.borrow().iter() {
                match x {
                    IbValue::Int(i) => out.push(*i as f64),
                    IbValue::Float(f) => out.push(*f),
                    _ => return None,
                }
            }
            (!out.is_empty()).then_some(out)
        }
        _ => None,
    }
}
