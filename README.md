# NLP コマンド入力ゲーム

pygame 上で、テキスト入力または音声入力から日本語コマンドを受け取り、プレイヤーの移動・戦闘・購入・使用などの行動へ変換する実験プロジェクトです。

現在の分類器は、短い日本語ゲームコマンド向けの `Ruri v3 embedding + LogisticRegression` です。音声入力は `faster-whisper` の `tiny` モデルで文字起こしし、その結果を通常のテキストコマンドと同じ推論境界へ渡します。

## 現在一番大きい問題

音声入力の誤認識が、現時点で最も大きい問題です。

例:

```text
ゴブリンを倒して -> ゴブリンをパウスして
ゴブリンを倒して -> オフリングを倒せ
```

ゲーム側では一部の誤認識に対して、現在マップ上にいるモンスター名との類似度で補正しています。たとえば `オフリング` は `ゴブリン` に近い場合だけ補正します。ただし、最高類似度が低い場合は別モンスターを誤攻撃しないように、その対象は「マップにいない」と判断します。

TODO: 音声誤認識を最優先で改善する。候補は、音声入力後の確認 UI、コマンド候補の選択、ASR モデルサイズ変更、ゲーム用語辞書、または認識結果の N-best / 類似度ログの追加。

## 実行方法

```sh
uv run Main.py
```

起動後:

- テキスト入力欄をクリックしてコマンドを入力する。
- Enter でコマンドを実行する。
- `V` キーを押している間だけ録音し、離すと音声認識を開始する。
- 入力欄がアクティブでない場合、`U` キーで先頭アイテムを使う。
- ウィンドウの閉じるボタン、または Ctrl-C で終了する。

## 主なコマンド例

```text
ゴブリンを倒して
倒して
敵を倒して
スライムへ移動
ポーションを買う
HPポーションを買う
ポーションを使う
MPポーションを使う
```

曖昧なポーション指定では、ゲームが選択肢を出します。

```text
ポーションを買う
2 2
mp,2
HPポーション/1
```

選択待ち中の入力は、番号と名前の両方を受け付けます。区切り文字は空白、`,`, `;`, `/`, `、`, `，`, `；`, `／` に対応しています。全角の英数字は入力境界で半角へ変換します。

## ディレクトリ構成

```text
Main.py                 ゲーム起動エントリポイント
game/                   pygame ゲーム本体
inference/              実行時のテキスト分類・推論モデル
training/               学習スクリプトと学習データ
test_regressions.py     回帰テスト
unrelated/              このゲーム本体と無関係な実験ファイル
```

`docs/`, `unrelated/`, `.DS_Store`, `AGENTS.md` は追跡対象外です。

## 推論モデル

ゲーム実行時は以下のファイルを読み込みます。

```text
inference/model1_sklearn.joblib  行動カテゴリ分類。Ruri v3 embedding 分類器を保存する。
inference/model2_sklearn.joblib  対象タイプ分類。Ruri v3 embedding 分類器を保存する。
```

モデルがない場合は、以下で再生成します。

```sh
uv run python -B -m training.Model1
uv run python -B -m training.Model2
```

学習データ:

```text
training/my_data/       movement, combat, take, use, find, buy, unknown
training/my_data2/      map, box
```

分類ラベル:

```text
category:
0 movement
1 combat
2 take
3 use
4 find
5 buy
6 unknown

type:
0 map
1 box
```

## 音声入力

音声入力は `game/VoiceInput.py` にあります。

## 意味分類

テキスト分類は `inference/TextClassifier.py` にあります。分類時は入力文を正規化した後、Ruri v3 の分類用 prefix を付けて embedding を作ります。

```text
トピック: ゴブリンを倒して
```

その embedding を `LogisticRegression` に渡して、行動カテゴリまたは対象タイプを選びます。これにより、学習データが少なくても `倒す`、`斬る`、`打倒`、`打死` のような表現を combat に寄せやすくしています。

Ruri v3 は事前学習済みモデルなので、日本語文の意味理解の大部分はモデル側がすでに持っています。このプロジェクトの学習データは、大量の日本語を覚えさせるためではなく、意味領域をゲーム内カテゴリへ対応づけるために使います。

