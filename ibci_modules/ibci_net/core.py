"""
ibci_net/core.py

IBCI Net 插件实现。非侵入层插件，零内核依赖。
依赖可选的 requests 库；未安装时自动降级为 Mock 响应。
"""
from typing import Dict, Any, Optional


class NetLib:
    """HTTP 网络请求工具。"""

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        try:
            import requests
            resp = requests.get(url, headers=headers, timeout=10, verify=False)
            resp.raise_for_status()
            return resp.text
        except ImportError:
            return f"[MOCK GET] {url}"
        except Exception as e:
            raise RuntimeError(f"Network GET failed: {str(e)}")

    def post(self, url: str, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        try:
            import requests
            resp = requests.post(url, json=body, headers=headers, timeout=10, verify=False)
            resp.raise_for_status()
            return resp.json()
        except ImportError:
            return {"mock": "post", "url": url}
        except Exception as e:
            raise RuntimeError(f"Network POST failed: {str(e)}")


def create_implementation() -> NetLib:
    return NetLib()
