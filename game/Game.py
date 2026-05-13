import pygame
from typing import List
import re

from game import Color
from game.Character import Monster, Player
from game.Item import HP_Potion, Item, MP_Potion
from game.Shop import Shop
from game.GameUtils import BOX_POSITION, ITEM_SHOW_COUNT_OFFSET, distance_square
from game.TextInput import TextInput
from game.Building import Building
from inference import eval
from game.GameConfig import GameConfig
from game.Character import Goblin
from game.Character import Slime
from inference.TextUtils import normalize_text
from game.TextInputEnvironment import configure_text_input_environment
from game.UIFont import create_ui_font
from game.VoiceInput import VOICE_EVENT_RECOGNIZED_TEXT, VoiceInput

class Game:
    """ゲームのメインクラス"""

    known_monster_names = ("ゴブリン", "スライム")
    minimum_monster_name_similarity = 0.4
    potion_choice_specs = {
        HP_Potion: {
            "name": "HPポーション",
            "aliases": ("hp", "hpポーション", "hp薬"),
        },
        MP_Potion: {
            "name": "MPポーション",
            "aliases": ("mp", "mpポーション", "mp薬"),
        },
    }
    generic_potion_aliases = ("ポーション", "薬")
    generic_combat_target_names = ("敵", "モンスター")
    # 選択待ち中だけ、短い入力の選択子と数量を記号でも分けられるようにする。
    pending_choice_separator_pattern = r"[\s,;/、，；／]+"

    def __init__(self) -> None:
        """ゲームの初期化"""
        configure_text_input_environment()
        pygame.init()

        self.setup_display()
        self.setup_game_components()
        self.setup_sprite_group()
        self.setup_map()
        self.setup_characters()

