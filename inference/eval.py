from pathlib import Path
import threading

from inference.TextClassifier import TextClassifierError
from inference.TextClassifier import load_text_classifier
from inference.TextClassifier import predict_label_id
from inference.TextUtils import normalize_text


MODEL_DIR = Path(__file__).resolve().parent
MODEL1_PATH = str(MODEL_DIR / "model1_sklearn.joblib")
MODEL2_PATH = str(MODEL_DIR / "model2_sklearn.joblib")

_model_cache = {}
_warmup_lock = threading.Lock()
_warmup_thread = None
_warmup_error_message = None
_warmup_error_code = None

WARMUP_STATE_IDLE = "idle"
WARMUP_STATE_LOADING = "loading"
WARMUP_STATE_READY = "ready"
WARMUP_STATE_ERROR = "error"
WARMUP_SAMPLE_TEXT = "ゴブリンを倒して"
_warmup_state = WARMUP_STATE_IDLE

ERROR_CODE_NLP_MODEL_LOAD_FAILED = "NLP_MODEL_LOAD_FAILED"
ERROR_CODE_NLP_WARMUP_PREDICT_FAILED = "NLP_WARMUP_PREDICT_FAILED"
ERROR_CODE_NLP_WARMUP_UNKNOWN_FAILED = "NLP_WARMUP_UNKNOWN_FAILED"


class ModelLoadError(RuntimeError):
    """NLP 推論モデルまたは依存ライブラリを読み込めない状態。"""


# class Category(Enum):
movement = 0
combat = 1
take = 2
use = 3
find = 4
buy = 5
unknown = 6

# class ObjectType(Enum):
map = 0
box = 1


def _get_model(model_path):
    """保存済み軽量分類器を遅延ロードしてキャッシュする。

    引数:
        model_path: `model1_sklearn.joblib` または `model2_sklearn.joblib` のパス。

    戻り値:
        `predict` を持つ学習済み分類器。

    例外:
        ModelLoadError: 依存ライブラリまたはモデルファイルを読み込めない。
    """
    if model_path in _model_cache:
        return _model_cache[model_path]
    try:
        model = load_text_classifier(model_path)
    except TextClassifierError as err:
        raise ModelLoadError(str(err)) from err
    _model_cache[model_path] = model
    return model


def start_async_warmup():
    """NLP 推論モデルを background thread で先読みする。

    Returns:
    - 新しい warm-up thread を開始した場合は `True`。
    - すでに loading / ready の場合は `False`。

    Caller:
    - pygame 初期化後、入力を受ける前に 1 回呼ぶ。
    - loading 中の入力実行は `get_warmup_state()` を見て上位で止める。
    """
    global _warmup_thread
    global _warmup_state
    global _warmup_error_message
    global _warmup_error_code

    with _warmup_lock:
        if _warmup_state in (WARMUP_STATE_LOADING, WARMUP_STATE_READY):
            return False
        _warmup_state = WARMUP_STATE_LOADING
        _warmup_error_message = None
        _warmup_error_code = None

    warmup_thread = threading.Thread(target=_warmup_models, daemon=True)
    _warmup_thread = warmup_thread
    warmup_thread.start()
    return True


def get_warmup_state():
    """現在の NLP warm-up 状態を返す。

    Returns:
    - `idle` / `loading` / `ready` / `error`。
    """
    with _warmup_lock:
        return _warmup_state


def get_warmup_error_message():
    """NLP warm-up 失敗時のエラーメッセージを返す。

    Returns:
    - エラー文字列。
    - エラーがない場合は `None`。
    """
    with _warmup_lock:
        return _warmup_error_message


def get_warmup_error_code():
    """NLP warm-up 失敗時の安定したエラーコードを返す。

    Returns:
    - `NLP_MODEL_LOAD_FAILED` などのエラーコード。
    - エラーがない場合は `None`。

    Caller:
    - ログや UI にはこの値を含める。例外文言ではなく、このコードで失敗境界を分類する。
    """
    with _warmup_lock:
        return _warmup_error_code


def _set_warmup_error(error_code, error_message):
    """warm-up 失敗状態を 1 つの lock 境界で保存する。

    Params:
    - error_code: ログ検索用の安定したエラーコード。
    - error_message: 実行時例外から得た詳細。呼び出し側はデバッグ用として扱う。

    Caller:
    - background thread から呼ぶ。state / code / message を別々に更新しない。
    """
    global _warmup_state
    global _warmup_error_message
    global _warmup_error_code

    with _warmup_lock:
        _warmup_state = WARMUP_STATE_ERROR
        _warmup_error_code = error_code
        _warmup_error_message = error_message


