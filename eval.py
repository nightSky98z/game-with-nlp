from TextClassifier import TextClassifierError
from TextClassifier import load_text_classifier
from TextClassifier import predict_label_id
from TextUtils import normalize_text


MODEL1_PATH = "./model1_sklearn.joblib"
MODEL2_PATH = "./model2_sklearn.joblib"

_model_cache = {}


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
        model_path: `Model1.py` または `Model2.py` が保存した joblib ファイル。

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


def predict_category(text: str) -> int:
    """入力テキストを行動カテゴリ ID に分類する。

    引数:
        text: ゲーム UI または ASR から渡される未正規化文字列。

    戻り値:
        `movement` / `combat` などの整数ラベル ID。

    例外:
        ModelLoadError: `model1_sklearn.joblib` を読み込めない。
    """
    model = _get_model(MODEL1_PATH)
    return predict_label_id(model, text)


def predict_type(text: str) -> int:
    """入力テキストを対象タイプ ID に分類する。

    引数:
        text: ゲーム UI または ASR から渡される未正規化文字列。

    戻り値:
        `map` または `box` の整数ラベル ID。

    例外:
        ModelLoadError: `model2_sklearn.joblib` を読み込めない。
    """
    model = _get_model(MODEL2_PATH)
    return predict_label_id(model, text)


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
