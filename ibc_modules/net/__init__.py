from typing import Dict, Any, Optional
from core.extension import sdk as ibci

class NetLib(ibci.IbPlugin):
    """
    Net 2.1: 网络请求插件。
    """
    def __init__(self):
        super().__init__()

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
            # [IES 2.1 SDK Isolation] 使用 SDK 导出的 PluginError
            raise ibci.PluginError(f"Network GET failed: {str(e)}")

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
            # [IES 2.1 SDK Isolation] 使用 SDK 导出的 PluginError
            raise ibci.PluginError(f"Network POST failed: {str(e)}")

def create_implementation():
    return NetLib()
