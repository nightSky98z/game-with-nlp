from __future__ import annotations

import os
import platform
from collections.abc import MutableMapping


LINUX_DEFAULT_IME_MODULE = "fcitx"
PROJECT_SET_IME_MODULES = {"fcitx", "ibus"}


def configure_text_input_environment(
    *,
    platform_name: str | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    """pygame のテキスト入力に必要な OS 別環境変数を設定する。

    Params:
    - platform_name: `platform.system()` と同じ OS 名。`None` の場合は現在の OS を読む。
    - environ: 更新対象の環境変数 map。`None` の場合は `os.environ` を更新する。

    Caller:
    - pygame 初期化前に 1 回呼ぶ。
    - Linux では IME backend を明示する。macOS / Windows では Linux 用 backend を残さない。
    """
    target_platform_name = platform.system() if platform_name is None else platform_name
    target_environ = os.environ if environ is None else environ

    if target_platform_name == "Linux":
        target_environ.setdefault("SDL_IM_MODULE", LINUX_DEFAULT_IME_MODULE)
        return

    if target_environ.get("SDL_IM_MODULE") in PROJECT_SET_IME_MODULES:
        del target_environ["SDL_IM_MODULE"]
