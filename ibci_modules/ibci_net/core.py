"""
ibci_net/core.py

IBCI Net 网络请求插件实现。非侵入层插件，零内核依赖。
依赖可选的 requests 库；未安装时自动降级为 Mock 响应。

功能：
- get/post/put/delete/head：标准 HTTP 方法
- get_json/post_json：自动解析 JSON 响应
- post_form：application/x-www-form-urlencoded 提交
- set_timeout/set_default_headers：会话级配置
- set_bearer_token/set_basic_auth：身份认证配置
"""
from typing import Dict, Any, Optional, List


class NetLib:
    """HTTP 网络请求工具。持有会话级配置（timeout、默认 headers、认证信息）。"""

    def __init__(self):
        self._timeout: float = 10.0
        self._default_headers: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # 会话级配置
    # ------------------------------------------------------------------

    def set_timeout(self, seconds: float) -> None:
        """设置全局请求超时时间（秒）。默认 10.0。"""
        self._timeout = max(0.1, float(seconds))

    def set_default_headers(self, headers: Dict[str, str]) -> None:
        """设置全局默认请求头（每次请求都会附带）。"""
        self._default_headers = dict(headers)

    def set_bearer_token(self, token: str) -> None:
        """设置 Bearer Token 认证头。"""
        self._default_headers["Authorization"] = f"Bearer {token}"

    def set_basic_auth(self, username: str, password: str) -> None:
        """设置 Basic Auth 认证头。"""
        import base64
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._default_headers["Authorization"] = f"Basic {credentials}"

    def clear_auth(self) -> None:
        """清除认证头。"""
        self._default_headers.pop("Authorization", None)

    # ------------------------------------------------------------------
    # HTTP 方法
    # ------------------------------------------------------------------

    def _merge_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        merged = dict(self._default_headers)
        if extra:
            merged.update(extra)
        return merged

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        """发送 GET 请求，返回响应文本。"""
        try:
            import requests
            resp = requests.get(url, headers=self._merge_headers(headers),
                                timeout=self._timeout, verify=False)
            resp.raise_for_status()
            return resp.text
        except ImportError:
            return f"[MOCK GET] {url}"
        except Exception as e:
            raise RuntimeError(f"Network GET failed: {e}")

    def get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """发送 GET 请求，自动解析 JSON 响应为 dict。"""
        try:
            import requests
            resp = requests.get(url, headers=self._merge_headers(headers),
                                timeout=self._timeout, verify=False)
            resp.raise_for_status()
            return resp.json()
        except ImportError:
            return {"mock": "get_json", "url": url}
        except Exception as e:
            raise RuntimeError(f"Network GET_JSON failed: {e}")

    def post(self, url: str, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> str:
        """发送 POST 请求（JSON body），返回响应文本。"""
        try:
            import requests
            resp = requests.post(url, json=body, headers=self._merge_headers(headers),
                                 timeout=self._timeout, verify=False)
            resp.raise_for_status()
            return resp.text
        except ImportError:
            return f"[MOCK POST] {url}"
        except Exception as e:
            raise RuntimeError(f"Network POST failed: {e}")

    def post_json(self, url: str, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """发送 POST 请求（JSON body），自动解析 JSON 响应为 dict。"""
        try:
            import requests
            resp = requests.post(url, json=body, headers=self._merge_headers(headers),
                                 timeout=self._timeout, verify=False)
            resp.raise_for_status()
            return resp.json()
        except ImportError:
            return {"mock": "post_json", "url": url}
        except Exception as e:
            raise RuntimeError(f"Network POST_JSON failed: {e}")

    def post_form(self, url: str, data: Dict[str, str], headers: Optional[Dict[str, str]] = None) -> str:
        """发送 POST 表单请求（application/x-www-form-urlencoded），返回响应文本。"""
        try:
            import requests
            resp = requests.post(url, data=data, headers=self._merge_headers(headers),
                                 timeout=self._timeout, verify=False)
            resp.raise_for_status()
            return resp.text
        except ImportError:
            return f"[MOCK POST_FORM] {url}"
        except Exception as e:
            raise RuntimeError(f"Network POST_FORM failed: {e}")

    def put(self, url: str, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> str:
        """发送 PUT 请求（JSON body），返回响应文本。"""
        try:
            import requests
            resp = requests.put(url, json=body, headers=self._merge_headers(headers),
                                timeout=self._timeout, verify=False)
            resp.raise_for_status()
            return resp.text
        except ImportError:
            return f"[MOCK PUT] {url}"
        except Exception as e:
            raise RuntimeError(f"Network PUT failed: {e}")

    def delete(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        """发送 DELETE 请求，返回响应文本。"""
        try:
            import requests
            resp = requests.delete(url, headers=self._merge_headers(headers),
                                   timeout=self._timeout, verify=False)
            resp.raise_for_status()
            return resp.text
        except ImportError:
            return f"[MOCK DELETE] {url}"
        except Exception as e:
            raise RuntimeError(f"Network DELETE failed: {e}")

    def head(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """发送 HEAD 请求，返回响应头 dict。"""
        try:
            import requests
            resp = requests.head(url, headers=self._merge_headers(headers),
                                 timeout=self._timeout, verify=False)
            return dict(resp.headers)
        except ImportError:
            return {"X-Mock": "head", "X-Url": url}
        except Exception as e:
            raise RuntimeError(f"Network HEAD failed: {e}")

    def get_status_code(self, url: str) -> int:
        """发送 GET 请求，仅返回 HTTP 状态码。"""
        try:
            import requests
            resp = requests.get(url, headers=self._merge_headers(),
                                timeout=self._timeout, verify=False, allow_redirects=False)
            return resp.status_code
        except ImportError:
            return 200
        except Exception as e:
            raise RuntimeError(f"Network status check failed: {e}")


def create_implementation() -> NetLib:
    return NetLib()
