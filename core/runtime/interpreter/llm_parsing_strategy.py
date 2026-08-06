"""
LLM Result Parsing Strategy Pattern

This module implements a chain of responsibility pattern for parsing LLM results.
Each strategy attempts to parse the raw LLM response using a specific method
(Axiom, VTable, Default). If a strategy cannot handle the result, the next
strategy in the chain is tried.

Refactored from llm_executor.py:366-478 to improve maintainability and testability.
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, TYPE_CHECKING
import warnings
from core.runtime.shared.llm_result import LLMResult
from core.runtime.objects.kernel.base import IbObject

if TYPE_CHECKING:
    from core.runtime.interfaces import Registry
    from core.runtime.interfaces import IExecutionContext


class ParsingStrategy(ABC):
    """
    Abstract base class for LLM result parsing strategies.

    Each strategy implements the chain of responsibility pattern:
    - can_handle: Check if this strategy can handle the given type
    - parse: Attempt to parse the raw result
    """

    def __init__(self, registry: 'Registry'):
        self.registry = registry

    @abstractmethod
    def can_handle(self, raw_res: str, type_name: str) -> bool:
        """
        Check if this strategy can handle the given type.

        Args:
            raw_res: Raw LLM response string
            type_name: Expected type name

        Returns:
            True if this strategy should attempt to parse the result
        """
        pass

    @abstractmethod
    def parse(self, raw_res: str, type_name: str, node_uid: str,
              execution_context: Optional['IExecutionContext'] = None) -> Optional[LLMResult]:
        """
        Attempt to parse the raw LLM result.

        Args:
            raw_res: Raw LLM response string
            type_name: Expected type name
            node_uid: Node unique identifier
            execution_context: Optional execution context

        Returns:
            LLMResult if successful, None if this strategy cannot parse
        """
        pass


class AxiomParsingStrategy(ParsingStrategy):
    """
    Parse LLM result using Axiom-based type system.

    This strategy uses the metadata registry to find type descriptors
    and uses either from_prompt or parser capabilities to convert
    the raw LLM response into typed values.
    """

    def can_handle(self, raw_res: str, type_name: str) -> bool:
        """Check if we have a registered axiom for this type."""
        if not type_name:
            return False

        meta_reg = self.registry.get_metadata_registry()
        if not meta_reg:
            return False

        descriptor = meta_reg.resolve(type_name)

        # Handle generic types (e.g., "dict[any,any]")
        if descriptor is None and '[' in type_name:
            base_name = type_name.split('[')[0]
            descriptor = meta_reg.resolve(base_name)

        return descriptor is not None

    def parse(self, raw_res: str, type_name: str, node_uid: str,
              execution_context: Optional['IExecutionContext'] = None) -> Optional[LLMResult]:
        """Parse using Axiom capabilities (from_prompt or parser)."""
        # Normalize type_name: 'type_root.str' -> 'str', 'type_pkg.cls' -> 'pkg.cls'
        if type_name and type_name.startswith("type_"):
            type_name = type_name[5:]
            if type_name.startswith("root."):
                type_name = type_name[5:]

        meta_reg = self.registry.get_metadata_registry()
        if not meta_reg:
            return None

        descriptor = meta_reg.resolve(type_name)

        # Handle generic types (Bug #2 fix)
        if descriptor is None and type_name and '[' in type_name:
            base_name = type_name.split('[')[0]
            descriptor = meta_reg.resolve(base_name)

        if not descriptor:
            return None

        # Try from_prompt capability first
        from_prompt_cap = meta_reg.get_from_prompt_cap(descriptor)
        if from_prompt_cap:
            success, result = from_prompt_cap.from_prompt(raw_res, descriptor)
            if success:
                return LLMResult.success_result(
                    value=self.registry.box(result),
                    raw_response=raw_res
                )
            else:
                return LLMResult.uncertain_result(
                    raw_response=raw_res,
                    retry_hint=result
                )

        # Try parser capability
        parser = meta_reg.get_parser_cap(descriptor)
        if parser:
            try:
                val = parser.parse_value(raw_res)
                return LLMResult.success_result(
                    value=self.registry.box(val),
                    raw_response=raw_res
                )
            except Exception as e:
                return LLMResult.uncertain_result(
                    raw_response=raw_res,
                    retry_hint=f"LLM 返回值类型转换失败：期望 {type_name}。详细: {str(e)}"
                )

        return None


class VTableParsingStrategy(ParsingStrategy):
    """
    Parse LLM result using user-defined __from_prompt__ method.

    This strategy looks for custom __from_prompt__ methods defined
    in user IBCI classes. The method should return (bool, any) where
    the bool indicates success and any is the parsed value or error hint.

    Design 2 improvement: Auto-boxing basic values into class instances.
    """

    def can_handle(self, raw_res: str, type_name: str) -> bool:
        """Check if we have a user class with __from_prompt__ method."""
        if not type_name:
            return False

        ib_class = self.registry.get_class(type_name)
        if not ib_class:
            return False

        method = ib_class.lookup_method('__from_prompt__')
        return method is not None

    def parse(self, raw_res: str, type_name: str, node_uid: str,
              execution_context: Optional['IExecutionContext'] = None) -> Optional[LLMResult]:
        """Parse using user-defined __from_prompt__ method.

        Enhanced: runs __validate_prompt__ pre-flight check if defined.
        """
        ib_class = self.registry.get_class(type_name)
        if not ib_class:
            return None

        method = ib_class.lookup_method('__from_prompt__')
        if not method:
            return None

        # --- __validate_prompt__ pre-flight (optional protocol) ---
        validate_method = ib_class.lookup_method('__validate_prompt__')
        if validate_method:
            try:
                raw_arg = self.registry.box(raw_res)
                validate_result = validate_method.call(ib_class, [raw_arg])
                if hasattr(validate_result, 'elements') and len(validate_result.elements) >= 2:
                    is_valid = validate_result.elements[0]
                    error_desc = validate_result.elements[1]
                    is_valid_native = is_valid.to_native() if isinstance(is_valid, IbObject) else bool(is_valid)
                    if not is_valid_native:
                        error_str = error_desc.to_native() if isinstance(error_desc, IbObject) else str(error_desc)
                        return LLMResult.uncertain_result(
                            raw_response=raw_res,
                            retry_hint=f"Validation failed: {error_str}"
                        )
            except Exception as e:
                warnings.warn(
                    f"__validate_prompt__ failed for '{type_name}': {e}",
                    stacklevel=2,
                )
                # __validate_prompt__ exception is non-fatal — proceed to __from_prompt__

        try:
            raw_arg = self.registry.box(raw_res)
            result_obj = method.call(ib_class, [raw_arg])

            # Expected return: tuple (bool, any)
            if not (hasattr(result_obj, 'elements') and len(result_obj.elements) >= 2):
                return None

            success_val = result_obj.elements[0]
            parsed_val = result_obj.elements[1]
            success_native = success_val.to_native() if isinstance(success_val, IbObject) else bool(success_val)

            if success_native:
                # Design 2: Auto-box basic values into class instances
                is_instance_of_target = (
                    isinstance(parsed_val, IbObject) and
                    parsed_val.ib_class is ib_class
                )

                if not is_instance_of_target:
                    # Try to auto-box the value into a class instance
                    parsed_val = self._auto_box_value(parsed_val, ib_class, execution_context)

                return LLMResult.success_result(
                    value=parsed_val,
                    raw_response=raw_res
                )
            else:
                hint = parsed_val.to_native() if isinstance(parsed_val, IbObject) else str(parsed_val)
                return LLMResult.uncertain_result(
                    raw_response=raw_res,
                    retry_hint=str(hint)
                )

        except Exception as e:
            warnings.warn(
                f"vtable __from_prompt__ failed for '{type_name}': {e}",
                stacklevel=2,
            )
            return None

    def _auto_box_value(self, parsed_val: Any, ib_class: Any,
                        execution_context: Optional['IExecutionContext']) -> Any:
        """
        Auto-box a basic value into a class instance.

        Tries two strategies:
        1. Call __init__ with the parsed value as argument
        2. Create empty instance and set parsed value as first field
        """
        try:
            # Try calling __init__ with the parsed value
            auto_instance = ib_class.instantiate([parsed_val], context=execution_context)
            return auto_instance
        except Exception as e:
            # 首策略失败是设计内路径，尝试第二策略（空实例 + 首字段注入）
            try:
                auto_instance = ib_class.instantiate([], context=execution_context)
                if ib_class.default_fields:
                    first_field = next(iter(ib_class.default_fields))
                    auto_instance.fields[first_field] = parsed_val
                return auto_instance
            except Exception as e2:
                # 两策略均失败，返回原始值（下游类型校验承接）
                return parsed_val


class DefaultParsingStrategy(ParsingStrategy):
    """
    Default fallback parsing strategy.

    兜底策略：无真实输出契约（auto/any/无类型/行为本体）时把原始字符串 box 成 str；
    已声明的具体类型却无任何解析能力时返回 uncertain（编译期
    SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE 已拦截主要路径，此处兜底防绕过路径
    静默流入错误类型）。
    """

    def can_handle(self, raw_res: str, type_name: str) -> bool:
        """Default strategy always returns True (fallback)."""
        return True

    def _is_declared_unparseable(self, type_name: str) -> bool:
        """type_name 是否指代一个已声明但无解析能力的具体类型。

        排除无契约情形：动态类型（any/auto/fn）与行为本体（behavior/fn_callable，
        ``-> any`` 行为运行时 type_hint 即裸 'behavior'）。仅当解析到具体 descriptor
        且无 from_prompt/parser 能力时判定为不可解析。
        """
        meta_reg = self.registry.get_metadata_registry()
        if meta_reg is None:
            return False
        descriptor = meta_reg.resolve(type_name)
        # 泛型形态（如 "list[int]"）无精确 descriptor，回退基名（与 Axiom 策略一致）。
        if descriptor is None and '[' in type_name:
            descriptor = meta_reg.resolve(type_name.split('[')[0])
        if descriptor is None:
            return False
        base = descriptor.get_base_name()
        if base in ("behavior", "fn_callable", "any", "auto"):
            return False
        if meta_reg.get_from_prompt_cap(descriptor) is not None:
            return False
        if meta_reg.get_parser_cap(descriptor) is not None:
            return False
        return True

    def parse(self, raw_res: str, type_name: str, node_uid: str,
              execution_context: Optional['IExecutionContext'] = None) -> Optional[LLMResult]:
        """无契约时返回字符串 box；已声明但不可解析的具体类型返回 uncertain。"""
        if type_name and self._is_declared_unparseable(type_name):
            return LLMResult.uncertain_result(
                raw_response=raw_res,
                retry_hint=(
                    f"Declared LLM output type '{type_name}' has no parsing capability "
                    f"(no __from_prompt__/parser). Add one, or declare "
                    f"'-> str'/'auto'/'any' if the raw string is intended."
                ),
            )
        return LLMResult.success_result(
            value=self.registry.box(raw_res),
            raw_response=raw_res
        )


class LLMResultParser:
    """
    Chain of responsibility coordinator for parsing LLM results.

    This class manages a chain of parsing strategies and applies them
    in order until one successfully parses the result.

    Strategy order:
    1. AxiomParsingStrategy - Try built-in type system
    2. VTableParsingStrategy - Try user-defined __from_prompt__
    3. DefaultParsingStrategy - Fallback to raw string
    """

    def __init__(self, registry: 'Registry'):
        """
        Initialize the parser with a chain of strategies.

        Args:
            registry: Type registry for resolving types
        """
        self.registry = registry
        self.strategies = [
            AxiomParsingStrategy(registry),
            VTableParsingStrategy(registry),
            DefaultParsingStrategy(registry)
        ]

    def parse_result(self, raw_res: str, type_name: str, node_uid: str,
                     execution_context: Optional['IExecutionContext'] = None) -> LLMResult:
        """
        Parse LLM result using the chain of strategies.

        Args:
            raw_res: Raw LLM response string
            type_name: Expected type name
            node_uid: Node unique identifier
            execution_context: Optional execution context

        Returns:
            LLMResult with parsed value or uncertainty
        """
        for strategy in self.strategies:
            if strategy.can_handle(raw_res, type_name):
                result = strategy.parse(raw_res, type_name, node_uid, execution_context)
                if result is not None:
                    return result

        # DefaultParsingStrategy.can_handle 恒为 True，循环必然在链末返回。