```text
Ruri v3: 日本語文を意味 embedding に変換する
学習データ: この意味領域は combat / use / buy などだと教える
LogisticRegression: embedding 上でカテゴリ境界を引く
```

そのため、学習データは大量でなくてもよいですが、各カテゴリの代表例は必要です。例えば combat には `倒す` だけでなく、`斬る`、`打倒`、`打死`、`攻撃する` のような言い換えを少数入れておくと境界が安定します。

速度面では、初回は Ruri v3 のモデルロードが重く、2 回目以降は embedding 計算と `LogisticRegression` 推論が主なコストになります。`cl-nagoya/ruri-v3-30m` は Ruri v3 系の小さいモデルなので、意味理解と実行速度のバランスを取るための第一候補です。

実測確認済みの例:

```text
ゴブリンを倒して => combat map
ゴブリンを倒す => combat map
ゴブリンを斬る => combat map
ゴブリンを打倒 => combat map
ゴブリンを打死 => combat map
```

現在の設定:

```text
model: faster-whisper tiny
device: cpu
compute_type: int8
language: ja
beam_size: 1
timeout: 120 秒
```

初回実行時は Hugging Face Hub からモデルを取得するため、以下の警告が出ることがあります。

```text
Warning: You are sending unauthenticated requests to the HF Hub.
```

これは未認証アクセスの警告であり、必ずしも実行失敗ではありません。レート制限や初回取得時間を安定させたい場合は `HF_TOKEN` を設定します。

音声認識が成功した場合、デバッグ用に以下を標準出力へ出します。

```text
音声認識結果: ...
```

ターゲット名を補正した場合は以下も出します。

```text
音声ターゲット補正: オフリング->ゴブリン (0.40)
```

## 戦闘ターゲット解決

戦闘コマンドのターゲット解決は安全側に倒しています。

- `ゴブリンを倒して`: 生存しているゴブリンがいれば攻撃する。
- `ゴブリンを倒して`: ゴブリンがいなければ、スライムなど別の敵へは fallback しない。
- `オフリングを倒せ`: 生存モンスター名との類似度が高ければ補正する。
- `ドラゴンを倒せ`: 類似度が低ければ「ドラゴンがマップにいませんでした。」とする。
- `倒して` / `敵を倒して`: 明示ターゲットなしなので最寄りの生存モンスターを攻撃する。

この境界は、音声誤認識による別対象への誤攻撃を避けるためのものです。

## テキスト入力と日本語表示

pygame の IME 入力と日本語フォントは OS ごとに扱いを分けています。

- macOS: Hiragino 系フォントを優先する。
- Windows: Yu Gothic / Meiryo 系フォントを優先する。
- Linux: Noto / IPA / VL / Takao 系フォントを優先する。

macOS / Windows では Linux 用の `SDL_IM_MODULE=fcitx` を強制しません。Linux では未設定の場合のみ `fcitx` を既定値にします。

## 検証

```sh
python3 -B -m unittest test_regressions.py
uv run python -B -m unittest test_regressions.py
uvx pyright .
```

構文チェック:

```sh
PYTHONPYCACHEPREFIX=/private/tmp/nlp_pycache_check python3 -B -c "import pathlib, py_compile; files=[p for p in pathlib.Path('.').rglob('*.py') if '.venv' not in p.parts and '__pycache__' not in p.parts and '.git' not in p.parts]; [py_compile.compile(str(p), doraise=True) for p in files]; print('syntax ok', len(files))"
```

HINT: sandbox 環境では `uvx pyright .` が `~/.cache/uv` へアクセスできず失敗する場合があります。その場合は sandbox 外の実行許可が必要です。通常のローカル端末ではそのまま実行できます。

## 既知の課題

TODO: 音声誤認識を最優先で改善する。現在は誤認識後の補正で被害を減らしているが、入力そのものの精度はまだ不安定。

TODO: 音声入力の認識結果をそのまま実行する前に、プレイヤーが確認・選択できる UI を検討する。

TODO: モンスター名やアイテム名が増えたら、`known_monster_names` や類似度閾値を手作業で維持しないデータ構造へ移す。

HINT: モンスター名が短い間は最長共通連続文字列ベースの軽量類似度で十分だが、名前数が増えたり似た名前が増えた場合は、読み仮名・別名辞書・編集距離・ASR 候補リストを併用する方が安全。
