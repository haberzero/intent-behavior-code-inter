//! 并行任务池（task_scheduler GIL-free 集成的有状态执行体）：CPU 任务（artifact）
//! 经 submit 入队、run_all 经 Rust 线程 GIL-free 真并行执行（纯 CPU 无宿主服务）。
//!
//! 设计：
//! - 有状态（pyclass）：任务池持有任务队列（submit 入队，run_all 取出并执行）——
//!   task_scheduler 可增量 submit CPU 任务、一次性 run_all 并行执行、按任务 ID 取
//!   结果（区别于 run_artifacts_parallel 的无状态批处理 API）。
//! - GIL-free 真并行：run_all 经 py.allow_threads 释放 GIL，Rust 线程各执行一批
//!   （纯 CPU），按线程序拼接 = 任务序（chunk 按任务序均分）。
//! - 纯 CPU 面：无宿主服务（含宿主服务的任务由单线程 run_artifact 经桥接处理）。

use std::collections::VecDeque;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;

use pyo3::prelude::*;
use pyo3::types::PyList;

use crate::interpreter;

/// 并行任务池：CPU 任务（artifact）submit 入队 → run_all GIL-free 真并行执行。
#[pyclass]
pub struct TaskPool {
    workers: usize,
    queue: Mutex<VecDeque<(u64, String)>>,
    next_id: AtomicU64,
}

#[pymethods]
impl TaskPool {
    /// 创建任务池（workers = 并行线程数）。
    #[new]
    fn new(workers: u32) -> Self {
        Self {
            workers: (workers as usize).max(1),
            queue: Mutex::new(VecDeque::new()),
            next_id: AtomicU64::new(0),
        }
    }

    /// submit 一个 CPU 任务（artifact JSON）→ 返回任务 ID（入队序）。
    fn submit(&self, artifact_json: &str) -> u64 {
        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        self.queue
            .lock()
            .unwrap()
            .push_back((id, artifact_json.to_string()));
        id
    }

    /// 入队任务数（未执行）。
    fn pending(&self) -> usize {
        self.queue.lock().unwrap().len()
    }

    /// run_all：取出全部已 submit 任务，经 Rust 线程 GIL-free 真并行执行 → 返回
    /// list of [task_id, result_list]（按任务 ID 序 = submit 序）。空池 = 空列表。
    fn run_all(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        // 取出全部任务（入队序 = 任务 ID 序）
        let tasks: Vec<(u64, String)> = {
            let mut q = self.queue.lock().unwrap();
            q.drain(..).collect()
        };
        let n = tasks.len();
        if n == 0 {
            return Ok(PyList::empty(py).unbind());
        }
        let w = self.workers.min(n);
        let per = n.div_ceil(w);
        // 均分：chunk i = 任务 i*per..(i+1)*per（chunk 按任务序 → 拼接 = 任务序）
        let chunks: Vec<Vec<(u64, String)>> = (0..w)
            .map(|wi| {
                let lo = wi * per;
                let hi = (lo + per).min(n);
                tasks[lo..hi].to_vec()
            })
            .filter(|c| !c.is_empty())
            .collect();
        // GIL-free 真并行：释放 GIL，Rust 线程各执行一批（纯 CPU 无宿主服务）
        let results: Result<Vec<(u64, Vec<String>)>, crate::errors::ErrorPayload> = py.allow_threads(|| {
            let handles: Vec<std::thread::JoinHandle<Result<Vec<(u64, Vec<String>)>, crate::errors::ErrorPayload>>> =
                chunks
                    .into_iter()
                    .map(|chunk| {
                        std::thread::spawn(move || {
                            let mut out = Vec::new();
                            for (id, js) in chunk {
                                let lines = interpreter::run_artifact(&js, None)?;
                                out.push((id, lines));
                            }
                            Ok(out)
                        })
                    })
                    .collect();
            // 按线程序拼接（chunk 按任务序均分 → 拼接 = 任务序）
            let mut all: Vec<(u64, Vec<String>)> = Vec::new();
            for h in handles {
                let r = h.join().unwrap();
                if let Err(e) = r {
                    return Err(e);
                }
                all.extend(r.unwrap());
            }
            Ok(all)
        });
        // 组装结果：list of [task_id, result_list]（每项 = 一个任务的 print 输出）
        let results = match results {
            Ok(r) => r,
            Err(payload) => return Err(payload.to_pyerr()),
        };
        let list = PyList::empty(py);
        for (id, result) in results {
            let inner = PyList::empty(py);
            for line in result {
                inner.append(line)?;
            }
            let item = PyList::empty(py);
            item.append(id)?;
            item.append(inner)?;
            list.append(item)?;
        }
        Ok(list.unbind())
    }
}
