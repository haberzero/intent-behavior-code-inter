from typing import Dict, Any, Optional
from core.extension import sdk as ibci

class NetLib:
    def __init__(self):
        self._capabilities = None

    def setup(self, capabilities):
        self._capabilities = capabilities

    @ibci.method("get")
    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        try:
            import requests
            # [ENV FIX] 禁用 SSL 校验以兼容某些受限的本地网络环境
            resp = requests.get(url, headers=headers, timeout=10, verify=False)
            resp.raise_for_status()
            return resp.text
        except ImportError:
            return f"[MOCK GET] {url}"
        except Exception as e:
            from core.domain.issue import InterpreterError
            raise InterpreterError(f"Network GET failed: {str(e)}")

    @ibci.method("post")
    def post(self, url: str, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        try:
            import requests
            # [ENV FIX] 禁用 SSL 校验
            resp = requests.post(url, json=body, headers=headers, timeout=10, verify=False)
            resp.raise_for_status()
            return resp.json()
        except ImportError:
            return {"mock": "post", "url": url}
        except Exception as e:
            from core.domain.issue import InterpreterError
            raise InterpreterError(f"Network POST failed: {str(e)}")

def create_implementation():
    return NetLib()
