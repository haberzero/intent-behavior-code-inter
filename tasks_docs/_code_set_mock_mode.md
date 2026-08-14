# set_mock_mode 对称开关（T05 §六.4）

> 2026-08-14。承接 `_HANDOFF_T05_ISSUES.md` §六.4：`set_mock_mode()` 仅单向进入
> mock（`_config["mock"]=True`），无 off API；退出只能 `ai.set_config`/`ai.apply_config`。

## 处置

改为对称开关 `set_mock_mode(enable: bool = True)`：

- `enable=True`（默认）：进入 MOCK 模式（行为不变，单向旧用法兼容）。
- `enable=False`：退出 MOCK 模式并重建真实客户端（`_init_client`）。未配置
  url/key 时 fail-fast（`_init_client` 非 mock 分支已含凭据缺失 fail-fast，
  不静默停留在半配置状态）。

同步更新 `ibci_modules/ibci_ai/_spec.py` vtable（`set_mock_mode` 增 `enable` 参数
+ `default: True` + description）。

## 判别性回归（tests/runtime/test_set_mock_mode_switch.py，3 项）

1. 无参 `set_mock_mode()` 进入 MOCK（旧用法兼容）。
2. `set_mock_mode(False)` 未配置 → fail-fast。
3. mock → 真实（load_project_config）→ mock 往返切换。

## 验证

全量 pytest **2661 passed / 1 skipped** 零回归。
