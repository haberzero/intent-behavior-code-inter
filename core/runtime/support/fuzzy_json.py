import re
import json
from typing import Any, Optional, Union

class FuzzyJsonParser:
    """
    [IES 2.2] 健壮的 JSON 解析器，专门用于从 LLM 杂乱的输出中提取结构化数据。
    支持处理：
    1. Markdown 代码块包裹 (```json ... ```)
    2. 前后缀干扰文本
    3. 基础的 JSON 容错处理
    """
    
    @staticmethod
    def parse(text: str, expected_type: str = "any") -> Any:
        if not text:
            return None
            
        clean_text = text.strip()
        
        # 1. 尝试直接解析 (最快路径)
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            pass
            
        # 2. 移除 Markdown 代码块包裹
        # 匹配 ```json ... ``` 或 ``` ... ```
        code_block_pattern = r'```(?:json|text)?\s*([\s\S]*?)\s*```'
        match = re.search(code_block_pattern, clean_text)
        if match:
            inner_content = match.group(1).strip()
            try:
                return json.loads(inner_content)
            except json.JSONDecodeError:
                clean_text = inner_content # 缩小范围继续尝试
        
        # 3. 根据预期类型进行边界搜索
        if expected_type == "list":
            return FuzzyJsonParser._extract_by_bounds(clean_text, '[', ']')
        elif expected_type == "dict":
            return FuzzyJsonParser._extract_by_bounds(clean_text, '{', '}')
        else:
            # 自动探测：哪个先出现就试哪个
            list_start = clean_text.find('[')
            dict_start = clean_text.find('{')
            
            if list_start != -1 and (dict_start == -1 or list_start < dict_start):
                return FuzzyJsonParser._extract_by_bounds(clean_text, '[', ']')
            elif dict_start != -1:
                return FuzzyJsonParser._extract_by_bounds(clean_text, '{', '}')
                
        raise ValueError(f"Could not extract valid JSON {expected_type} from LLM response.")

    @staticmethod
    def _extract_by_bounds(text: str, start_char: str, end_char: str) -> Any:
        start = text.find(start_char)
        end = text.rfind(end_char)
        
        if start != -1 and end != -1 and end > start:
            json_str = text[start:end+1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                # [Future] 这里可以引入更高级的修复逻辑，目前仅抛出原始错误
                raise ValueError(f"Found {start_char}{end_char} bounds but JSON is malformed: {str(e)}")
                
        raise ValueError(f"No {start_char}{end_char} bounds found in text.")
