from typing import Dict, Any, Optional
from core.extension import ibcext

class NetLib(ibcext.IbPlugin):
    """
    Net 2.1: 网络请求插件。
    """
    def __init__(self):
        super().__init__()

    @ibcext.method("get")
    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        try:
            import requests
            resp = requests.get(url, headers=headers, timeout=10, verify=False)
            resp.raise_for_status()
            return resp.text
        except ImportError:
            return f"[MOCK GET] {url}"
        except Exception as e:
            raise ibcext.PluginError(f"Network GET failed: {str(e)}")

    @ibcext.method("post")
    def post(self, url: str, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        try:
            import requests
            resp = requests.post(url, json=body, headers=headers, timeout=10, verify=False)
            resp.raise_for_status()
            return resp.json()
        except ImportError:
            return {"mock": "post", "url": url}
        except Exception as e:
            raise ibcext.PluginError(f"Network POST failed: {str(e)}")

def create_implementation():
    return NetLib()
