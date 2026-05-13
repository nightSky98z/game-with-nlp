import contextlib
import io
import importlib
import os
import sys
import tempfile
import threading
import types
import unittest


class FakeRect:
    def __init__(self, x=0, y=0, w=0, h=0):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    @property
    def center(self):
        return (self.x + self.w // 2, self.y + self.h // 2)

    @center.setter
    def center(self, value):
        self.x = value[0] - self.w // 2
        self.y = value[1] - self.h // 2

    @property
    def centerx(self):
        return self.center[0]

    @property
    def centery(self):
        return self.center[1]

    def collidepoint(self, pos):
        return self.x <= pos[0] <= self.x + self.w and self.y <= pos[1] <= self.y + self.h

    def move_ip(self, dx, dy):
        self.x += dx
        self.y += dy


class FakeSurface:
    def __init__(self, size):
        self.size = tuple(size)
        self.fill_color = None
        self.blit_calls = []
        self.color_key = None
        self.rendered_text = ""

    def fill(self, color):
        self.fill_color = color

    def blit(self, *args):
        self.blit_calls.append(args)

    def set_colorkey(self, color):
        self.color_key = color

    def get_rect(self):
        return FakeRect(0, 0, self.size[0], self.size[1])

    def get_width(self):
        return self.size[0]

    def get_height(self):
        return self.size[1]

    def convert_alpha(self):
        return self


class FakeSpriteBase:
    def __init__(self):
        self.killed = False

    def kill(self):
        self.killed = True


class FakeGroup:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    def update(self):
        pass

    def draw(self, screen):
        pass


class FakeFont:
    def render(self, text, antialias, color):
        surface = FakeSurface((max(1, len(str(text))) * 8, 20))
        surface.rendered_text = str(text)
        return surface


class FakePygame(types.ModuleType):
    def __init__(self):
        super().__init__("pygame")
        self.QUIT = 1
        self.KEYUP = 2
        self.KEYDOWN = 3
        self.MOUSEBUTTONDOWN = 4
        self.TEXTINPUT = 5
        self.TEXTEDITING = 6
        self.K_u = 117
        self.K_v = 118
        self.K_RETURN = 13
        self.K_BACKSPACE = 8
        self.error = Exception
        self.Rect = FakeRect
        self.Surface = FakeSurface
        self.Color = lambda name: name
        self.draw = types.SimpleNamespace(rect=lambda *args, **kwargs: None)
        self.sprite = types.SimpleNamespace(Sprite=FakeSpriteBase, Group=FakeGroup)
        self.font = types.SimpleNamespace(
            SysFont=lambda *args, **kwargs: FakeFont(),
            Font=lambda *args, **kwargs: FakeFont(),
        )
        self.image = types.SimpleNamespace(load=self._load_missing_image)
        self.transform = types.SimpleNamespace(scale=lambda image, size: FakeSurface(size))
        self.key = types.SimpleNamespace(
            start_text_input=lambda: None,
            set_text_input_rect=lambda rect: None,
        )

    def _load_missing_image(self, filename):
        raise FileNotFoundError(filename)


def install_fake_pygame():
    pygame = FakePygame()
    sys.modules["pygame"] = pygame
    sys.modules["pygame.image"] = pygame.image
    return pygame


def clear_modules(*names):
    for name in names:
        sys.modules.pop(name, None)


class GameRegressionTests(unittest.TestCase):
    def setUp(self):
        clear_modules(
            "pygame",
            "pygame.image",
            "SpriteSheet",
            "Sprite",
            "Shop",
            "Building",
            "Character",
            "Item",
            "TextInput",
            "TextClassifier",
            "VoiceInput",
            "Main",
            "TextUtils",
            "eval",
            "Game",
            "joblib",
        )

    def test_sprite_sheet_missing_asset_uses_requested_rectangle_color(self):
        install_fake_pygame()
        from SpriteSheet import SpriteSheet

        sprite_sheet = SpriteSheet("./resources/missing.png", fallback_color=(255, 255, 255))
        image = sprite_sheet.get_image(0, 0, 16, 16)

        self.assertEqual((255, 255, 255), image.fill_color)
        self.assertEqual((16, 16), image.size)

    def test_shop_missing_asset_uses_blue_rectangle(self):
        install_fake_pygame()
        from Color import BLUE
        from Shop import Shop

        with contextlib.redirect_stdout(io.StringIO()):
            shop = Shop(name="商店", x=10, y=10, sprite=None, game=None, item_type_list=[])

        self.assertEqual(BLUE, shop.sprite.fill_color)

    def test_potion_missing_assets_use_hp_red_and_mp_blue_rectangles(self):
        install_fake_pygame()
        from Color import BLUE, RED
        from Item import HP_Potion, MP_Potion

        with contextlib.redirect_stdout(io.StringIO()):
            hp_potion = HP_Potion()
            mp_potion = MP_Potion()

        self.assertEqual(RED, hp_potion.sprite.image.fill_color)
        self.assertEqual(BLUE, mp_potion.sprite.image.fill_color)

    def test_main_constructs_game_once(self):
        fake_game_module = types.ModuleType("Game")

        class FakeGame:
            init_count = 0

            def __init__(self):
                type(self).init_count += 1
                self.running = True

            def update(self):
                self.running = False

            def shutdown(self):
                pass

        fake_game_module.Game = FakeGame
        sys.modules["Game"] = fake_game_module

        import Main

        Main.main()

        self.assertEqual(1, FakeGame.init_count)

    def test_player_take_returns_false_when_box_is_full(self):
        install_fake_pygame()
        from Character import Player
        from Item import HP_Potion, Item, MP_Potion

        class FakeSprite:
            def change_position(self, position):
                self.position = position

        class Stone(Item):
            pass

        class Herb(Item):
            pass

        class StaticSpriteSheet:
            def get_image(self, x, y, width, height):
                return FakeSurface((width, height))

        fake_game = types.SimpleNamespace(
            all_sprites=FakeGroup(),
            nlp_result_font=FakeFont(),
            action_result=None,
        )
        with contextlib.redirect_stdout(io.StringIO()):
            player = Player(0, 0, fake_game, sprite_sheet=StaticSpriteSheet())
            player.item_box = [
                HP_Potion(count=1),
                MP_Potion(count=1),
                Stone(name="石", sprite=FakeSprite(), count=1),
            ]
            result = player.take(Herb(name="薬草", sprite=FakeSprite(), count=1))

        self.assertFalse(result)
        self.assertFalse(any(type(item).__name__ == "Herb" for item in player.item_box))

    def test_text_input_return_submitted_text_without_game_object(self):
        install_fake_pygame()
        from TextInput import TextInput

        text_input = TextInput(0, 0, 200, 40)
        text_input.active = True
        text_input.text = "スライムへ移動"
        event = types.SimpleNamespace(type=3, key=13)

        with contextlib.redirect_stdout(io.StringIO()):
            submitted = text_input.handle_event(event)

        self.assertEqual("スライムへ移動", submitted)
        self.assertEqual("", text_input.text)

    def test_text_input_converts_fullwidth_ascii_on_input_and_submit(self):
        install_fake_pygame()
        from TextInput import TextInput

        text_input = TextInput(0, 0, 200, 40)
        text_input.active = True
        game_object = types.SimpleNamespace(nlp_text="")

        text_event = types.SimpleNamespace(type=5, text="ＡｂＣ１２３ポーション")
        text_input.handle_event(text_event, game_object)

        self.assertEqual("AbC123ポーション", text_input.text)

        return_event = types.SimpleNamespace(type=3, key=13)
        with contextlib.redirect_stdout(io.StringIO()):
            submitted = text_input.handle_event(return_event, game_object)

        self.assertEqual("AbC123ポーション", submitted)
        self.assertEqual("AbC123ポーション", game_object.nlp_text)
        self.assertEqual("", text_input.text)

    def test_normalize_text_applies_nfkc_before_lowercase(self):
        from TextUtils import normalize_text

        self.assertEqual("abchpポーション", normalize_text("ＡＢＣ　HP、ポーション。"))

    def test_voice_input_records_transcribes_and_exposes_status(self):
        from VoiceInput import VOICE_EVENT_RECOGNIZED_TEXT, VOICE_STATE_IDLE, VOICE_STATE_RECORDING
        from VoiceInput import VOICE_STATE_TRANSCRIBING, VoiceInput

        class FakeRecorder:
            def __init__(self):
                self.started = False
                self.stopped = False

            def start(self):
                self.started = True

            def stop_to_wav_file(self):
                self.stopped = True
                return "fake.wav"

        transcription_started = threading.Event()
        continue_transcription = threading.Event()

        class FakeTranscriber:
            def __init__(self):
                self.audio_paths = []

            def transcribe(self, audio_path):
                self.audio_paths.append(audio_path)
                transcription_started.set()
                continue_transcription.wait(timeout=1.0)
                return "ＡＢＣ１２３ポーション"

        recorder = FakeRecorder()
        transcriber = FakeTranscriber()
        voice_input = VoiceInput(recorder=recorder, transcriber=transcriber)

        self.assertEqual(VOICE_STATE_IDLE, voice_input.state)
        self.assertEqual("Vキーで音声入力", voice_input.get_status_text())

        self.assertTrue(voice_input.start_recording())
        self.assertTrue(recorder.started)
        self.assertEqual(VOICE_STATE_RECORDING, voice_input.state)
        self.assertEqual("録音しています", voice_input.get_status_text())

        self.assertTrue(voice_input.stop_recording_and_transcribe())
        self.assertTrue(recorder.stopped)
        self.assertTrue(transcription_started.wait(timeout=1.0))
        self.assertEqual(VOICE_STATE_TRANSCRIBING, voice_input.state)
        self.assertEqual("音声を認識しています", voice_input.get_status_text())

        continue_transcription.set()
        self.assertTrue(voice_input.wait_for_pending_transcription(timeout_seconds=1.0))
        event = voice_input.poll_event()

        self.assertEqual(VOICE_EVENT_RECOGNIZED_TEXT, event.kind)
        self.assertEqual("ABC123ポーション", event.text)
        self.assertEqual(["fake.wav"], transcriber.audio_paths)
        self.assertEqual(VOICE_STATE_IDLE, voice_input.state)
        self.assertEqual("認識: ABC123ポーション", voice_input.get_status_text())

    def test_voice_input_reports_transcription_error_without_text_event(self):
        from VoiceInput import VOICE_EVENT_ERROR, VOICE_STATE_IDLE, VoiceInput

        class FakeRecorder:
            def start(self):
                pass

            def stop_to_wav_file(self):
                return "broken.wav"

        class FailingTranscriber:
            def transcribe(self, audio_path):
                raise RuntimeError("モデルなし")

        voice_input = VoiceInput(recorder=FakeRecorder(), transcriber=FailingTranscriber())

        with contextlib.redirect_stdout(io.StringIO()):
            voice_input.start_recording()
            voice_input.stop_recording_and_transcribe()
            self.assertTrue(voice_input.wait_for_pending_transcription(timeout_seconds=1.0))
        event = voice_input.poll_event()

        self.assertEqual(VOICE_EVENT_ERROR, event.kind)
        self.assertIn("モデルなし", event.message)
        self.assertIsNone(event.text)
        self.assertEqual(VOICE_STATE_IDLE, voice_input.state)
        self.assertIn("音声入力エラー: モデルなし", voice_input.get_status_text())

    def test_eval_reuses_loaded_category_model(self):
        load_count = {"model": 0}

        class FakeClassifier:
            def predict(self, texts):
                self.texts = texts
                return [0]

        fake_joblib = types.ModuleType("joblib")

        def fake_load(path):
            load_count["model"] += 1
            return FakeClassifier()

        fake_joblib.load = fake_load
        sys.modules["joblib"] = fake_joblib

        with tempfile.NamedTemporaryFile(delete=False) as model_file:
            model_path = model_file.name

        try:
            target_eval = importlib.import_module("eval")
            target_eval.MODEL1_PATH = model_path
            target_eval.predict_category("スライムへ移動")
            target_eval.predict_category("ゴブリンへ移動")

            self.assertEqual(1, load_count["model"])
        finally:
            os.unlink(model_path)

    def test_game_eval_text_reports_model_error_without_raising(self):
        install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.movement = 0
        fake_eval.combat = 1
        fake_eval.take = 2
        fake_eval.use = 3
        fake_eval.find = 4
        fake_eval.buy = 5
        fake_eval.unknown = 6
        fake_eval.map = 0
        fake_eval.box = 1
        fake_eval.ModelLoadError = type("ModelLoadError", (RuntimeError,), {})

        def raise_model_error(text):
            raise fake_eval.ModelLoadError("モデルが見つかりません")

        fake_eval.predict_category = raise_model_error
        fake_eval.predict_type = raise_model_error
        sys.modules["eval"] = fake_eval

        from Game import Game

        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = "スライムへ移動"
        game.player = types.SimpleNamespace(target="old", action_type="combat")

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("スライムへ移動")

        self.assertFalse(result)
        self.assertIsNone(game.player.target)
        self.assertIsNone(game.player.action_type)
        self.assertIsInstance(game.action_result, FakeSurface)

    def test_game_eval_text_accepts_integer_labels(self):
        install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.movement = 0
        fake_eval.combat = 1
        fake_eval.take = 2
        fake_eval.use = 3
        fake_eval.find = 4
        fake_eval.buy = 5
        fake_eval.unknown = 6
        fake_eval.map = 0
        fake_eval.box = 1
        fake_eval.ModelLoadError = type("ModelLoadError", (RuntimeError,), {})
        fake_eval.predict_category = lambda text: fake_eval.unknown
        fake_eval.predict_type = lambda text: fake_eval.map
        sys.modules["eval"] = fake_eval

        from Game import Game

        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = "これは未知の行動です"
        game.player = types.SimpleNamespace(target="old", action_type="combat")

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("これは未知の行動です")

        self.assertIsNone(result)
        self.assertIsInstance(game.eval_result, FakeSurface)
        self.assertIsInstance(game.action_result, FakeSurface)

    def test_game_voice_input_key_events_and_result_dispatch(self):
        pygame = install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.movement = 0
        fake_eval.combat = 1
        fake_eval.take = 2
        fake_eval.use = 3
        fake_eval.find = 4
        fake_eval.buy = 5
        fake_eval.unknown = 6
        fake_eval.map = 0
        fake_eval.box = 1
        fake_eval.ModelLoadError = type("ModelLoadError", (RuntimeError,), {})
        sys.modules["eval"] = fake_eval

        from Game import Game
        from VoiceInput import VOICE_EVENT_RECOGNIZED_TEXT, VoiceInputEvent

        class FakeVoiceInput:
            def __init__(self):
                self.started = 0
                self.stopped = 0
                self.events = [VoiceInputEvent(kind=VOICE_EVENT_RECOGNIZED_TEXT, text="スライムへ移動")]

            def start_recording(self):
                self.started += 1
                return True

            def stop_recording_and_transcribe(self):
                self.stopped += 1
                return True

            def poll_event(self):
                if len(self.events) == 0:
                    return None
                return self.events.pop(0)

        game = Game.__new__(Game)
        game.voice_input = FakeVoiceInput()
        game.eval_calls = []

        def fake_eval_text(text):
            game.eval_calls.append(text)
            return True

        game.eval_text = fake_eval_text
        keydown_event = types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_v)
        keyup_event = types.SimpleNamespace(type=pygame.KEYUP, key=pygame.K_v)

        game.handle_voice_input_event(keydown_event)
        game.handle_voice_input_event(keyup_event)
        game.consume_voice_input_events()

        self.assertEqual(1, game.voice_input.started)
        self.assertEqual(1, game.voice_input.stopped)
        self.assertEqual(["スライムへ移動"], game.eval_calls)

    def test_game_renders_voice_input_status(self):
        install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.movement = 0
        fake_eval.combat = 1
        fake_eval.take = 2
        fake_eval.use = 3
        fake_eval.find = 4
        fake_eval.buy = 5
        fake_eval.unknown = 6
        fake_eval.map = 0
        fake_eval.box = 1
        fake_eval.ModelLoadError = type("ModelLoadError", (RuntimeError,), {})
        sys.modules["eval"] = fake_eval

        from Game import Game

        class FakeVoiceInput:
            def get_status_text(self):
                return "録音しています"

        game = Game.__new__(Game)
        game.screen = FakeSurface((800, 600))
        game.voice_status_font = FakeFont()
        game.voice_status_result = None
        game.voice_input = FakeVoiceInput()

        game.render_voice_input_status()

        self.assertEqual("録音しています", game.voice_status_result.rendered_text)
        self.assertEqual((game.voice_status_result, (300, 510)), game.screen.blit_calls[-1])

    def test_ambiguous_buy_potion_waits_for_shop_choice_and_count(self):
        install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.movement = 0
        fake_eval.combat = 1
        fake_eval.take = 2
        fake_eval.use = 3
        fake_eval.find = 4
        fake_eval.buy = 5
        fake_eval.unknown = 6
        fake_eval.map = 0
        fake_eval.box = 1
        fake_eval.ModelLoadError = type("ModelLoadError", (RuntimeError,), {})
        fake_eval.predict_category = lambda text: fake_eval.buy
        fake_eval.predict_type = lambda text: fake_eval.box
        sys.modules["eval"] = fake_eval

        from Game import Game
        from Item import HP_Potion, MP_Potion

        class FakePlayer:
            def __init__(self):
                self.target = None
                self.action_type = None
                self.item_box = []
                self.bought_items = []

            def buy(self, item=None, shop=None):
                self.bought_items.append(item)
                return True

        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = ""
        game.start_eval = False
        game.pending_choice = None
        with contextlib.redirect_stdout(io.StringIO()):
            game.player = FakePlayer()
        game.shop = types.SimpleNamespace(item_type_list=[HP_Potion, MP_Potion])

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("ポーションを買う")

        self.assertFalse(result)
        self.assertEqual("buy", game.pending_choice["action"])
        self.assertIn("1: HPポーション", game.action_result.rendered_text)
        self.assertIn("2: MPポーション", game.action_result.rendered_text)

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("2 2")

        self.assertTrue(result)
        self.assertIsNone(game.pending_choice)
        self.assertEqual(MP_Potion, type(game.player.bought_items[0]))
        self.assertEqual(2, game.player.bought_items[0].count)

    def test_pending_buy_choice_accepts_name_and_count(self):
        install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.movement = 0
        fake_eval.combat = 1
        fake_eval.take = 2
        fake_eval.use = 3
        fake_eval.find = 4
        fake_eval.buy = 5
        fake_eval.unknown = 6
        fake_eval.map = 0
        fake_eval.box = 1
        fake_eval.ModelLoadError = type("ModelLoadError", (RuntimeError,), {})
        sys.modules["eval"] = fake_eval

        from Game import Game
        from Item import HP_Potion, MP_Potion

        class FakePlayer:
            def __init__(self):
                self.target = None
                self.action_type = None
                self.bought_items = []

            def buy(self, item=None, shop=None):
                self.bought_items.append(item)
                return True

        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.action_result = None
        game.nlp_text = ""
        game.start_eval = True
        game.player = FakePlayer()
        game.shop = types.SimpleNamespace(item_type_list=[HP_Potion, MP_Potion])
        game.pending_choice = {
            "action": "buy",
            "choices": [
                game.make_potion_choice(HP_Potion),
                game.make_potion_choice(MP_Potion),
            ],
        }

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("mp 2")

        self.assertTrue(result)
        self.assertIsNone(game.pending_choice)
        self.assertEqual(MP_Potion, type(game.player.bought_items[0]))
        self.assertEqual(2, game.player.bought_items[0].count)

    def test_pending_choice_accepts_punctuation_separators(self):
        install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.movement = 0
        fake_eval.combat = 1
        fake_eval.take = 2
        fake_eval.use = 3
        fake_eval.find = 4
        fake_eval.buy = 5
        fake_eval.unknown = 6
        fake_eval.map = 0
        fake_eval.box = 1
        fake_eval.ModelLoadError = type("ModelLoadError", (RuntimeError,), {})
        sys.modules["eval"] = fake_eval

        from Game import Game
        from Item import HP_Potion, MP_Potion

        class FakePlayer:
            def __init__(self):
                self.target = None
                self.action_type = None
                self.bought_items = []

            def buy(self, item=None, shop=None):
                self.bought_items.append(item)
                return True

        cases = [
            ("2,2", MP_Potion, 2),
            ("HPポーション;2", HP_Potion, 2),
            ("mp/3", MP_Potion, 3),
        ]
        for input_text, expected_type, expected_count in cases:
            with self.subTest(input_text=input_text):
                game = Game.__new__(Game)
                game.nlp_result_font = FakeFont()
                game.action_result = None
                game.nlp_text = ""
                game.start_eval = True
                game.player = FakePlayer()
                game.shop = types.SimpleNamespace(item_type_list=[HP_Potion, MP_Potion])
                game.pending_choice = {
                    "action": "buy",
                    "choices": [
                        game.make_potion_choice(HP_Potion),
                        game.make_potion_choice(MP_Potion),
                    ],
                }

                with contextlib.redirect_stdout(io.StringIO()):
                    result = game.eval_text(input_text)

                self.assertTrue(result)
                self.assertIsNone(game.pending_choice)
                self.assertEqual(expected_type, type(game.player.bought_items[0]))
                self.assertEqual(expected_count, game.player.bought_items[0].count)

    def test_ambiguous_use_potion_waits_for_box_choice_and_count(self):
        install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.movement = 0
        fake_eval.combat = 1
        fake_eval.take = 2
        fake_eval.use = 3
        fake_eval.find = 4
        fake_eval.buy = 5
        fake_eval.unknown = 6
        fake_eval.map = 0
        fake_eval.box = 1
        fake_eval.ModelLoadError = type("ModelLoadError", (RuntimeError,), {})
        fake_eval.predict_category = lambda text: fake_eval.use
        fake_eval.predict_type = lambda text: fake_eval.box
        sys.modules["eval"] = fake_eval

        from Game import Game
        from Item import HP_Potion, MP_Potion

        class FakePlayer:
            def __init__(self):
                self.target = None
                self.action_type = None
                self.hp = 100
                self.hp_max = 200
                self.mp = 100
                self.mp_max = 250
                self.name = "player"
                self.item_box = [HP_Potion(count=5), MP_Potion(count=3), None]

            def check_hp_limit(self):
                self.hp = min(self.hp, self.hp_max)

            def check_mp_limit(self):
                self.mp = min(self.mp, self.mp_max)

            def use(self, index):
                item = self.item_box[index]
                after_count = item.use(self)
                if after_count <= 0:
                    self.item_box[index] = None
                return True

        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = ""
        game.start_eval = False
        game.pending_choice = None
        with contextlib.redirect_stdout(io.StringIO()):
            game.player = FakePlayer()
        game.shop = types.SimpleNamespace(item_type_list=[HP_Potion, MP_Potion])

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("ポーションを使う")

        self.assertFalse(result)
        self.assertEqual("use", game.pending_choice["action"])
        self.assertIn("1: HPポーション", game.action_result.rendered_text)
        self.assertIn("2: MPポーション", game.action_result.rendered_text)

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("1 2")

        self.assertTrue(result)
        self.assertIsNone(game.pending_choice)
        self.assertEqual(3, game.player.item_box[0].count)
        self.assertEqual(3, game.player.item_box[1].count)


if __name__ == "__main__":
    unittest.main()
