from typing import Dict, Any, Optional

class NetLib:
    def __init__(self):
        self._capabilities = None

    def setup(self, capabilities):
        self._capabilities = capabilities

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        try:
            import requests
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.text
        except ImportError:
            return f"[MOCK GET] {url}"
        except Exception as e:
            from core.types.exception_types import InterpreterError
            raise InterpreterError(f"Network GET failed: {str(e)}")

    def post(self, url: str, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        try:
            import requests
            resp = requests.post(url, json=body, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except ImportError:
            return {"mock": "post", "url": url}
        except Exception as e:
            from core.types.exception_types import InterpreterError
            raise InterpreterError(f"Network POST failed: {str(e)}")

def create_implementation():
    return NetLib()