# ゲームロジック
    def setup_display(self) -> None:
        """ディスプレイ関連の設定"""
        pygame.display.set_caption(GameConfig.TITLE)
        self.screen = pygame.display.set_mode(GameConfig.SCREEN_DIMENSIONS)
        self.font = create_ui_font(80)
        self.text_font = create_ui_font(25)
        self.nlp_result_font = create_ui_font(25)
        self.voice_status_font = create_ui_font(22)
        self.eval_result = self.nlp_result_font.render("", True, Color.WHITE)
        self.action_result = self.nlp_result_font.render("", True, Color.WHITE)
        self.voice_status_result = self.voice_status_font.render("Vキーで音声入力", True, Color.WHITE)

    def setup_game_components(self) -> None:
        """ゲームコンポーネントの設定"""
        self.clock = pygame.time.Clock()
        self.tmr = 0
        self.running = True

        # テキストボックス
        self.text_input_box = TextInput(100, 550, 200, 50)
        self.nlp_text = ""
        self.start_eval = False
        self.pending_choice: dict | None = None
        self.voice_input = VoiceInput()

    def setup_characters(self) -> None:
        """キャラクターの初期設定"""
        self.player = Player(32, 32, self)
        hp_potion = HP_Potion(count=5)
        self.player.buy(item=hp_potion, shop=self.shop)
        for item in self.player.item_box:
            if isinstance(item, Item):
                self.all_sprites.add(item.sprite)
                #print(len(self.all_sprites))

        self.monsters: List[Monster] = []
        self.init_monsters()
        print('現在マップにいるモンスター:')
        for monster in self.monsters:
            print(f"[{monster.name}]")

    def setup_map(self):
        """マップ上にあるオブジェクトを初期化"""
        self.buildings: List[Building] = []
        self.shop = Shop(name="商店", x=200, y=200, game=self, item_type_list=[HP_Potion, MP_Potion])
        if isinstance(self.shop, Building):
            self.buildings.append(self.shop)
        print('現在マップにある建造物:')
        for building in self.buildings:
            print(f"[{building.name}]")
        print("商店にHPポーションがありますか? :", self.shop.has_item(HP_Potion))

    def setup_sprite_group(self) -> None:
        """spriteグループの初期設定"""
        self.all_sprites = pygame.sprite.Group()

    def update(self) -> None:
        """メインゲームループ"""
        self.handle_events()
        if not self.running:
            return
        self.consume_voice_input_events()
        self.render()
        self.maintain_frame_rate()

    def handle_events(self) -> None:
        """イベント処理"""
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_u and not self.is_text_input_active():
                    self.player.use(index=0)

            self.handle_voice_input_event(event)
            self.text_input_box.handle_event(event, self)
            if self.nlp_text != "":
                self.eval_text(self.nlp_text)

    def update_game_state(self) -> None:
        """ゲーム状態の更新"""
        self.tmr += 1
        for monster in self.monsters:
            if not monster.alive:
                self.monsters.remove(monster)
                continue
            monster.update()
        for building in self.buildings:
            building.update()
        self.player.update()
        self.all_sprites.update()
        self.all_sprites.draw(self.screen)

        target = self.player.target
        if isinstance(target, Monster) and self.player.action_type == "combat":
            self.player.move_to(target)
            self.player.attack(target)
        elif isinstance(target, (Monster, Building)) and self.player.action_type == "movement":
            self.player.move_to(target)

    def render(self) -> None:
        """画面描画"""
        self.screen.fill(Color.BLACK)
        # アイテムボックスとゲーム画面を分ける線
        pygame.draw.rect(self.screen, Color.WHITE, (0, 540, 800, 1))
        self.render_box()
        self.update_game_state()
        self.text_input_box.draw(self.screen)
        self.render_voice_input_status()

        if self.start_eval:
            self.screen.blit(self.eval_result, (300, 40))
            self.screen.blit(self.action_result, (300, 70))
        pygame.display.update()

    def maintain_frame_rate(self) -> None:
        """フレームレートの維持"""
        self.clock.tick(60)

    def shutdown(self) -> None:
        """ゲームの終了処理"""
        self.running = False
        if getattr(self, "_shutdown_done", False):
            return
        self._shutdown_done = True

        voice_input = getattr(self, "voice_input", None)
        if voice_input is not None:
            if hasattr(voice_input, "shutdown"):
                voice_input.shutdown(timeout_seconds=1.0)
            else:
                voice_input.wait_for_pending_transcription(timeout_seconds=1.0)
        pygame.quit()

    def init_monsters(self) -> None:
        """モンスターの初期配置"""
        self.add_monster(Goblin(500, 500, self))
        self.add_monster(Goblin(300, 400, self))
        self.add_monster(Slime(400, 300, self))

    def add_monster(self, monster: Monster) -> None:
        """モンスターの追加"""
        self.monsters.append(monster)

    def render_box(self):
        for idx, item in enumerate(self.player.item_box):
            if isinstance(item, Item):
                count = item.check_count()
                sprite = item.sprite
                text = self.text_font.render(str(count), True, Color.WHITE)
                self.screen.blit(text, (BOX_POSITION[idx][0] + ITEM_SHOW_COUNT_OFFSET,
                                        BOX_POSITION[idx][1] + ITEM_SHOW_COUNT_OFFSET))

    def handle_voice_input_event(self, event):
        """音声入力用の push-to-talk キーイベントを処理する。

        Params:
        - event: pygame event。`KEYDOWN V` で録音開始、`KEYUP V` で録音終了と認識開始を行う。

        Returns:
        - 音声入力イベントとして処理した場合は `True`。それ以外は `False`。

        Caller:
        - pygame main thread から呼ぶ。worker thread はこの関数を呼ばない。
        """
        if event.type == pygame.KEYDOWN and event.key == pygame.K_v:
            self.voice_input.start_recording()
            return True
        if event.type == pygame.KEYUP and event.key == pygame.K_v:
            self.voice_input.stop_recording_and_transcribe()
            return True
        return False

    def is_text_input_active(self):
        text_input_box = getattr(self, "text_input_box", None)
        if text_input_box is None:
            return False
        return bool(getattr(text_input_box, "active", False))

    def consume_voice_input_events(self):
        """音声認識 worker の結果を main thread 側で消費する。

        Caller:
        - 毎フレーム呼ぶ。認識済みテキストだけを `eval_text()` に渡し、エラーイベントは音声 UI に任せる。
        """
        while True:
            event = self.voice_input.poll_event()
            if event is None:
                return
            if event.kind == VOICE_EVENT_RECOGNIZED_TEXT and event.text is not None:
                self.eval_text(event.text)

    def render_voice_input_status(self):
        """音声入力状態を入力欄付近に描画する。

        Caller:
        - `VoiceInput` の状態だけを読む。ゲーム状態の変更は行わない。
        """
        status_text = self.voice_input.get_status_text()
        self.voice_status_result = self.voice_status_font.render(status_text, True, Color.WHITE)
        self.screen.blit(self.voice_status_result, (300, 510))


