from __future__ import annotations

import platform

import pygame


JAPANESE_FONT_CANDIDATES_BY_OS = {
    "Windows": (
        "Yu Gothic",
        "Meiryo",
        "MS Gothic",
        "Noto Sans CJK JP",
        "Noto Sans JP",
    ),
    "Darwin": (
        "Hiragino Sans",
        "Hiragino Kaku Gothic ProN",
        "Hiragino Maru Gothic ProN",
        "AppleGothic",
        "Noto Sans CJK JP",
        "Noto Sans JP",
    ),
    "Linux": (
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "IPAexGothic",
        "IPAGothic",
        "Takao Gothic",
        "VL Gothic",
        "DejaVu Sans",
    ),
}

DEFAULT_JAPANESE_FONT_CANDIDATES = (
    "Noto Sans CJK JP",
    "Noto Sans JP",
    "Yu Gothic",
    "Meiryo",
    "Hiragino Sans",
    "IPAexGothic",
)


def get_japanese_font_candidates(platform_name: str | None = None) -> tuple[str, ...]:
    """OS 名に対応する日本語 UI フォント候補を返す。

    Params:
    - platform_name: `platform.system()` と同じ OS 名。`None` の場合は現在の OS を読む。

    Returns:
    - pygame に渡すフォント名候補。先頭ほどその OS で優先する。

    Caller:
    - 戻り値は候補名だけで、実際に存在する保証はない。存在確認は `create_ui_font()` が行う。
    """
    current_platform_name = platform.system() if platform_name is None else platform_name
    return JAPANESE_FONT_CANDIDATES_BY_OS.get(current_platform_name, DEFAULT_JAPANESE_FONT_CANDIDATES)


def create_ui_font(size: int, *, bold: bool = False, platform_name: str | None = None):
    """日本語 UI 用の pygame フォントを作る。

    Params:
    - size: pygame Font に渡すピクセルサイズ。
    - bold: 太字候補を探すかどうか。
    - platform_name: テスト用の OS 名。通常の呼び出し側は指定しない。

    Returns:
    - `render()` を持つ pygame Font。

    Caller:
    - pygame の font subsystem 初期化後に呼ぶ。
    - ここで候補検索の IO が発生するため、毎フレームではなく初期化時に保持して使う。
    """
    font_candidates = get_japanese_font_candidates(platform_name)
    match_font = getattr(pygame.font, "match_font", None)
    if match_font is not None:
        matched_path = match_font(font_candidates, bold=bold, italic=False)
        if matched_path is not None:
            return pygame.font.Font(matched_path, size)

    return pygame.font.SysFont(font_candidates, size, bold=bold)
