//! 序列化 UID（全量 Rust 化·序列化面：确定性哈希 + 稳定 UID）。
//!
//! 对应 Python `core/base/uid.py` 的 UID 生成（node_uid / type_uid / asset_uid）——
//! FlatSerializer 的节点/类型/资产 UID 生成核心。Rust 化后与 Python UID 逐条差分
//! 等价（确定性哈希 = sha256 前 16 hex；稳定 UID = 命名规则）。

use sha2::{Digest, Sha256};

/// 内容哈希前缀（sha256 前 16 hex 字符，UTF-8 编码）。
fn hash_prefix(content: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(content.as_bytes());
    let result = hasher.finalize();
    // 前 16 hex 字符（sha256 hexdigest 前 16）
    let hex: String = result.iter().map(|b| format!("{:02x}", b)).collect();
    hex[..16].to_string()
}

/// AST 节点 UID：`node_<sha256[:16]>`（内容确定性）。
pub fn node_uid(content: &str) -> String {
    format!("node_{}", hash_prefix(content))
}

/// 类型 UID：`type_<module>.<name>`（root 模块退化 `type_root.<name>`）。
pub fn type_uid(module_path: Option<&str>, name: &str) -> String {
    let module = module_path.unwrap_or("root");
    format!("type_{}.{}", module, name)
}

/// 文本资产 UID：`asset_<sha256[:16]>`（内容确定性）。
pub fn asset_uid(text: &str) -> String {
    format!("asset_{}", hash_prefix(text))
}
