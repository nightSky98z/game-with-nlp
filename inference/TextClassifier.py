from __future__ import annotations

import glob
import os

from inference.TextUtils import normalize_text


DEFAULT_RURI_MODEL_NAME = "cl-nagoya/ruri-v3-30m"
DEFAULT_RURI_DEVICE = "cpu"
DEFAULT_RURI_BATCH_SIZE = 32
RURI_CLASSIFICATION_PREFIX = "トピック: "


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


class RuriSentenceEmbeddingBackend:
    """Ruri v3 でテキスト配列を embedding へ変換する。

    Params:
    - model_name: Hugging Face Hub またはローカルの SentenceTransformer モデル ID。
    - device: `cpu` / `cuda` など、SentenceTransformer に渡す推論 device。

    Caller:
    - モデル本体は初回 `encode()` で遅延ロードする。
    - この backend は joblib 保存対象にしない。保存モデルは `model_name` だけ保持する。
    """

    def __init__(self, model_name: str = DEFAULT_RURI_MODEL_NAME, device: str = DEFAULT_RURI_DEVICE):
        self.model_name = model_name
        self.device = device
        self.model = None

    def encode(self, texts: list[str], batch_size: int | None = None):
        """テキスト配列を Ruri v3 embedding へ変換する。

        Params:
        - texts: Ruri の prefix 付与済みテキスト配列。呼び出し中は変更しない。
        - batch_size: SentenceTransformer の encode batch size。`None` は既定値を使う。

        Returns:
        - scikit-learn が受け取れる embedding 配列。

        Errors:
        - TextClassifierError: `sentence-transformers` の読み込み、モデルロード、推論に失敗した。
        """
        model = self._get_model()
        try:
            return model.encode(
                texts,
                batch_size=DEFAULT_RURI_BATCH_SIZE if batch_size is None else batch_size,
                convert_to_numpy=True,
            )
        except Exception as err:
            raise TextClassifierError("Ruri v3 embedding の生成に失敗しました") from err

    def _get_model(self):
        if self.model is not None:
            return self.model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as err:
            raise TextClassifierError("sentence-transformers が利用できません") from err
        try:
            self.model = SentenceTransformer(self.model_name, device=self.device)
        except Exception as err:
            raise TextClassifierError(f"Ruri v3 モデルを読み込めません: {self.model_name}") from err
        return self.model


class RuriEmbeddingTextClassifier:
    """Ruri v3 embedding と線形分類器で短いゲームコマンドを分類する。

    Params:
    - label_classifier: embedding を受け取る scikit-learn 互換分類器。`None` なら LogisticRegression を使う。
    - embedding_backend: `encode(texts, batch_size)` を持つ embedding backend。`None` なら Ruri v3 を使う。
    - model_name: Ruri v3 のモデル ID。joblib 保存後の再ロードに使う。
    - device: embedding 推論 device。既定は hidden GPU 使用を避けるため `cpu`。
    - batch_size: embedding 生成 batch size。

    Caller:
    - `fit()` は全量再学習する。追加学習ではない。
    - joblib 保存時は embedding backend を保存しない。推論時に再度遅延ロードする。
    """

    def __init__(
        self,
        label_classifier=None,
        embedding_backend=None,
        model_name: str = DEFAULT_RURI_MODEL_NAME,
        device: str = DEFAULT_RURI_DEVICE,
        batch_size: int = DEFAULT_RURI_BATCH_SIZE,
    ):
        self.label_classifier = label_classifier if label_classifier is not None else build_label_classifier()
        self.embedding_backend = embedding_backend
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size

    def fit(self, texts: list[str], labels: list[int]):
        """正規化済みテキストと整数ラベルで分類器を学習する。

        Params:
        - texts: 学習対象テキスト配列。呼び出し中は変更しない。
        - labels: `texts` と同じ順序の整数ラベル配列。

        Returns:
        - self。

        Caller:
        - 入力件数とクラス数の検査は上位の `train_text_classifier()` が行う。
        """
        embeddings = self.encode_texts(texts)
        self.label_classifier.fit(embeddings, labels)
        return self

    def predict(self, texts: list[str]):
        """テキスト配列を整数ラベルへ分類する。

        Params:
        - texts: 未正規化または正規化済みの入力テキスト配列。

        Returns:
        - label classifier の `predict()` が返すラベル配列。
        """
        embeddings = self.encode_texts(texts)
        return self.label_classifier.predict(embeddings)

    def encode_texts(self, texts: list[str]):
        """Ruri の分類 prefix を付けて embedding を生成する。

        Params:
        - texts: 分類対象テキスト配列。呼び出し中は変更しない。

        Returns:
        - embedding backend が返す embedding 配列。
        """
        prefixed_texts = [RURI_CLASSIFICATION_PREFIX + normalize_text(text) for text in texts]
        return self._get_embedding_backend().encode(prefixed_texts, batch_size=self.batch_size)

    def _get_embedding_backend(self):
        if self.embedding_backend is None:
            self.embedding_backend = RuriSentenceEmbeddingBackend(
                model_name=self.model_name,
                device=self.device,
            )
        return self.embedding_backend

    def __getstate__(self):
        state = self.__dict__.copy()
        state["embedding_backend"] = None
        return state


def build_label_classifier():
    """Ruri embedding 上で intent を分類する線形分類器を構築する。

    Returns:
    - `fit` / `predict` を持つ LogisticRegression。

    Errors:
    - TextClassifierError: scikit-learn を import できない。
    """
    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError as err:
        raise TextClassifierError("scikit-learn が利用できません") from err

    return LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        random_state=0,
    )


def build_text_classifier(
    *,
    embedding_backend=None,
    label_classifier=None,
    model_name: str = DEFAULT_RURI_MODEL_NAME,
    device: str = DEFAULT_RURI_DEVICE,
    batch_size: int = DEFAULT_RURI_BATCH_SIZE,
):
    """短い日本語コマンド向けの Ruri v3 embedding 分類器を構築する。

    Returns:
    - `fit` / `predict` を持つ `RuriEmbeddingTextClassifier`。

    Caller:
    - この関数は学習しない。embedding 生成と学習コストは `fit()` を呼ぶ側が明示的に負担する。
    """
    return RuriEmbeddingTextClassifier(
        embedding_backend=embedding_backend,
        label_classifier=label_classifier,
        model_name=model_name,
        device=device,
        batch_size=batch_size,
    )


def train_text_classifier(
    texts: list[str],
    labels: list[int],
    *,
    embedding_backend=None,
    label_classifier=None,
    model_name: str = DEFAULT_RURI_MODEL_NAME,
    device: str = DEFAULT_RURI_DEVICE,
    batch_size: int = DEFAULT_RURI_BATCH_SIZE,
):
    """正規化済みテキストと整数ラベルから Ruri embedding 分類器を学習する。

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

    classifier = build_text_classifier(
        embedding_backend=embedding_backend,
        label_classifier=label_classifier,
        model_name=model_name,
        device=device,
        batch_size=batch_size,
    )
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
