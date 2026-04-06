import re
import json
import ast
from typing import Any, Optional, Union

class FuzzyJsonParser:
    """
     健壮的 JSON 解析器，专门用于从 LLM 杂乱的输出中提取结构化数据。
    支持处理：
    1. Markdown 代码块包裹 (```json ... ```)
    2. 前后缀干扰文本
    3. 边界搜索 ({...} 或 [...] 内容提取)
    
    注意：此解析器包含容错增强机制，用于处理 LLM 可能返回的 Python dict/list 字面量语法。
    这不是严格遵循 RFC 8259 JSON 标准的实现，而是为了提高 LLM 返回解析的成功率。
    严格 JSON 必须使用双引号括起键和字符串值。
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
            
            # 第一尝试：严格 JSON 解析
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
            
            # 第二尝试：Python dict/list 字面量容错解析
            # 注意：这不是严格遵循 RFC 8259 JSON 标准的实现
            # 严格 JSON 必须使用双引号，此处增强仅用于提高 LLM 返回解析的容错率
            try:
                result = FuzzyJsonParser._parse_python_literal(json_str)
                if result is not None:
                    return result
            except (ValueError, SyntaxError):
                pass
            
            raise ValueError(
                f"Found {start_char}{end_char} bounds but content is not valid JSON. "
                f"Strict JSON requires double quotes for keys and string values. "
                f"Content: {json_str[:100]}..."
            )
                
        raise ValueError(f"No {start_char}{end_char} bounds found in text.")
    
    @staticmethod
    def _parse_python_literal(text: str) -> Any:
        """
        尝试解析 Python dict/list 字面量语法。
        
        这是容错增强机制，用于处理 LLM 可能返回的 Python 语法格式：
        - 单引号代替双引号: {'key': 'value'}
        - Python 关键字: True, False, None
        
        注意：这会降低 JSON 格式的严格性，但能显著提高 LLM 返回的解析成功率。
        如果需要严格 JSON，请确保 LLM 返回标准 JSON 格式（双引号）。
        """
        # 首先尝试基本的字符串替换修复
        fixed = FuzzyJsonParser._fix_python_syntax(text)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        
        # 最后尝试 ast.literal_eval（仅用于 Python 语法）
        # 这是最宽松的解析方式
        try:
            result = ast.literal_eval(text)
            # 仅当结果是 dict 或 list 时返回
            if isinstance(result, (dict, list)):
                return result
        except (ValueError, SyntaxError, TypeError):
            pass
        
        return None
    
    @staticmethod
    def _fix_python_syntax(text: str) -> str:
        """
        将 Python dict/list 字面量语法转换为接近 JSON 的格式。
        
        处理的转换：
        1. 单引号 -> 双引号
        2. Python 布尔值 -> JSON 布尔值
        3. Python None -> JSON null
        
        注意：这是简单的正则替换，可能在复杂嵌套情况下不完全准确。
        建议优先使用标准 JSON 格式（双引号）。
        """
        result = text
        
        # Python 关键字转换（需要小心处理避免破坏字符串内容）
        # 匹配完整的单词边界，避免部分替换
        result = re.sub(r'\bTrue\b', 'true', result)
        result = re.sub(r'\bFalse\b', 'false', result)
        result = re.sub(r'\bNone\b', 'null', result)
        
        # 单引号转双引号（需要更复杂的处理避免破坏字符串内容）
        # 这是一个简化的实现，可能在某些边缘情况下不完全准确
        # 更好的方式是完全解析再重新生成
        result = FuzzyJsonParser._quote_to_double(result)
        
        return result
    
    @staticmethod
    def _quote_to_double(text: str) -> str:
        """
        将 Python 单引号字符串转换为 JSON 双引号格式。
        
        这是一个简化的实现，通过追踪字符串边界来处理引号转换。
        注意：对于包含转义字符或特殊格式的字符串可能不完美。
        """
        result = []
        i = 0
        in_string = False
        current_quote = None
        
        while i < len(text):
            char = text[i]
            
            if not in_string:
                if char in ('"', "'"):
                    in_string = True
                    current_quote = char
                    # 将引号统一转换为双引号
                    result.append('"')
                else:
                    result.append(char)
            else:
                if char == current_quote and (i == 0 or text[i-1] != '\\'):
                    # 字符串结束
                    in_string = False
                    current_quote = None
                    result.append('"')
                else:
                    result.append(char)
            
            i += 1
        
        return ''.join(result)
