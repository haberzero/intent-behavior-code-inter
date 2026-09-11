//! Rust 原生 KB 值（第四批 增量 2——去 Host 化：世界模型知识图谱执行面）。
//!
//! 转录自 Python 参考内核 `core/runtime/objects/primitives/knowledge.py`（IbKnowledge
//! 治理词表 / 事实面 / 查找面）：单一权威源 = IBCI KB 声明（治理门 fail-fast +
//! append-only 事实日志 + 确定性序）；Python 参考内核 = 迁移期差分安全网。
//! 零 LLM（机器强制治理门，确定性）。
//!
//! 错误面（登记限制，非本增量范围）：参数形态错误 / 词表未注册 / 重复登记等
//! 治理门失败 = None_ 静默（Rust 解释器无错误传播面——InterpreterError 值语义
//! = 跨切面后续增量；语料无错误探针，数据面无偏离）。

use std::cell::RefCell;
use std::collections::BTreeMap;
use std::rc::Rc;

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
    /// 事实序号（前置自增——首事实 id = "1"）
    pub seq: i64,
}

impl KbState {
    pub fn blank() -> KbState {
        KbState {
            words: Vec::new(),
            relations: Vec::new(),
            worlds: Vec::new(),
            facts: Vec::new(),
            by_pair: BTreeMap::new(),
            by_triple: BTreeMap::new(),
            seq: 0,
        }
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
    kb: &Rc<RefCell<KbState>>,
    method: &str,
    args: &[IbValue],
) -> IbValue {
    match method {
        // 治理词表面（fail-fast 重复登记拒绝 = None_）
        "register_world" => {
            let [IbValue::Str(n), IbValue::Str(d), IbValue::Int(sr)] = args else {
                return IbValue::None_;
            };
            let mut st = kb.borrow_mut();
            if find_name(&st.worlds, n) {
                return IbValue::None_;
            }
            st.worlds
                .push((n.clone(), KbWorld { description: d.clone(), size_rank: *sr }));
            IbValue::None_
        }
        "register_relation" => {
            let [
                IbValue::Str(rt),
                IbValue::Str(sem),
                IbValue::Bool(tr),
                IbValue::Bool(mv),
            ] = args else {
                return IbValue::None_;
            };
            if rt.is_empty() {
                return IbValue::None_;
            }
            let mut st = kb.borrow_mut();
            if find_name(&st.relations, rt) {
                return IbValue::None_;
            }
            st.relations.push((
                rt.clone(),
                KbRelation {
                    semantics: sem.clone(),
                    transitive: *tr,
                    multi_valued: *mv,
                },
            ));
            IbValue::None_
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
                _ => return IbValue::None_,
            };
            if lex.is_empty() {
                return IbValue::None_;
            }
            let mut st = kb.borrow_mut();
            if find_name(&st.words, lex) {
                return IbValue::None_;
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
            IbValue::None_
        }
        // 枚举面（插入序）
        "worlds" => IbValue::list_new(
            kb.borrow()
                .worlds
                .iter()
                .map(|(n, _)| IbValue::Str(n.clone()))
                .collect(),
        ),
        "words" => IbValue::list_new(
            kb.borrow()
                .words
                .iter()
                .map(|(n, _)| IbValue::Str(n.clone()))
                .collect(),
        ),
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
                _ => return IbValue::None_,
            };
            if w.is_empty() || subj.is_empty() || rel.is_empty() || obj.is_empty() {
                return IbValue::None_;
            }
            // source 允许空串（缺省 ""）；status 须非空
            if stt.is_empty() {
                return IbValue::None_;
            }
            let mut st = kb.borrow_mut();
            // 治理门：词表 allowlist（确定性，零 LLM）
            if !find_name(&st.worlds, w)
                || !find_name(&st.relations, rel)
                || !find_name(&st.words, subj)
                || !find_name(&st.words, obj)
            {
                return IbValue::None_;
            }
            // 去重门：同 (world,s,r,o) active 事实机器强制唯一
            let triple_key = (w.clone(), subj.clone(), rel.clone(), obj.clone());
            if st.by_triple.contains_key(&triple_key) {
                return IbValue::None_;
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
            IbValue::Str(fid)
        }
        // 查找面（active 视图）
        "exists" => {
            let [IbValue::Str(w), IbValue::Str(s), IbValue::Str(r), IbValue::Str(o)] = args
            else {
                return IbValue::None_;
            };
            let st = kb.borrow();
            IbValue::Bool(
                st.by_triple
                    .contains_key(&(w.clone(), s.clone(), r.clone(), o.clone())),
            )
        }
        "lookup_pair" => {
            let [IbValue::Str(s), IbValue::Str(r)] = args else {
                return IbValue::None_;
            };
            let st = kb.borrow();
            let ids = st.by_pair.get(&(s.clone(), r.clone()));
            let items: Vec<IbValue> = ids
                .map(|v| v.iter().map(|i| fact_value(&st.facts[*i])).collect())
                .unwrap_or_default();
            IbValue::list_new(items)
        }
        "contradicts" => {
            // 同 (s,r) 已有 active o'≠o 且关系非 multi_valued ⇒ 矛盾
            let [IbValue::Str(s), IbValue::Str(r), IbValue::Str(o)] = args else {
                return IbValue::None_;
            };
            let st = kb.borrow();
            let rel_rec = st.relations.iter().find(|(n, _)| n == r);
            let Some((_, rec)) = rel_rec else {
                return IbValue::None_;
            };
            if rec.multi_valued {
                return IbValue::Bool(false);
            }
            let others = st.by_pair.get(&(s.clone(), r.clone()));
            let conflict = others
                .map(|ids| ids.iter().any(|i| st.facts[*i].o != *o))
                .unwrap_or(false);
            IbValue::Bool(conflict)
        }
        _ => IbValue::None_,
    }
}
