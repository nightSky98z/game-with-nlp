import re
import unicodedata


def normalize_ascii_width(text: str) -> str:
    """全角の ASCII 英数字だけを半角へ変換する。

    Params:
    - text: プレイヤー入力または表示前の文字列。呼び出し側は `str` として渡す。

    Returns:
    - 全角 `０-９`、`Ａ-Ｚ`、`ａ-ｚ` を半角化した新しい文字列。

    Caller:
    - 日本語文字、空白、記号はこの関数では変換しない。区切り文字や句読点の扱いは上位処理で決める。
    """
    converted_chars = []
    for char in text:
        codepoint = ord(char)
        if ord("０") <= codepoint <= ord("９"):
            converted_chars.append(chr(ord("0") + codepoint - ord("０")))
        elif ord("Ａ") <= codepoint <= ord("Ｚ"):
            converted_chars.append(chr(ord("A") + codepoint - ord("Ａ")))
        elif ord("ａ") <= codepoint <= ord("ｚ"):
            converted_chars.append(chr(ord("a") + codepoint - ord("ａ")))
        else:
            converted_chars.append(char)
    return "".join(converted_chars)


def normalize_text(text: str) -> str:
    """NLP 入力文字列を学習時と推論時で同じ形へ正規化する。

    引数:
        text: 正規化する入力文字列。呼び出し側は `str` として渡す。

    戻り値:
        NFKC 正規化、小文字化、空白除去、句読点除去を適用した文字列。

    呼び出し側:
        戻り値は新しい文字列であり、元の入力文字列は変更しない。
    """
    normalized_text = unicodedata.normalize("NFKC", text)
    normalized_text = normalized_text.lower()
    normalized_text = re.sub(" ", "", normalized_text)
    normalized_text = re.sub("　", "", normalized_text)
    normalized_text = re.sub(r"[、，。,.]+", "", normalized_text)
    return normalized_text
