from TextClassifier import load_labeled_texts
from TextClassifier import save_text_classifier
from TextClassifier import train_text_classifier


TYPE_LABEL_NAMES = [
    "map",
    "box",
]
DATA_DIR = "./my_data2"
MODEL_PATH = "./model2_sklearn.joblib"


def main() -> None:
    """対象タイプ分類器を学習して joblib ファイルへ保存する。

    呼び出し側:
        実行前に `scikit-learn` と `joblib` を利用可能にする。
        出力された `MODEL_PATH` はゲーム実行時の `eval.predict_type` が読み込む。
    """
    texts, labels = load_labeled_texts(DATA_DIR, TYPE_LABEL_NAMES)
    classifier = train_text_classifier(texts, labels)
    save_text_classifier(classifier, MODEL_PATH)
    print(f"saved: {MODEL_PATH}")
    print(f"examples: {len(texts)}")
    print(f"labels: {TYPE_LABEL_NAMES}")


if __name__ == "__main__":
    main()
