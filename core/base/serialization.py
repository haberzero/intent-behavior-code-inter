from typing import Dict, Any, List, Optional, Union
import uuid
import hashlib
from enum import Enum

class BaseFlatSerializer:
    """
    扁平化序列化基类：提供通用的池化、UID 管理和基础值处理逻辑。
    该类位于 foundation 层，不依赖 compiler 或 runtime，确保物理隔离。
    """
    def __init__(self):
        self.type_pool: Dict[str, Any] = {}
        self.external_assets: Dict[str, str] = {} # [IES 2.2] 存储外部文本资产: uid -> content
        self.type_map: Dict[int, str] = {} # 映射内存 ID 到稳定 UID
        
    def _generate_deterministic_uid(self, prefix: str, content: str) -> str:
        """[IES 2.1] 生成确定性 UID，基于内容的 SHA-256 哈希"""
        h = hashlib.sha256(content.encode('utf-8')).hexdigest()
        return f"{prefix}_{h[:16]}"

    def _process_value(self, value: Any) -> Any:
        """通用的基础值处理逻辑"""
        if isinstance(value, list):
            return [self._process_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._process_value(v) for k, v in value.items()}
        elif isinstance(value, Enum):
            return value.name
        elif isinstance(value, str):
            return self._process_text_asset(value)
        elif hasattr(value, "__dict__"): 
            # 这里的 vars(value) 可能会包含非序列化内容，子类可以覆盖此方法
            return {k: self._process_value(v) for k, v in vars(value).items()}
        return value

    def _process_text_asset(self, text: str) -> Any:
        """[IES 2.2 Security Update] 文本资产化处理"""
        if not isinstance(text, str):
            return text
            
        # 安全阈值：超过 128 字符，或包含可能引起 JSON 冲突的字符
        if len(text) > 128 or '\n' in text or '\"' in text:
            # 检查是否已经资产化过
            text_id = id(text)
            if text_id in self.type_map:
                return {"_type": "ext_ref", "uid": self.type_map[text_id]}
                
            # [IES 2.1] 改为确定性哈希，确保 Prompt Cache 命中率
            uid = self._generate_deterministic_uid("asset", text)
            self.type_map[text_id] = uid
            self.external_assets[uid] = text
            return {"_type": "ext_ref", "uid": uid}
        return text
