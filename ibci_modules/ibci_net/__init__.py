"""
Net 网络请求插件

纯 Python 实现，零侵入。
"""
from typing import Dict, Any, Optional


class NetLib:
    """
    Net 2.2: 网络请求插件。
    不继承任何核心类，完全独立。
    """
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


def create_implementation():
    return NetLib()