def _warmup_models():
    """カテゴリ/タイプモデルを読み込み、Ruri 初回推論まで先に実行する。

    Caller:
    - `start_async_warmup()` が作る background thread からだけ呼ぶ。
    - 失敗時は例外を thread 外へ漏らさず、warm-up error state に変換する。
    """
    global _warmup_state
    global _warmup_error_message
    global _warmup_error_code

    try:
        category_model = _get_model(MODEL1_PATH)
        type_model = _get_model(MODEL2_PATH)
        predict_label_id(category_model, WARMUP_SAMPLE_TEXT)
        predict_label_id(type_model, WARMUP_SAMPLE_TEXT)
    except ModelLoadError as err:
        _set_warmup_error(ERROR_CODE_NLP_MODEL_LOAD_FAILED, str(err))
        return
    except TextClassifierError as err:
        _set_warmup_error(ERROR_CODE_NLP_WARMUP_PREDICT_FAILED, str(err))
        return
    except Exception as err:
        _set_warmup_error(ERROR_CODE_NLP_WARMUP_UNKNOWN_FAILED, f"NLP warm-up 推論に失敗しました: {err}")
        return

    with _warmup_lock:
        _warmup_state = WARMUP_STATE_READY
        _warmup_error_message = None
        _warmup_error_code = None


def _predict_label_from_model_path(model_path, text):
    """保存済みモデルを使い、推論境界の失敗を `ModelLoadError` に揃える。

    Params:
    - model_path: `model1_sklearn.joblib` または `model2_sklearn.joblib` のパス。
    - text: ゲーム UI または ASR から渡される未正規化文字列。

    Returns:
    - 整数ラベル ID。

    Errors:
    - ModelLoadError: モデル読み込み、embedding 生成、分類器推論のいずれかが失敗した。

    Caller:
    - ゲーム側は `ModelLoadError` を安全終了境界として扱う。
    """
    model = _get_model(model_path)
    try:
        return predict_label_id(model, text)
    except TextClassifierError as err:
        raise ModelLoadError(str(err)) from err
    except Exception as err:
        raise ModelLoadError(f"モデル推論に失敗しました: {model_path}: {err}") from err


def predict_category(text: str) -> int:
    """入力テキストを行動カテゴリ ID に分類する。

    引数:
        text: ゲーム UI または ASR から渡される未正規化文字列。

    戻り値:
        `movement` / `combat` などの整数ラベル ID。

    例外:
        ModelLoadError: `model1_sklearn.joblib` の読み込み、embedding 生成、分類器推論に失敗した。
    """
    return _predict_label_from_model_path(MODEL1_PATH, text)


def predict_type(text: str) -> int:
    """入力テキストを対象タイプ ID に分類する。

    引数:
        text: ゲーム UI または ASR から渡される未正規化文字列。

    戻り値:
        `map` または `box` の整数ラベル ID。

    例外:
        ModelLoadError: `model2_sklearn.joblib` の読み込み、embedding 生成、分類器推論に失敗した。
    """
    return _predict_label_from_model_path(MODEL2_PATH, text)


def eval(text_list, label_list, model):
    """分類器の予測結果と正解ラベルから accuracy を表示する。

    引数:
        text_list: 未正規化テキスト配列。
        label_list: `text_list` と同じ順序の整数ラベル配列。
        model: `predict` を持つ学習済み分類器。

    戻り値:
        `model.predict` が返した予測ラベル配列。
    """
    normalized_texts = [normalize_text(text) for text in text_list]
    labels_predicted = model.predict(normalized_texts)
    num_correct = sum(int(predicted) == int(label) for predicted, label in zip(labels_predicted, label_list))
    accuracy = num_correct / len(label_list)

    print("predicted labels:")
    print(labels_predicted)
    print("accuracy:")
    print(accuracy)
    return labels_predicted


def main():
    """保存済みモデルの簡易評価を標準出力へ表示する。

    Caller:
    - モジュールを直接実行した時の手動確認用。ゲーム実行経路では使わない。
    """
    text_list = ["ドミノを倒します。", "プリンがあります。", "大阪に行くます。", "スライムがいます。", "HPポーションを買う。", "ポーションを使用する。"]
    label_list1 = [
        unknown,
        unknown,
        movement,
        unknown,
        buy,
        use,
    ]

    label_list2 = [
        map,
        map,
        map,
        map,
        map,
        box,
    ]
    category_model = _get_model(MODEL1_PATH)
    type_model = _get_model(MODEL2_PATH)
    eval(text_list, label_list1, category_model)
    print("-----------------------------")
    eval(text_list, label_list2, type_model)


if __name__ == "__main__":
    main()