# nlp部分
    def eval_text(self, text):
        """入力されたテキストをモデルで評価"""
        self.start_eval = True
        if getattr(self, "pending_choice", None) is not None:
            return self.resolve_pending_choice(text)

        self.eval_init()
        if text == None or text == "":
            return
        text = self.text_preprocess(text)
        try:
            label_category = eval.predict_category(text)
            label_type = eval.predict_type(text)
        except eval.ModelLoadError as err:
            txt = f"NLPモデルを読み込めません: {err}"
            print(txt)
            self.eval_result = self.nlp_result_font.render("NLPモデル読み込み失敗", True, Color.WHITE)
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return False

        category_message = ""
        type_message = ""
        categories = ["移動", "戦闘", "採取", "使用", "捜索", "購入", "未知"]
        types = ["マップ", "ボックス"]
        label_category = int(label_category)
        label_type = int(label_type)
        category_message = categories[label_category]
        type_message = types[label_type]
        print("category:", category_message, "type:", type_message)
        output_message = "category:" + category_message + " type:" + type_message
        self.eval_result = self.nlp_result_font.render(output_message, True, Color.WHITE)

        if label_category == eval.movement and label_type == eval.map:
            txt = ""
            for i, monster in enumerate(self.monsters):
                if monster.name in text:
                    self.player.target = self.monsters[i]
                    self.player.action_type = "movement"
                    txt = f"{monster.name}:移動"
                    print(txt)
                    self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
                    return
            for i, building in enumerate(self.buildings):
                if building.name in text:
                    self.player.target = self.buildings[i]
                    self.player.action_type = "movement"
                    txt = f"{building.name}:移動"
                    print(txt)
                    self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
                    return
            print('オブジェクトがマップ上に存在しません！')
            txt = 'オブジェクトがマップ上に存在しません！'
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return

        elif label_category == eval.combat and label_type == eval.map:
            target_monster = self.find_alive_monster_named_in_text(text)
            if target_monster is not None:
                self.player.target = target_monster
                self.player.action_type = "combat"
                return True

            explicit_target_text = self.extract_explicit_combat_target(text)
            if explicit_target_text is not None:
                similar_monster, similarity = self.find_most_similar_alive_monster(explicit_target_text)
                if similar_monster is not None:
                    self.player.target = similar_monster
                    self.player.action_type = "combat"
                    print(f"音声ターゲット補正: {explicit_target_text}->{similar_monster.name} ({similarity:.2f})")
                    txt = f"{similar_monster.name}:戦闘"
                    self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
                    return True

                mentioned_monster_name = self.find_mentioned_known_monster_name(text)
                missing_target_name = mentioned_monster_name if mentioned_monster_name is not None else explicit_target_text
                txt = f"{missing_target_name}がマップにいませんでした。"
                print(txt)
                self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
                return False

            nearest_monster = self.find_nearest_monster()
            if nearest_monster is not None:
                self.player.target = nearest_monster
                self.player.action_type = "combat"
                txt = f"{nearest_monster.name}:戦闘"
                print(txt)
                self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
                return True
            print('モンスターがマップにいませんでした。')
            txt = 'モンスターがマップにいませんでした。'
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return True

        elif label_category == eval.buy and label_type == eval.box:
            name_list = ['mp', 'mpポーション', 'mp薬']
            item = MP_Potion
            if self.buy_item_with_eval(text, item, name_list):
                return True

            name_list = ['hp', 'hpポーション', 'hp薬']
            item = HP_Potion
            if self.buy_item_with_eval(text, item, name_list):
                return True

            if self.has_generic_potion_alias(text):
                choices = self.get_shop_potion_choices()
                return self.start_pending_choice("buy", choices)

            print('このオブジェクトは購入できません。')
            txt = 'このオブジェクトは購入できません。'
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return False

        elif label_category == eval.take and label_type == eval.map:
            name_list = ['うさぎ', 'ウサギ', '野菜', 'おおかみ', 'オオカミ', '狼']
            for name in name_list:
                if name in text:
                    txt = f"{name}を採取した"
                    print(txt)
                    self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
                    return True
            txt = "採取できませんでした"
            print(txt)
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return False

        elif label_category == eval.use and label_type == eval.box:
            name_list = ['mp', 'mpポーション', 'mp薬']
            item = MP_Potion
            if self.use_position_with_eval(text, item, name_list):
                return True

            if 'mp' in text:
                txt = 'MPポーションがありません'
                print(txt)
                self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
                return False

            name_list = ['hp', 'hpポーション', 'hp薬']
            item = HP_Potion
            if self.use_position_with_eval(text, item, name_list):
                return True

            if 'hp' in text:
                txt = 'HPポーションがありません'
                print(txt)
                self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
                return False

            if self.has_generic_potion_alias(text):
                choices = self.get_player_potion_choices()
                return self.start_pending_choice("use", choices)

            txt = '使用できません。'
            print(txt)
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return False

        elif label_category == eval.find:
            in_box, on_map = False, False
            txt = ""
            # map上で探してみる
            for i, monster in enumerate(self.monsters):
                name = self.text_preprocess(monster.name)
                if name in text:
                    txt = f"{monster.name}はマップ上にいます。"
                    print(txt)
                    on_map = True
                    break

            for i, building in enumerate(self.buildings):
                name = self.text_preprocess(building.name)
                if name in text:
                    txt = f"{building.name}はマップ上にあります。"
                    print(txt)
                    on_map = True
                    break

            # box内で探してみる
            for idx, item in enumerate(self.player.item_box):
                if isinstance(item, Item):
                    name = self.text_preprocess(item.name)
                    if name in text:
                        txt = f"{item.name}はボックス内にあります。"
                        print(txt)
                        in_box = True
                        break

            # 見つかりません
            if not in_box and not on_map:
                print('オブジェクトが存在しません！')
                txt = 'オブジェクトが存在しません！'
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return

        else:
            txt = "この行動を知りません。"
            print(txt)
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return

    def eval_init(self):
        """eval機能の初期化"""
        self.nlp_text = ""
        self.player.target = None
        # 戦闘か移動か
        self.player.action_type = None

    def text_preprocess(self, text):
        return normalize_text(text)

    def find_alive_monster_named_in_text(self, text):
        """入力文に含まれる生存モンスターを返す。

        Params:
        - text: `text_preprocess()` 後の入力文。呼び出し中は変更しない。

        Returns:
        - 名前が入力文に含まれる生存 monster。
        - `None`: 名前一致する生存 monster が現在マップにいない。

        Caller:
        - 明示ターゲットが存在する場合は、最寄り fallback より先にこの結果を使う。
        """
        for monster in self.monsters:
            if not getattr(monster, "alive", True):
                continue
            if monster.name in text:
                return monster
        return None

    def find_mentioned_known_monster_name(self, text):
        """入力文に含まれる既知モンスター名を返す。

        Params:
        - text: `text_preprocess()` 後の入力文。呼び出し中は変更しない。

        Returns:
        - 入力文に含まれる既知モンスター名。
        - `None`: 明示モンスター名がない。

        Caller:
        - `None` の場合だけ、ターゲット省略コマンドとして最寄り fallback を許可する。
        """
        for monster_name in self.known_monster_names:
            if monster_name in text:
                return monster_name
        return None

    def extract_explicit_combat_target(self, text):
        """戦闘文にある明示ターゲット名を返す。

        Params:
        - text: `text_preprocess()` 後の入力文。呼び出し中は変更しない。

        Returns:
        - `を` の前にあるターゲット文字列。
        - `None`: ターゲット省略、または `敵` / `モンスター` のような汎用対象。

        Caller:
        - `None` でない場合は、まず現在マップ上のモンスター名との類似度で対象解決する。
        """
        object_marker_index = text.find("を")
        if object_marker_index <= 0:
            return None

        target_text = text[:object_marker_index]
        for generic_target_name in self.generic_combat_target_names:
            if generic_target_name in target_text:
                return None
        return target_text

    def find_most_similar_alive_monster(self, target_text):
        """明示ターゲット名に最も似ている生存モンスターを返す。

        Params:
        - target_text: 音声認識から得たターゲット名。呼び出し中は変更しない。

        Returns:
        - `(monster, similarity)`。類似度が閾値以上の生存 monster。
        - `(None, best_similarity)`。候補なし、または最高類似度が低すぎる。

        Caller:
        - `None` の場合は最寄り fallback せず、指定対象はマップにいないものとして扱う。
        """
        normalized_target_text = self.text_preprocess(target_text)
        best_monster = None
        best_similarity = 0.0
        for monster in self.monsters:
            if not getattr(monster, "alive", True):
                continue
            monster_name = self.text_preprocess(monster.name)
            similarity = self.calculate_monster_name_similarity(normalized_target_text, monster_name)
            if similarity > best_similarity:
                best_monster = monster
                best_similarity = similarity

        if best_similarity < self.minimum_monster_name_similarity:
            return None, best_similarity
        return best_monster, best_similarity

    def calculate_monster_name_similarity(self, left_name, right_name):
        """モンスター名同士の連続文字一致率を返す。

        Params:
        - left_name: 音声認識から得た名前。
        - right_name: マップ上にいるモンスター名。

        Returns:
        - `0.0` から `1.0` の類似度。空文字列を含む場合は `0.0`。

        Caller:
        - 短い固有名詞用の軽量比較。閾値は `minimum_monster_name_similarity` で管理する。
        """
        if left_name == "" or right_name == "":
            return 0.0

        previous_lengths = [0] * (len(right_name) + 1)
        longest_common_length = 0
        for left_char in left_name:
            current_lengths = [0] * (len(right_name) + 1)
            for right_index, right_char in enumerate(right_name, start=1):
                if left_char == right_char:
                    current_lengths[right_index] = previous_lengths[right_index - 1] + 1
                    longest_common_length = max(longest_common_length, current_lengths[right_index])
            previous_lengths = current_lengths
        return longest_common_length / max(len(left_name), len(right_name))

    def find_nearest_monster(self):
        """プレイヤーから最も近い生存モンスターを返す。

        Returns:
        - 最寄りの monster。
        - `None`: マップ上に生存モンスターがいない。

        Caller:
        - 戦闘コマンドに明示ターゲット名が含まれない場合だけ使う。
        """
        player_position = self.get_object_position(self.player)
        nearest_monster = None
        nearest_distance_square = None
        for monster in self.monsters:
            if not getattr(monster, "alive", True):
                continue
            monster_position = self.get_object_position(monster)
            current_distance_square = distance_square(player_position, monster_position)
            if nearest_distance_square is None or current_distance_square < nearest_distance_square:
                nearest_monster = monster
                nearest_distance_square = current_distance_square
        return nearest_monster

    def get_object_position(self, obj):
        position = getattr(obj, "position", None)
        if position is not None:
            return position
        return (getattr(obj, "x", 0), getattr(obj, "y", 0))

    def has_generic_potion_alias(self, text):
        normalized_text = self.text_preprocess(text)
        for alias in self.generic_potion_aliases:
            if alias in normalized_text:
                return True
        return False

    def make_potion_choice(self, item_type, box_index=None, count=None):
        spec = self.potion_choice_specs[item_type]
        choice = {
            "item_type": item_type,
            "name": spec["name"],
            "aliases": spec["aliases"],
        }
        if box_index is not None:
            choice["box_index"] = box_index
        if count is not None:
            choice["count"] = count
        return choice

    def get_shop_potion_choices(self):
        choices = []
        shop = getattr(self, "current_shop", self.shop)
        for item_type in shop.item_type_list:
            if item_type in self.potion_choice_specs:
                choices.append(self.make_potion_choice(item_type))
        return choices

    def get_player_potion_choices(self):
        choices = []
        seen_item_types = set()
        for idx, item in enumerate(self.player.item_box):
            if isinstance(item, Item) and type(item) in self.potion_choice_specs:
                if type(item) in seen_item_types:
                    continue
                choices.append(self.make_potion_choice(type(item), box_index=idx, count=item.count))
                seen_item_types.add(type(item))
        return choices

    def build_choice_prompt(self, action, choices):
        action_text = "買います" if action == "buy" else "使います"
        parts = [f"{idx + 1}: {choice['name']}" for idx, choice in enumerate(choices)]
        return f"どのポーションを{action_text}か？ " + " ".join(parts)

    def start_pending_choice(self, action, choices):
        """曖昧なポーション対象を次の入力で解決するために保持する。

        引数:
            action: `buy` または `use`。次入力で実行する操作を表す。
            choices: 選択肢配列。各要素は item type、表示名、alias、必要なら box index を持つ。

        戻り値:
            選択待ちに入った場合は false。候補がない場合も false。

        呼び出し側:
            次の `eval_text` は通常分類ではなく `resolve_pending_choice` へ渡される。
        """
        self.nlp_text = ""
        if len(choices) == 0:
            txt = "購入できるポーションがありません。" if action == "buy" else "使用できるポーションがありません。"
            print(txt)
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            self.pending_choice = None
            return False

        self.pending_choice = {
            "action": action,
            "choices": choices,
        }
        txt = self.build_choice_prompt(action, choices)
        print(txt)
        self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
        return False

    def resolve_pending_choice(self, text):
        """選択待ち中の入力を番号または名前と数量として解決する。

        引数:
            text: `2 2`、`2,2`、`mp/2`、`HPポーション;1` のような選択入力。

        戻り値:
            有効な選択を実行できた場合は true。不正入力または実行失敗は false。

        呼び出し側:
            不正入力では `pending_choice` を維持するため、次入力で再選択できる。
        """
        self.nlp_text = ""
        self.player.target = None
        self.player.action_type = None
        pending_choice = self.pending_choice
        if pending_choice is None:
            return False
        choice, count = self.parse_pending_choice_input(text, pending_choice["choices"])
        if choice is None or count < 1:
            txt = "選択できません。 " + self.build_choice_prompt(pending_choice["action"], pending_choice["choices"])
            print(txt)
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return False

        self.pending_choice = None
        if pending_choice["action"] == "buy":
            return self.execute_pending_buy(choice, count)
        if pending_choice["action"] == "use":
            return self.execute_pending_use(choice, count)
        return False

    def parse_pending_choice_input(self, text, choices):
        tokens = self.split_pending_choice_tokens(text)
        if len(tokens) == 0:
            return None, 0

        choice_token = tokens[0]
        count = 1
        if len(tokens) >= 2 and tokens[1].isdigit():
            count = int(tokens[1])

        if choice_token.isdigit():
            choice_index = int(choice_token) - 1
            if 0 <= choice_index < len(choices):
                return choices[choice_index], count
            return None, count

        for choice in choices:
            aliases = [self.text_preprocess(alias) for alias in choice["aliases"]]
            if choice_token == self.text_preprocess(choice["name"]) or choice_token in aliases:
                return choice, count
        return None, count

    def split_pending_choice_tokens(self, text):
        """選択待ち入力を選択子と数量のトークンに分割する。

        Params:
        - text: プレイヤーの次入力。空白、`,`、`;`、`/`、日本語/全角の近い記号を区切りとして扱う。

        Returns:
        - 正規化済みトークン配列。空入力または区切りだけの場合は空配列。

        Caller:
        - 先頭トークンを選択子、2番目の数値トークンを数量として扱う。
        """
        return [
            self.text_preprocess(token)
            for token in re.split(self.pending_choice_separator_pattern, text.strip())
            if token != ""
        ]

    def execute_pending_buy(self, choice, count):
        item_instance = choice["item_type"](count=count)
        if self.player.buy(item_instance, self.shop):
            txt = f"{choice['name']}を{count}個購入しました。"
            print(txt)
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return True
        return False

    def execute_pending_use(self, choice, count):
        used_count = 0
        item_type = choice["item_type"]
        for _ in range(count):
            item_index = self.find_item_index(item_type)
            if item_index is None:
                break
            if self.player.use(item_index):
                used_count += 1
        if used_count == 0:
            txt = f"{choice['name']}がありません。"
            print(txt)
            self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
            return False

        txt = f"{choice['name']}を{used_count}個使用しました。"
        print(txt)
        self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
        return True

    def find_item_index(self, item_type):
        for idx, item in enumerate(self.player.item_box):
            if isinstance(item, Item) and type(item) == item_type:
                return idx
        return None

    def use_position_with_eval(self, text, item, name_list):
        for name in name_list:
            if name in text:
                all_use_text_list = ['全部', 'すべて', '全て', 'ぜんぶ']
                # ポーションなら複数使用できる
                count = re.sub(r"\D", "", text)
                if count != "":
                    count = int(count)
                else:
                    count = 1

                for idx, obj in enumerate(self.player.item_box):
                    if type(obj) == item and isinstance(obj, Item):
                        for t in all_use_text_list:
                            if t in text:
                                count = obj.count
                        for _ in range(count):
                            self.player.use(idx)
                        txt = f"{obj.name}使用"
                        self.action_result = self.nlp_result_font.render(txt, True, Color.WHITE)
                        return True
        return False

    def buy_item_with_eval(self, text, item, name_list):
        for name in name_list:
            if name in text:
                count = re.sub(r"\D", "", text)
                if count != "":
                    count = int(count)
                else:
                    count = 1
                item_instance = item(count=count)
                return self.player.buy(item_instance, self.shop)
        return False
