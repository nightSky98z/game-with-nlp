import glob
import os

from TextUtils import normalize_text


class TextClassifierError(RuntimeError):
    """軽量テキスト分類器の依存、学習データ、モデルファイル境界の失敗。"""


def load_labeled_texts(data_dir: str, label_names: list[str]) -> tuple[list[str], list[int]]:
    """ラベル名ごとのテキストファイルから学習データを読み込む。

    引数:
        data_dir: `movement.txt` のようなラベル別ファイルを置くディレクトリ。
        label_names: ラベル ID と同じ順序のラベル名。インデックスが保存モデルの出力 ID になる。

    戻り値:
        正規化済みテキスト配列と、同じ長さの整数ラベル配列。

    例外:
        TextClassifierError: 読み込める非空行が 1 件もない。

    呼び出し側:
        戻り値の順序はファイル名と行順に依存する。再現性が必要な処理は呼び出し側で分割 seed を固定する。
    """
    texts = []
    labels = []
    for label_id, label_name in enumerate(label_names):
        pattern = os.path.join(data_dir, f"{label_name}*")
        for path in sorted(glob.glob(pattern)):
            with open(path, "r", encoding="utf-8") as input_file:
                for line in input_file:
                    text = normalize_text(line.strip())
                    if text == "":
                        continue
                    texts.append(text)
                    labels.append(label_id)

    if len(texts) == 0:
        raise TextClassifierError(f"学習データが空です: {data_dir}")
    return texts, labels


def build_text_classifier():
    """短い日本語コマンド向けの文字 n-gram 分類器を構築する。

    戻り値:
        `fit` / `predict` を持つ scikit-learn Pipeline。

    例外:
        TextClassifierError: scikit-learn を import できない。

    呼び出し側:
        この関数はモデルを学習しない。学習コストは戻り値の `fit` を呼ぶ側が明示的に負担する。
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import Pipeline
        from sklearn.svm import LinearSVC
    except ImportError as err:
        raise TextClassifierError("scikit-learn が利用できません") from err

    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char",
                    ngram_range=(1, 4),
                    lowercase=False,
                ),
            ),
            ("classifier", LinearSVC(class_weight="balanced")),
        ]
    )


def train_text_classifier(texts: list[str], labels: list[int]):
    """正規化済みテキストと整数ラベルから分類器を学習する。

    引数:
        texts: `normalize_text` 済みの入力文字列配列。
        labels: `texts` と同じ長さの整数ラベル配列。

    戻り値:
        学習済み scikit-learn Pipeline。

    例外:
        TextClassifierError: 入力件数が不一致、または 2 クラス未満。
    """
    if len(texts) != len(labels):
        raise TextClassifierError("texts と labels の件数が一致しません")
    if len(set(labels)) < 2:
        raise TextClassifierError("分類器には 2 種類以上のラベルが必要です")

    classifier = build_text_classifier()
    classifier.fit(texts, labels)
    return classifier


def save_text_classifier(classifier, model_path: str) -> None:
    """学習済み分類器を joblib 形式で保存する。

    引数:
        classifier: `predict` を持つ学習済み scikit-learn Pipeline。
        model_path: 保存先ファイルパス。親ディレクトリがある場合はこの関数が作成する。

    例外:
        TextClassifierError: joblib を import できない、または保存に失敗した。
    """
    try:
        import joblib
    except ImportError as err:
        raise TextClassifierError("joblib が利用できません") from err

    model_dir = os.path.dirname(model_path)
    if model_dir != "":
        os.makedirs(model_dir, exist_ok=True)
    try:
        joblib.dump(classifier, model_path)
    except OSError as err:
        raise TextClassifierError(f"モデルを保存できません: {model_path}") from err


def load_text_classifier(model_path: str):
    """保存済み joblib モデルを読み込む。

    引数:
        model_path: `save_text_classifier` が出力したモデルファイル。

    戻り値:
        `predict` を持つ学習済み分類器。

    例外:
        TextClassifierError: joblib を import できない、モデルファイルが存在しない、または読み込めない。
    """
    try:
        import joblib
    except ImportError as err:
        raise TextClassifierError("joblib が利用できません") from err

    if not os.path.exists(model_path):
        raise TextClassifierError(f"モデルファイルが存在しません: {model_path}")
    try:
        return joblib.load(model_path)
    except Exception as err:
        raise TextClassifierError(f"モデルを読み込めません: {model_path}") from err


def predict_label_id(classifier, text: str) -> int:
    """学習済み分類器で 1 件の入力テキストを分類する。

    引数:
        classifier: `predict` を持つ学習済み分類器。
        text: 未正規化の入力文字列。ASR 出力もこの境界へ渡す。

    戻り値:
        整数ラベル ID。
    """
    normalized_text = normalize_text(text)
    predicted_labels = classifier.predict([normalized_text])
    return int(predicted_labels[0])
