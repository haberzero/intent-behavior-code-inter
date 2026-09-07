"""api_config.json 加载与校验器。

把 api_config.json 从"脚本级约定"提升为 ai 模块原生一等机制：``ai.load_project_config``
（显式加载项目根配置）/ ``ai.load_config``（指定路径）经本模块读取、解析、校验配置，
失败时 fail-fast（带 CFG_ 诊断码），不静默回退 mock。

schema（完备形态）::

    {
      "defaults": {                       # 可选；全局默认
        "timeout": 30.0,                  # number（默认 30.0）
        "retry": 3,                       # int（默认 3）
        "auto_intent_injection": true,    # bool（默认 true）
        "mock": false                     # bool（默认 false；显式 mock 声明，替代字符串嗅探）
      },
      "providers": {                      # 可选；连接层（base_url + api_key）
        "ollama": { "base_url": "http://localhost:11434/v1", "api_key": "{env:OLLAMA_KEY}" }
      },
      "models": {                         # 可选；命名模型（引用 provider + 模型名 + 每模型参数）
        "default": { "provider": "ollama", "model": "qwen3-8b", "reasoning": false },
        "local":   { "provider": "ollama", "model": "qwen3-8b", "timeout": 60.0,
                     "max_tokens": 2048 }
      },
      "default_model": "default"          # 必需；字符串引用 models，或对象形态（直接含连接信息）
    }

兼容旧式（无 providers/models，直接 default_model 对象）::

    { "default_model": { "base_url": "...", "api_key": "...", "model": "..." } }

env 引用：``{env:VAR}`` 在 providers/models 的 base_url/api_key 字段加载时解析，
变量不存在 fail-fast（CFG_CONFIG_ENV_VAR_MISSING）。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from core.base.diagnostics.codes import (
    CFG_CONFIG_ENV_VAR_MISSING,
    CFG_CONFIG_INVALID_FIELD_TYPE,
    CFG_CONFIG_UNKNOWN_FIELD,
    CFG_CONFIG_INVALID_JSON,
    CFG_CONFIG_MISSING_DEFAULT,
    CFG_CONFIG_MISSING_FIELD,
    CFG_CONFIG_MODEL_NOT_OBJECT,
    CFG_CONFIG_NOT_FOUND,
    CFG_CONFIG_NOT_OBJECT,
    CFG_CONFIG_UNKNOWN_MODEL_REF,
    CFG_CONFIG_UNKNOWN_PROVIDER,
)
from core.kernel.issue import InterpreterError

from ibci_modules.ibci_ai.config_normalize import (
    _DEFAULT_TIMEOUT,
    _DEFAULT_RETRY,
    _DEFAULT_AUTO_INTENT,
    _TEMPERATURE_RANGE,
    _TOP_P_RANGE,
)

_ENV_PATTERN = re.compile(r"\{env:([A-Z_][A-Z0-9_]*)\}")

_DEFAULT_MOCK = False
_DEFAULT_REASONING = False

# model 条目允许字段（未知字段 fail-fast 的 allowlist——配置面可审计性纪律）
_ALLOWED_MODEL_FIELDS = frozenset({
    "model", "provider", "base_url", "api_key", "timeout", "reasoning",
    "max_tokens", "temperature", "top_p", "top_k", "seed", "extra_body", "kind",
})


def _resolve_env(value: Any, context: str) -> str:
    """解析 ``{env:VAR}`` 引用；非字符串原样透传，VAR 缺失或格式非法 fail-fast。

    格式非法（变量名非 ``[A-Z_][A-Z0-9_]*``，如小写/连字符/点号）与变量缺失同样
    fail-fast——静默把 ``{env:...}`` 当字面量透传给 provider 会在调用期才暴露
    难定位的鉴权/连接失败。
    """
    if not isinstance(value, str):
        return value

    def _sub(m: "re.Match[str]") -> str:
        var = m.group(1)
        if var not in os.environ:
            raise InterpreterError(
                f"{context}: 环境变量 '{var}' 未设置",
                error_code=CFG_CONFIG_ENV_VAR_MISSING,
            )
        return os.environ[var]

    result = _ENV_PATTERN.sub(_sub, value)
    if "{env:" in result:
        raise InterpreterError(
            f"{context}: 环境变量引用格式非法: {value}（变量名须为大写下划线）",
            error_code=CFG_CONFIG_ENV_VAR_MISSING,
        )
    return result


class ApiConfig:
    """``api_config.json`` 加载与校验器（单一职责：读取 + 解析 + 校验 + env 解析）。

    路径解析由调用方（``AIPlugin.load_project_config`` / ``AIPlugin.load_config``）负责；
    本类只处理已定位的文件或已加载的 dict。
    """

    @classmethod
    def load(cls, path: str) -> Dict[str, Any]:
        """读取 + 解析 + 校验 ``api_config.json``，返回结构化配置 dict。

        失败 raise ``InterpreterError(error_code=CFG_xxx)``（fail-fast）。
        """
        if not os.path.isfile(path):
            raise InterpreterError(
                f"配置文件不存在: {path}",
                error_code=CFG_CONFIG_NOT_FOUND,
            )
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise InterpreterError(
                f"配置文件 JSON 解析失败: {path}: {e}",
                error_code=CFG_CONFIG_INVALID_JSON,
            ) from e
        return cls.validate(data)

    @classmethod
    def validate(cls, data: Any) -> Dict[str, Any]:
        """校验配置 schema，返回结构化配置 dict。

        返回结构：``{"defaults": {...}, "default_model": {...}, "models": {NAME: {...}}}``。
        每个模型 dict 已解析 env 引用、补全默认值（timeout/reasoning）。
        """
        if not isinstance(data, dict):
            raise InterpreterError(
                "配置顶层必须是 JSON 对象",
                error_code=CFG_CONFIG_NOT_OBJECT,
            )

        defaults = cls._validate_defaults(data.get("defaults"))
        providers = cls._validate_providers(data.get("providers"))
        models = cls._validate_models(data.get("models"), providers, defaults)

        if "default_model" not in data:
            raise InterpreterError(
                "配置缺少 default_model 字段",
                error_code=CFG_CONFIG_MISSING_DEFAULT,
            )

        dm = data["default_model"]
        if isinstance(dm, str):
            if dm not in models:
                raise InterpreterError(
                    f"default_model 引用的命名模型 '{dm}' 不存在",
                    error_code=CFG_CONFIG_UNKNOWN_MODEL_REF,
                )
            if models[dm].get("kind") == "embedding":
                raise InterpreterError(
                    f"default_model 不得引用 embedding 模型 '{dm}'"
                    "（embedding 面无默认模型概念，调用侧显式选模型）",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            default_model = models[dm]
        elif isinstance(dm, dict):
            default_model = cls._validate_model_entry(dm, "default_model", providers, defaults)
        else:
            raise InterpreterError(
                "default_model 必须是对象或命名模型引用字符串",
                error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
            )

        return {
            "defaults": defaults,
            "default_model": default_model,
            "models": models,
        }

    @classmethod
    def _validate_defaults(cls, raw: Any) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "timeout": _DEFAULT_TIMEOUT,
            "retry": _DEFAULT_RETRY,
            "auto_intent_injection": _DEFAULT_AUTO_INTENT,
            "mock": _DEFAULT_MOCK,
        }
        if raw is None:
            return result
        if not isinstance(raw, dict):
            raise InterpreterError(
                "defaults 必须是 JSON 对象",
                error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
            )
        cls._check_number(raw, "defaults", "timeout", result)
        cls._check_int(raw, "defaults", "retry", result)
        cls._check_bool(raw, "defaults", "auto_intent_injection", result)
        cls._check_bool(raw, "defaults", "mock", result)
        return result

    @classmethod
    def _require_nonempty(cls, value: Any, context: str, field: str) -> str:
        """校验字段为**非空**字符串（空白也拒绝）——空凭据静默透传会在调用期
        产生无诊断码的泛化错误，与 fail-fast 契约不符。"""
        if not isinstance(value, str):
            raise InterpreterError(
                f"{context}.{field} 必须是字符串",
                error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
            )
        if not value.strip():
            raise InterpreterError(
                f"{context}.{field} 不能为空",
                error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
            )
        return value

    @classmethod
    def _validate_providers(cls, raw: Any) -> Dict[str, Dict[str, Any]]:
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise InterpreterError(
                "providers 必须是 JSON 对象",
                error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
            )
        result: Dict[str, Dict[str, Any]] = {}
        for name, prov in raw.items():
            if not isinstance(prov, dict):
                raise InterpreterError(
                    f"providers.{name} 必须是 JSON 对象",
                    error_code=CFG_CONFIG_MODEL_NOT_OBJECT,
                )
            for field in ("base_url", "api_key"):
                if field not in prov:
                    raise InterpreterError(
                        f"providers.{name} 缺少必要字段 {field}",
                        error_code=CFG_CONFIG_MISSING_FIELD,
                    )
                cls._require_nonempty(prov[field], f"providers.{name}", field)
            result[name] = {
                "base_url": _resolve_env(prov["base_url"], f"providers.{name}.base_url"),
                "api_key": _resolve_env(prov["api_key"], f"providers.{name}.api_key"),
            }
        return result

    @classmethod
    def _validate_models(
        cls, raw: Any, providers: Dict[str, Dict[str, Any]], defaults: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise InterpreterError(
                "models 必须是 JSON 对象",
                error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
            )
        result: Dict[str, Dict[str, Any]] = {}
        for name, model in raw.items():
            result[name] = cls._validate_model_entry(model, f"models.{name}", providers, defaults)
        return result

    @classmethod
    def _validate_model_entry(
        cls, model: Any, context: str, providers: Dict[str, Dict[str, Any]], defaults: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not isinstance(model, dict):
            raise InterpreterError(
                f"{context} 必须是 JSON 对象",
                error_code=CFG_CONFIG_MODEL_NOT_OBJECT,
            )

        if "model" not in model:
            raise InterpreterError(
                f"{context} 缺少必要字段 model",
                error_code=CFG_CONFIG_MISSING_FIELD,
            )
        cls._require_nonempty(model["model"], context, "model")
        result: Dict[str, Any] = {"model": model["model"]}

        # 连接信息：provider 引用 或 直接 base_url/api_key
        if "provider" in model:
            prov_name = model["provider"]
            if not isinstance(prov_name, str):
                raise InterpreterError(
                    f"{context}.provider 必须是字符串",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            if prov_name not in providers:
                raise InterpreterError(
                    f"{context} 引用的 provider '{prov_name}' 不存在",
                    error_code=CFG_CONFIG_UNKNOWN_PROVIDER,
                )
            result["base_url"] = providers[prov_name]["base_url"]
            result["api_key"] = providers[prov_name]["api_key"]
        else:
            for field in ("base_url", "api_key"):
                if field not in model:
                    raise InterpreterError(
                        f"{context} 缺少必要字段 {field}（或 provider 引用）",
                        error_code=CFG_CONFIG_MISSING_FIELD,
                    )
                cls._require_nonempty(model[field], context, field)
            result["base_url"] = _resolve_env(model["base_url"], f"{context}.base_url")
            result["api_key"] = _resolve_env(model["api_key"], f"{context}.api_key")

        # timeout（可选，覆盖 defaults）
        timeout = model.get("timeout", defaults["timeout"])
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            raise InterpreterError(
                f"{context}.timeout 必须是数字",
                error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
            )
        result["timeout"] = float(timeout)

        # reasoning（可选，默认 false）
        reasoning = model.get("reasoning", _DEFAULT_REASONING)
        if not isinstance(reasoning, bool):
            raise InterpreterError(
                f"{context}.reasoning 必须是布尔值",
                error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
            )
        result["reasoning"] = reasoning

        # max_tokens（可选；单次生成上限，正整数）
        if "max_tokens" in model:
            mt = model["max_tokens"]
            if not isinstance(mt, int) or isinstance(mt, bool) or mt <= 0:
                raise InterpreterError(
                    f"{context}.max_tokens 必须是正整数",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            result["max_tokens"] = mt

        # 标准生成参数（可选；缺省 = 不发送——采样姿态由 vendor 默认，
        # call_info 记录有效值；标准参数走命名类型化面，不进 extra_body）
        if "temperature" in model:
            t = model["temperature"]
            if not isinstance(t, (int, float)) or isinstance(t, bool) or not (_TEMPERATURE_RANGE[0] <= t <= _TEMPERATURE_RANGE[1]):
                raise InterpreterError(
                    f"{context}.temperature 必须是 [0, 2] 内的数字",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            result["temperature"] = float(t)
        if "top_p" in model:
            tp = model["top_p"]
            if not isinstance(tp, (int, float)) or isinstance(tp, bool) or not (_TOP_P_RANGE[0] <= tp <= _TOP_P_RANGE[1]):
                raise InterpreterError(
                    f"{context}.top_p 必须是 [0, 1] 内的数字",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            result["top_p"] = float(tp)
        if "top_k" in model:
            tk = model["top_k"]
            if not isinstance(tk, int) or isinstance(tk, bool) or tk <= 0:
                raise InterpreterError(
                    f"{context}.top_k 必须是正整数",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            result["top_k"] = tk
        if "seed" in model:
            sd = model["seed"]
            if not isinstance(sd, int) or isinstance(sd, bool) or sd < 0:
                raise InterpreterError(
                    f"{context}.seed 必须是非负整数",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            result["seed"] = sd
        if "extra_body" in model:
            eb = model["extra_body"]
            if not isinstance(eb, dict):
                raise InterpreterError(
                    f"{context}.extra_body 必须是 JSON 对象（vendor 特定参数透传口子）",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            result["extra_body"] = eb

        # kind（可选；模型面判别："chat"（缺省）/ "embedding"）
        kind = model.get("kind", "chat")
        if kind not in ("chat", "embedding"):
            raise InterpreterError(
                f"{context}.kind 必须是 'chat' 或 'embedding'",
                error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
            )
        result["kind"] = kind

        # 未知字段严格性（静默丢弃 → fail-fast：配置面拼写错误/废弃字段
        # 不得无声无息——采样姿态/凭据面的可审计性纪律）
        unknown = sorted(set(model.keys()) - _ALLOWED_MODEL_FIELDS)
        if unknown:
            raise InterpreterError(
                f"{context} 含未知字段 {unknown}（model 条目允许字段：{sorted(_ALLOWED_MODEL_FIELDS)}）",
                error_code=CFG_CONFIG_UNKNOWN_FIELD,
            )

        return result

    @staticmethod
    def _check_number(raw: Dict[str, Any], ctx: str, key: str, out: Dict[str, Any]) -> None:
        if key in raw:
            v = raw[key]
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise InterpreterError(
                    f"{ctx}.{key} 必须是数字",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            out[key] = float(v)

    @staticmethod
    def _check_int(raw: Dict[str, Any], ctx: str, key: str, out: Dict[str, Any]) -> None:
        if key in raw:
            v = raw[key]
            if not isinstance(v, int) or isinstance(v, bool):
                raise InterpreterError(
                    f"{ctx}.{key} 必须是整数",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            out[key] = v

    @staticmethod
    def _check_bool(raw: Dict[str, Any], ctx: str, key: str, out: Dict[str, Any]) -> None:
        if key in raw:
            v = raw[key]
            if not isinstance(v, bool):
                raise InterpreterError(
                    f"{ctx}.{key} 必须是布尔值",
                    error_code=CFG_CONFIG_INVALID_FIELD_TYPE,
                )
            out[key] = v
