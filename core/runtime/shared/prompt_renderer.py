"""
core/runtime/shared/prompt_renderer.py — unified prompt rendering.

This module is the single authority for converting an IBCI value into
LLM-visible text or multi-modal content blocks.  It replaces the scattered
``_obj_to_prompt_str`` / ``_obj_to_payload`` implementations in the LLM
executor and the intent system.

The renderer is protocol-aware: when a SpecRegistry is supplied, it uses
``satisfies_protocol`` to decide whether the value participates in the
``payload_prompt`` protocol before dispatching to the corresponding method.
This is the first step toward making prompt protocols a kernel-level
abstraction rather than magic dunder strings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.runtime.observability.diagnostics import kernel_diagnostic
from core.base.diagnostics.codes import KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK


class PromptRenderer:
    """Stateless prompt renderer.

    All methods are static; the class exists as a namespace and as the
    future extension point for user-defined prompt protocols.
    """

    @staticmethod
    def to_prompt_str(val: Any, registry: Any = None) -> str:
        """Convert a value to plain prompt text.

        Resolution order:
        1. ``__to_prompt__`` via the unified object receive() protocol.
        2. ``to_native()`` fallback for primitive IbObjects.
        3. ``str()`` last resort.
        """
        # Try __to_prompt__ through receive() (unified protocol dispatch)
        if hasattr(val, 'receive'):
            try:
                result = val.receive('__to_prompt__', [])
                if hasattr(result, 'to_native'):
                    return str(result.to_native())
                return str(result)
            except AttributeError:
                # Protocol missing -> fallback; user method bugs fail-fast.
                pass

        if hasattr(val, 'to_native'):
            try:
                return str(val.to_native())
            except AttributeError:
                pass

        return str(val)

    @staticmethod
    def to_payload(
        val: Any,
        registry: Any = None,
    ) -> Union[str, Dict[str, Any], List[Dict[str, Any]]]:
        """Convert a value to a prompt content block.

        Resolution order:
        1. ``__payload_prompt__`` via receive() — when the type satisfies the
           ``payload_prompt`` protocol (or the method exists).
        2. Fallback to :meth:`to_prompt_str`.

        The protocol check is advisory; the actual dispatch still goes through
        ``receive()`` to preserve existing vtable behaviour.
        """
        if hasattr(val, 'receive'):
            spec = None
            ib_class = getattr(val, 'ib_class', None)
            if ib_class is not None:
                spec = getattr(ib_class, 'spec', None)
            can_payload = False
            if registry is not None and spec is not None:
                if not hasattr(registry, 'satisfies_protocol'):
                    get_meta = getattr(registry, 'get_metadata_registry', None)
                    if get_meta is not None:
                        registry = get_meta()
                can_payload = registry.satisfies_protocol(spec, 'payload_prompt')
            elif hasattr(val, 'ib_class') and getattr(val, 'ib_class', None) is not None:
                can_payload = PromptRenderer._has_method(val, '__payload_prompt__')
            else:
                # No type information: preserve legacy behaviour of attempting
                # the payload protocol whenever receive() exists.
                can_payload = True
            if can_payload:
                try:
                    result = val.receive('__payload_prompt__', [])
                    if result is not None:
                        if hasattr(result, 'to_native'):
                            native = result.to_native()
                            if isinstance(native, (dict, list)):
                                return native
                            return str(native)
                        if isinstance(result, (dict, list)):
                            return result
                        return str(result)
                except AttributeError:
                    pass
                except Exception as e:
                    kernel_diagnostic(
                        code=KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK,
                        detail={"error": repr(e)},
                        message=(
                            f"__payload_prompt__ dispatch failed, "
                            f"falling back to text: {e!r}"
                        ),
                    )

        return PromptRenderer.to_prompt_str(val, registry=registry)

    @staticmethod
    def _has_method(val: Any, name: str) -> bool:
        ib_class = getattr(val, 'ib_class', None)
        if ib_class is None:
            return False
        lookup = getattr(ib_class, 'lookup_method', None)
        if lookup is None:
            return False
        return lookup(name) is not None
