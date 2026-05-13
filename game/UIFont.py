from __future__ import annotations

import os
import platform
from collections.abc import Callable

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

JAPANESE_FONT_FILE_CANDIDATES_BY_OS = {
    "Windows": (
        "C:/Windows/Fonts/YuGothR.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ),
    "Darwin": (
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W5.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W5.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    ),
    "Linux": (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
        "/usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf",
        "/usr/share/fonts/truetype/vlgothic/VL-Gothic-Regular.ttf",
        "/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf",
    ),
}

DEFAULT_JAPANESE_FONT_FILE_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/YuGothR.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
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


def get_japanese_font_file_candidates(platform_name: str | None = None) -> tuple[str, ...]:
    """OS 標準の日本語フォントファイル候補を返す。

    Params:
    - platform_name: `platform.system()` と同じ OS 名。`None` の場合は現在の OS を読む。

    Returns:
    - pygame Font に直接渡せる可能性があるファイルパス候補。

    Caller:
    - 戻り値は候補パスだけで、存在確認と読み込みは呼び出し側が行う。
    """
    current_platform_name = platform.system() if platform_name is None else platform_name
    return JAPANESE_FONT_FILE_CANDIDATES_BY_OS.get(
        current_platform_name,
        DEFAULT_JAPANESE_FONT_FILE_CANDIDATES,
    )


def resolve_japanese_font_path(
    platform_name: str | None = None,
    path_exists: Callable[[str], bool] = os.path.exists,
    match_font=None,
    *,
    bold: bool = False,
) -> str | None:
    """日本語 UI に使うフォントファイルパスを解決する。

    Params:
    - platform_name: `platform.system()` と同じ OS 名。`None` の場合は現在の OS を読む。
    - path_exists: ファイル存在確認関数。テストでは副作用なしの関数を渡す。
    - match_font: pygame の system font 検索関数。`None` の場合は `pygame.font.match_font` を使う。
    - bold: 太字候補を探すかどうか。

    Returns:
    - 見つかったフォントファイルパス。
    - `None`: OS 固定パスと pygame のフォント検索の両方で見つからない。

    Caller:
    - 戻り値が `None` の場合だけ、pygame の既定 fallback を使う。
    """
    for font_path in get_japanese_font_file_candidates(platform_name):
        if path_exists(font_path):
            return font_path

    font_matcher = getattr(pygame.font, "match_font", None) if match_font is None else match_font
    if font_matcher is None:
        return None

    return font_matcher(get_japanese_font_candidates(platform_name), bold=bold, italic=False)


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
    matched_path = resolve_japanese_font_path(platform_name, bold=bold)
    if matched_path is not None:
        return pygame.font.Font(matched_path, size)

    return pygame.font.SysFont(get_japanese_font_candidates(platform_name), size, bold=bold)
