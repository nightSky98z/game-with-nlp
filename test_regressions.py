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
        self.time = types.SimpleNamespace(Clock=lambda: types.SimpleNamespace(tick=lambda fps: None))
        self.draw = types.SimpleNamespace(rect=lambda *args, **kwargs: None)
        self.sprite = types.SimpleNamespace(Sprite=FakeSpriteBase, Group=FakeGroup)
        self.font = types.SimpleNamespace(
            SysFont=lambda *args, **kwargs: FakeFont(),
            Font=lambda *args, **kwargs: FakeFont(),
        )
        self.image = types.SimpleNamespace(load=self._load_missing_image)
        self.transform = types.SimpleNamespace(scale=lambda image, size: FakeSurface(size))
        self.key_start_count = 0
        self.key_stop_count = 0
        self.text_input_rects = []
        self.key = types.SimpleNamespace(
            start_text_input=self._start_text_input,
            stop_text_input=self._stop_text_input,
            set_text_input_rect=self._set_text_input_rect,
        )
        self.quit_called = 0

    def _load_missing_image(self, filename):
        raise FileNotFoundError(filename)

    def _start_text_input(self):
        self.key_start_count += 1

    def _stop_text_input(self):
        self.key_stop_count += 1

    def _set_text_input_rect(self, rect):
        self.text_input_rects.append(rect)

    def quit(self):
        self.quit_called += 1


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
            "inference",
            "inference.TextClassifier",
            "inference.TextUtils",
            "inference.eval",
            "threading",
            "Game",
            "game",
            "game.SpriteSheet",
            "game.Sprite",
            "game.Shop",
            "game.Building",
            "game.Character",
            "game.Item",
            "game.TextInput",
            "game.VoiceInput",
            "game.Game",
            "game.Color",
            "game.GameUtils",
            "game.GameConfig",
            "game.UIFont",
            "game.TextInputEnvironment",
            "joblib",
            "faster_whisper",
        )

    def test_sprite_sheet_missing_asset_uses_requested_rectangle_color(self):
        install_fake_pygame()
        from game.SpriteSheet import SpriteSheet

        with contextlib.redirect_stdout(io.StringIO()) as stdout_buffer:
            sprite_sheet = SpriteSheet("./resources/missing.png", fallback_color=(255, 255, 255))
        image = sprite_sheet.get_image(0, 0, 16, 16)

        self.assertEqual((255, 255, 255), image.fill_color)
        self.assertEqual((16, 16), image.size)
        self.assertIn("Warning:", stdout_buffer.getvalue())
        self.assertIn("デフォルトの矩形テクスチャを使用します", stdout_buffer.getvalue())

    def test_sprite_missing_asset_warns_and_uses_default_rectangle(self):
        install_fake_pygame()
        from game.Sprite import Sprite

        with contextlib.redirect_stdout(io.StringIO()) as stdout_buffer:
            sprite = Sprite("./resources/missing.png", 1, 2, (8, 8), fallback_color=(1, 2, 3))

        self.assertEqual((1, 2, 3), sprite.image.fill_color)
        self.assertEqual((8, 8), sprite.image.size)
        self.assertIn("Warning:", stdout_buffer.getvalue())
        self.assertIn("デフォルトの矩形テクスチャを使用します", stdout_buffer.getvalue())

    def test_shop_missing_asset_uses_blue_rectangle(self):
        install_fake_pygame()
        from game.Color import BLUE
        from game.Shop import Shop

        with contextlib.redirect_stdout(io.StringIO()):
            shop = Shop(name="商店", x=10, y=10, sprite=None, game=None, item_type_list=[])

        self.assertEqual(BLUE, shop.sprite.fill_color)

    def test_potion_missing_assets_use_hp_red_and_mp_blue_rectangles(self):
        install_fake_pygame()
        from game.Color import BLUE, RED
        from game.Item import HP_Potion, MP_Potion

        with contextlib.redirect_stdout(io.StringIO()):
            hp_potion = HP_Potion()
            mp_potion = MP_Potion()

        self.assertEqual(RED, hp_potion.sprite.image.fill_color)
        self.assertEqual(BLUE, mp_potion.sprite.image.fill_color)

    def test_main_constructs_game_once(self):
        fake_game_module = types.ModuleType("game.Game")

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
        sys.modules["game.Game"] = fake_game_module

        import Main

        Main.main()

        self.assertEqual(1, FakeGame.init_count)

    def test_main_shutdown_runs_when_keyboard_interrupt_stops_loop(self):
        fake_game_module = types.ModuleType("game.Game")

        class InterruptingGame:
            shutdown_count = 0

            def __init__(self):
                self.running = True

            def update(self):
                raise KeyboardInterrupt

            def shutdown(self):
                type(self).shutdown_count += 1
                self.running = False

        fake_game_module.Game = InterruptingGame
        sys.modules["game.Game"] = fake_game_module

        import Main

        Main.main()

        self.assertEqual(1, InterruptingGame.shutdown_count)

    def test_game_shutdown_quits_pygame_without_raising_system_exit(self):
        pygame = install_fake_pygame()
        from game.Game import Game

        class FakeVoiceInput:
            def __init__(self):
                self.shutdown_timeout = None

            def shutdown(self, timeout_seconds=None):
                self.shutdown_timeout = timeout_seconds

        game = Game.__new__(Game)
        game.running = True
        game.voice_input = FakeVoiceInput()

        game.shutdown()

        self.assertFalse(game.running)
        self.assertEqual(1.0, game.voice_input.shutdown_timeout)
        self.assertEqual(1, pygame.quit_called)

    def test_game_update_stops_before_rendering_after_quit_event(self):
        pygame = install_fake_pygame()
        from game.Game import Game

        quit_event = types.SimpleNamespace(type=pygame.QUIT)
        pygame.event = types.SimpleNamespace(get=lambda: [quit_event])

        game = Game.__new__(Game)
        game.running = True
        game.nlp_text = ""
        game.text_input_box = types.SimpleNamespace(handle_event=lambda event, game_object: "")
        game.consume_count = 0
        game.render_count = 0
        game.tick_count = 0

        def consume_voice_input_events():
            game.consume_count += 1

        def render():
            game.render_count += 1

        def maintain_frame_rate():
            game.tick_count += 1

        game.consume_voice_input_events = consume_voice_input_events
        game.render = render
        game.maintain_frame_rate = maintain_frame_rate

        game.update()

        self.assertFalse(game.running)
        self.assertEqual(0, game.consume_count)
        self.assertEqual(0, game.render_count)
        self.assertEqual(0, game.tick_count)

    def test_game_does_not_use_item_shortcut_while_text_input_is_active(self):
        pygame = install_fake_pygame()
        from game.Game import Game

        key_event = types.SimpleNamespace(type=pygame.KEYUP, key=pygame.K_u)
        pygame.event = types.SimpleNamespace(get=lambda: [key_event])

        class FakePlayer:
            def __init__(self):
                self.use_calls = []

            def use(self, index):
                self.use_calls.append(index)
                return True

        game = Game.__new__(Game)
        game.nlp_text = ""
        game.player = FakePlayer()
        game.text_input_box = types.SimpleNamespace(active=True, handle_event=lambda event, game_object: "")

        game.handle_events()

        self.assertEqual([], game.player.use_calls)

    def test_player_take_returns_false_when_box_is_full(self):
        install_fake_pygame()
        from game.Character import Player
        from game.Item import HP_Potion, Item, MP_Potion

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
        from game.TextInput import TextInput

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
        from game.TextInput import TextInput

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

    def test_text_input_submits_uncommitted_ime_composition_on_return(self):
        install_fake_pygame()
        from game.TextInput import TextInput

        text_input = TextInput(0, 0, 200, 40)
        text_input.active = True
        text_input.text = "ゴブリンを"
        text_input.composition = "倒して"
        game_object = types.SimpleNamespace(nlp_text="")
        return_event = types.SimpleNamespace(type=3, key=13)

        with contextlib.redirect_stdout(io.StringIO()):
            submitted = text_input.handle_event(return_event, game_object)

        self.assertEqual("ゴブリンを倒して", submitted)
        self.assertEqual("ゴブリンを倒して", game_object.nlp_text)
        self.assertEqual("", text_input.text)
        self.assertEqual("", text_input.composition)

    def test_text_input_ignores_ime_commit_after_return_submit(self):
        install_fake_pygame()
        from game.TextInput import TextInput

        text_input = TextInput(0, 0, 200, 40)
        text_input.active = True
        text_input.text = "ゴブリンを"
        text_input.composition = "倒して"
        game_object = types.SimpleNamespace(nlp_text="")
        return_event = types.SimpleNamespace(type=3, key=13)
        late_commit_event = types.SimpleNamespace(type=5, text="倒して")

        with contextlib.redirect_stdout(io.StringIO()):
            text_input.handle_event(return_event, game_object)
        text_input.handle_event(late_commit_event, game_object)

        self.assertEqual("ゴブリンを倒して", game_object.nlp_text)
        self.assertEqual("", text_input.text)
        self.assertEqual("", text_input.composition)

    def test_text_input_accepts_new_text_after_plain_return_submit(self):
        install_fake_pygame()
        from game.TextInput import TextInput

        text_input = TextInput(0, 0, 200, 40)
        text_input.active = True
        text_input.text = "a"
        game_object = types.SimpleNamespace(nlp_text="")
        return_event = types.SimpleNamespace(type=3, key=13)
        next_text_event = types.SimpleNamespace(type=5, text="a")

        with contextlib.redirect_stdout(io.StringIO()):
            text_input.handle_event(return_event, game_object)
        text_input.handle_event(next_text_event, game_object)

        self.assertEqual("a", game_object.nlp_text)
        self.assertEqual("a", text_input.text)
        self.assertEqual("", text_input.composition)

    def test_text_input_clears_composition_when_textinput_commits(self):
        install_fake_pygame()
        from game.TextInput import TextInput

        text_input = TextInput(0, 0, 200, 40)
        text_input.active = True
        text_input.composition = "倒して"
        text_event = types.SimpleNamespace(type=5, text="倒して")

        text_input.handle_event(text_event)

        self.assertEqual("倒して", text_input.text)
        self.assertEqual("", text_input.composition)

    def test_text_input_enables_ime_only_while_active(self):
        pygame = install_fake_pygame()
        from game.TextInput import TextInput

        text_input = TextInput(0, 0, 200, 40)

        self.assertEqual(0, pygame.key_start_count)
        self.assertEqual(0, pygame.key_stop_count)

        inside_click = types.SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, pos=(10, 10))
        outside_click = types.SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, pos=(300, 300))
        text_input.handle_event(inside_click)
        text_input.handle_event(outside_click)

        self.assertFalse(text_input.active)
        self.assertEqual(1, pygame.key_start_count)
        self.assertEqual(1, pygame.key_stop_count)
        self.assertEqual([text_input.rect], pygame.text_input_rects)

    def test_ui_font_uses_os_specific_japanese_font_candidates(self):
        pygame = install_fake_pygame()

        class TrackingFontModule:
            def __init__(self):
                self.match_calls = []
                self.font_calls = []

            def match_font(self, names, bold=False, italic=False):
                self.match_calls.append((names, bold, italic))
                return "/system/japanese-ui.ttf"

            def Font(self, path, size):
                self.font_calls.append((path, size))
                return FakeFont()

            def SysFont(self, names, size, bold=False, italic=False):
                raise AssertionError("matched font path should be used before SysFont fallback")

        font_module = TrackingFontModule()
        pygame.font = font_module

        from game.UIFont import create_ui_font
        from game.UIFont import get_japanese_font_candidates

        font = create_ui_font(25, platform_name="Windows")

        self.assertIsInstance(font, FakeFont)
        self.assertIn("Yu Gothic", get_japanese_font_candidates("Windows"))
        self.assertIn("Hiragino Sans", get_japanese_font_candidates("Darwin"))
        self.assertIn("Noto Sans CJK JP", get_japanese_font_candidates("Linux"))
        self.assertEqual((get_japanese_font_candidates("Windows"), False, False), font_module.match_calls[0])
        self.assertEqual([("/system/japanese-ui.ttf", 25)], font_module.font_calls)

    def test_ui_font_prefers_os_font_file_before_match_font(self):
        install_fake_pygame()
        from game.UIFont import get_japanese_font_file_candidates
        from game.UIFont import resolve_japanese_font_path

        darwin_paths = get_japanese_font_file_candidates("Darwin")

        def path_exists(path):
            return path == darwin_paths[0]

        def fail_match_font(names, bold=False, italic=False):
            raise AssertionError("OS 固定フォントファイルがある場合は match_font まで進まない")

        self.assertIn("/System/Library/Fonts/", darwin_paths[0])
        self.assertEqual(darwin_paths[0], resolve_japanese_font_path("Darwin", path_exists, fail_match_font))

    def test_text_input_environment_does_not_force_linux_ime_module_on_macos(self):
        from game.TextInputEnvironment import configure_text_input_environment

        mac_env = {"SDL_IM_MODULE": "fcitx"}
        linux_env = {}

        configure_text_input_environment(platform_name="Darwin", environ=mac_env)
        configure_text_input_environment(platform_name="Linux", environ=linux_env)

        self.assertNotIn("SDL_IM_MODULE", mac_env)
        self.assertEqual("fcitx", linux_env["SDL_IM_MODULE"])

    def test_normalize_text_applies_nfkc_before_lowercase(self):
        from inference.TextUtils import normalize_text

        self.assertEqual("abchpポーション", normalize_text("ＡＢＣ　HP、ポーション。"))

    def test_train_text_classifier_uses_ruri_topic_embeddings(self):
        from inference.TextClassifier import RURI_CLASSIFICATION_PREFIX
        from inference.TextClassifier import train_text_classifier

        class FakeEmbeddingBackend:
            def __init__(self):
                self.encode_calls = []

            def encode(self, texts, batch_size=None):
                self.encode_calls.append((list(texts), batch_size))
                return [[float(len(text)), float(index)] for index, text in enumerate(texts)]

        class FakeLabelClassifier:
            def __init__(self):
                self.fit_embeddings = None
                self.fit_labels = None

            def fit(self, embeddings, labels):
                self.fit_embeddings = embeddings
                self.fit_labels = list(labels)
                return self

            def predict(self, embeddings):
                return [1 for _embedding in embeddings]

        embedding_backend = FakeEmbeddingBackend()
        label_classifier = FakeLabelClassifier()

        classifier = train_text_classifier(
            ["打死", "スライムへ移動"],
            [1, 0],
            embedding_backend=embedding_backend,
            label_classifier=label_classifier,
        )

        self.assertIs(label_classifier, classifier.label_classifier)
        self.assertEqual(
            [RURI_CLASSIFICATION_PREFIX + "打死", RURI_CLASSIFICATION_PREFIX + "スライムへ移動"],
            embedding_backend.encode_calls[0][0],
        )
        self.assertEqual(32, embedding_backend.encode_calls[0][1])
        self.assertEqual([[8.0, 0.0], [13.0, 1.0]], label_classifier.fit_embeddings)
        self.assertEqual([1, 0], label_classifier.fit_labels)

    def test_predict_label_id_uses_ruri_embedding_classifier(self):
        from inference.TextClassifier import RURI_CLASSIFICATION_PREFIX
        from inference.TextClassifier import RuriEmbeddingTextClassifier
        from inference.TextClassifier import predict_label_id

        class FakeEmbeddingBackend:
            def __init__(self):
                self.encode_calls = []

            def encode(self, texts, batch_size=None):
                self.encode_calls.append((list(texts), batch_size))
                return [[10.0, 20.0] for _text in texts]

        class FakeLabelClassifier:
            def __init__(self):
                self.predict_embeddings = None

            def predict(self, embeddings):
                self.predict_embeddings = embeddings
                return [1]

        embedding_backend = FakeEmbeddingBackend()
        label_classifier = FakeLabelClassifier()
        classifier = RuriEmbeddingTextClassifier(
            embedding_backend=embedding_backend,
            label_classifier=label_classifier,
        )

        label_id = predict_label_id(classifier, "打倒")

        self.assertEqual(1, label_id)
        self.assertEqual([RURI_CLASSIFICATION_PREFIX + "打倒"], embedding_backend.encode_calls[0][0])
        self.assertEqual([[10.0, 20.0]], label_classifier.predict_embeddings)

    def test_ruri_embedding_backend_shares_loaded_model_by_name_and_device(self):
        fake_sentence_transformers = types.ModuleType("sentence_transformers")
        load_calls = []

        class FakeSentenceTransformer:
            def __init__(self, model_name, device=None):
                load_calls.append((model_name, device))

            def encode(self, texts, batch_size=None, convert_to_numpy=None):
                return [[float(len(text))] for text in texts]

        fake_sentence_transformers.SentenceTransformer = FakeSentenceTransformer
        sys.modules["sentence_transformers"] = fake_sentence_transformers

        from inference import TextClassifier
        from inference.TextClassifier import RuriSentenceEmbeddingBackend

        TextClassifier._ruri_model_cache.clear()
        first_backend = RuriSentenceEmbeddingBackend(model_name="cl-nagoya/ruri-v3-30m", device="cpu")
        second_backend = RuriSentenceEmbeddingBackend(model_name="cl-nagoya/ruri-v3-30m", device="cpu")

        first_backend.encode(["トピック: 倒す"], batch_size=1)
        second_backend.encode(["トピック: 使う"], batch_size=1)

        self.assertEqual([("cl-nagoya/ruri-v3-30m", "cpu")], load_calls)

    def test_voice_input_records_transcribes_and_exposes_status(self):
        from game.VoiceInput import VOICE_EVENT_RECOGNIZED_TEXT, VOICE_STATE_IDLE, VOICE_STATE_RECORDING
        from game.VoiceInput import VOICE_STATE_TRANSCRIBING, VoiceInput

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

    def test_voice_input_prints_recognized_text_once_for_debug(self):
        from game.VoiceInput import VOICE_EVENT_RECOGNIZED_TEXT, VoiceInput

        class FakeRecorder:
            def start(self):
                pass

            def stop_to_wav_file(self):
                return "debug.wav"

        class FakeTranscriber:
            def transcribe(self, audio_path):
                return "ゴブリンを倒して"

        voice_input = VoiceInput(recorder=FakeRecorder(), transcriber=FakeTranscriber())
        stdout_buffer = io.StringIO()

        with contextlib.redirect_stdout(stdout_buffer):
            self.assertTrue(voice_input.start_recording())
            self.assertTrue(voice_input.stop_recording_and_transcribe())
            self.assertTrue(voice_input.wait_for_pending_transcription(timeout_seconds=1.0))
        event = voice_input.poll_event()

        self.assertEqual(VOICE_EVENT_RECOGNIZED_TEXT, event.kind)
        self.assertEqual("ゴブリンを倒して", event.text)
        self.assertEqual(1, stdout_buffer.getvalue().count("音声認識結果: ゴブリンを倒して"))

    def test_voice_input_reports_transcription_error_without_text_event(self):
        from game.VoiceInput import VOICE_EVENT_ERROR, VOICE_STATE_IDLE, VoiceInput

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

    def test_faster_whisper_transcriber_uses_fast_short_command_options(self):
        fake_faster_whisper = types.ModuleType("faster_whisper")
        model_calls = []
        transcribe_calls = []

        class FakeWhisperModel:
            def __init__(self, model_size, device=None, compute_type=None):
                model_calls.append((model_size, device, compute_type))

            def transcribe(self, audio_path, **kwargs):
                transcribe_calls.append((audio_path, kwargs))
                return [types.SimpleNamespace(text=" 倒して ")], object()

        fake_faster_whisper.WhisperModel = FakeWhisperModel
        sys.modules["faster_whisper"] = fake_faster_whisper

        from game.VoiceInput import DEFAULT_MAX_TRANSCRIPTION_SECONDS, DEFAULT_WHISPER_MODEL_SIZE
        from game.VoiceInput import FasterWhisperTranscriber

        transcriber = FasterWhisperTranscriber()
        text = transcriber.transcribe("voice.wav")

        self.assertEqual("tiny", DEFAULT_WHISPER_MODEL_SIZE)
        self.assertEqual(120.0, DEFAULT_MAX_TRANSCRIPTION_SECONDS)
        self.assertEqual("倒して", text)
        self.assertEqual([("tiny", "cpu", "int8")], model_calls)
        self.assertEqual("voice.wav", transcribe_calls[0][0])
        self.assertEqual("ja", transcribe_calls[0][1]["language"])
        self.assertEqual(1, transcribe_calls[0][1]["beam_size"])
        self.assertFalse(transcribe_calls[0][1]["vad_filter"])

    def test_voice_input_timeout_releases_state_and_ignores_stale_result(self):
        from game.VoiceInput import VOICE_EVENT_ERROR, VOICE_STATE_IDLE, VOICE_STATE_TRANSCRIBING
        from game.VoiceInput import VoiceInput

        current_time = {"value": 0.0}
        transcription_started = threading.Event()
        continue_transcription = threading.Event()

        class FakeRecorder:
            def __init__(self):
                self.start_count = 0

            def start(self):
                self.start_count += 1

            def stop_to_wav_file(self):
                return "late.wav"

        class HangingTranscriber:
            def transcribe(self, audio_path):
                transcription_started.set()
                continue_transcription.wait(timeout=1.0)
                return "倒して"

        recorder = FakeRecorder()
        voice_input = VoiceInput(
            recorder=recorder,
            transcriber=HangingTranscriber(),
            max_transcription_seconds=0.5,
            clock=lambda: current_time["value"],
        )

        self.assertTrue(voice_input.start_recording())
        self.assertTrue(voice_input.stop_recording_and_transcribe())
        self.assertTrue(transcription_started.wait(timeout=1.0))
        self.assertEqual(VOICE_STATE_TRANSCRIBING, voice_input.state)

        current_time["value"] = 1.0
        event = voice_input.poll_event()

        self.assertEqual(VOICE_EVENT_ERROR, event.kind)
        self.assertIn("タイムアウト", event.message)
        self.assertEqual(VOICE_STATE_IDLE, voice_input.state)
        self.assertTrue(voice_input.start_recording())
        self.assertEqual(2, recorder.start_count)

        continue_transcription.set()
        self.assertTrue(voice_input.wait_for_pending_transcription(timeout_seconds=1.0))
        self.assertIsNone(voice_input.poll_event())

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
            target_eval = importlib.import_module("inference.eval")
            target_eval.MODEL1_PATH = model_path
            target_eval.predict_category("スライムへ移動")
            target_eval.predict_category("ゴブリンへ移動")

            self.assertEqual(1, load_count["model"])
        finally:
            os.unlink(model_path)

    def test_eval_async_warmup_loads_models_and_forces_embedding_warmup(self):
        import threading as real_threading

        target_eval = importlib.import_module("inference.eval")
        load_started = real_threading.Event()
        continue_load = real_threading.Event()
        load_paths = []
        predict_calls = []

        class FakeThread:
            def __init__(self, target, daemon=False):
                self.target = target
                self.daemon = daemon
                self.started = False

            def start(self):
                self.started = True
                self.target()

        def fake_get_model(model_path):
            load_paths.append(model_path)
            load_started.set()
            continue_load.wait(timeout=0.01)
            return object()

        def fake_predict_label_id(model, text):
            predict_calls.append((model, text))
            return 0

        target_eval._model_cache = {}
        target_eval._warmup_state = target_eval.WARMUP_STATE_IDLE
        target_eval._warmup_error_message = None
        target_eval._get_model = fake_get_model
        target_eval.predict_label_id = fake_predict_label_id
        target_eval.threading.Thread = FakeThread

        self.assertTrue(target_eval.start_async_warmup())
        self.assertEqual(target_eval.WARMUP_STATE_READY, target_eval.get_warmup_state())
        self.assertIsNone(target_eval.get_warmup_error_message())
        self.assertIsNone(target_eval.get_warmup_error_code())
        self.assertEqual([target_eval.MODEL1_PATH, target_eval.MODEL2_PATH], load_paths)
        self.assertEqual(2, len(predict_calls))
        self.assertEqual(target_eval.WARMUP_SAMPLE_TEXT, predict_calls[0][1])
        self.assertEqual(target_eval.WARMUP_SAMPLE_TEXT, predict_calls[1][1])

    def test_eval_async_warmup_marks_model_load_error_code(self):
        target_eval = importlib.import_module("inference.eval")

        def failing_get_model(model_path):
            raise target_eval.ModelLoadError("モデルファイルが存在しません")

        target_eval._model_cache = {}
        target_eval._warmup_state = target_eval.WARMUP_STATE_LOADING
        target_eval._warmup_error_message = None
        target_eval._warmup_error_code = None
        target_eval._get_model = failing_get_model

        target_eval._warmup_models()

        self.assertEqual(target_eval.WARMUP_STATE_ERROR, target_eval.get_warmup_state())
        self.assertEqual(target_eval.ERROR_CODE_NLP_MODEL_LOAD_FAILED, target_eval.get_warmup_error_code())
        self.assertIn("モデルファイルが存在しません", target_eval.get_warmup_error_message())

    def test_eval_async_warmup_marks_prediction_error_code(self):
        target_eval = importlib.import_module("inference.eval")

        def fake_get_model(model_path):
            return object()

        def failing_predict_label_id(model, text):
            raise target_eval.TextClassifierError("embedding 生成失敗")

        target_eval._model_cache = {}
        target_eval._warmup_state = target_eval.WARMUP_STATE_LOADING
        target_eval._warmup_error_message = None
        target_eval._warmup_error_code = None
        target_eval._get_model = fake_get_model
        target_eval.predict_label_id = failing_predict_label_id

        target_eval._warmup_models()

        self.assertEqual(target_eval.WARMUP_STATE_ERROR, target_eval.get_warmup_state())
        self.assertEqual(target_eval.ERROR_CODE_NLP_WARMUP_PREDICT_FAILED, target_eval.get_warmup_error_code())
        self.assertIn("embedding 生成失敗", target_eval.get_warmup_error_message())

    def test_eval_async_warmup_marks_error_when_prediction_raises_unexpected_error(self):
        target_eval = importlib.import_module("inference.eval")

        def fake_get_model(model_path):
            return object()

        def failing_predict_label_id(model, text):
            raise ValueError("壊れた分類器出力")

        target_eval._model_cache = {}
        target_eval._warmup_state = target_eval.WARMUP_STATE_LOADING
        target_eval._warmup_error_message = None
        target_eval._warmup_error_code = None
        target_eval._get_model = fake_get_model
        target_eval.predict_label_id = failing_predict_label_id

        target_eval._warmup_models()

        self.assertEqual(target_eval.WARMUP_STATE_ERROR, target_eval.get_warmup_state())
        self.assertEqual(target_eval.ERROR_CODE_NLP_WARMUP_UNKNOWN_FAILED, target_eval.get_warmup_error_code())
        self.assertIn("壊れた分類器出力", target_eval.get_warmup_error_message())

    def test_game_eval_text_waits_while_nlp_model_is_loading(self):
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
        fake_eval.WARMUP_STATE_LOADING = "loading"
        fake_eval.WARMUP_STATE_ERROR = "error"
        fake_eval.ModelLoadError = type("ModelLoadError", (RuntimeError,), {})
        fake_eval.get_warmup_state = lambda: fake_eval.WARMUP_STATE_LOADING
        fake_eval.get_warmup_error_message = lambda: None
        fake_eval.predict_category = lambda text: (_ for _ in ()).throw(AssertionError("loading 中は分類しない"))
        fake_eval.predict_type = lambda text: (_ for _ in ()).throw(AssertionError("loading 中は分類しない"))
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = "ゴブリンを倒して"
        game.player = types.SimpleNamespace(target="old", action_type="combat")

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("ゴブリンを倒して")

        self.assertFalse(result)
        self.assertEqual("", game.nlp_text)
        self.assertEqual("old", game.player.target)
        self.assertEqual("combat", game.player.action_type)
        self.assertEqual("NLPモデル読み込み中", game.eval_result.rendered_text)
        self.assertEqual("読み込み完了後にもう一度入力してください。", game.action_result.rendered_text)

    def test_game_ignores_text_and_voice_input_events_while_nlp_model_is_loading(self):
        pygame = install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.WARMUP_STATE_LOADING = "loading"
        fake_eval.WARMUP_STATE_ERROR = "error"
        fake_eval.get_warmup_state = lambda: fake_eval.WARMUP_STATE_LOADING
        fake_eval.get_warmup_error_message = lambda: None
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        keydown_event = types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_v)
        pygame.event = types.SimpleNamespace(get=lambda: [keydown_event])

        class FakeTextInputBox:
            def __init__(self):
                self.events = []
                self.active = False

            def handle_event(self, event, game_object):
                self.events.append(event)
                game_object.nlp_text = "ゴブリンを倒して"

        class FakeVoiceInput:
            def __init__(self):
                self.started = 0

            def start_recording(self):
                self.started += 1

        game = Game.__new__(Game)
        game.nlp_text = ""
        game.text_input_box = FakeTextInputBox()
        game.voice_input = FakeVoiceInput()
        game.player = types.SimpleNamespace(use=lambda index: None)

        game.handle_events()

        self.assertEqual([], game.text_input_box.events)
        self.assertEqual(0, game.voice_input.started)
        self.assertEqual("", game.nlp_text)

    def test_game_setup_starts_nlp_model_warmup(self):
        install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.start_count = 0

        def start_async_warmup():
            fake_eval.start_count += 1
            return True

        fake_eval.start_async_warmup = start_async_warmup
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        game = Game.__new__(Game)
        game.clock = types.SimpleNamespace()
        game.running = False

        Game.setup_game_components(game)

        self.assertEqual(1, fake_eval.start_count)

    def test_game_renders_nlp_model_loading_status(self):
        install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.WARMUP_STATE_LOADING = "loading"
        fake_eval.WARMUP_STATE_READY = "ready"
        fake_eval.WARMUP_STATE_ERROR = "error"
        fake_eval.get_warmup_state = lambda: fake_eval.WARMUP_STATE_LOADING
        fake_eval.get_warmup_error_message = lambda: None
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        game = Game.__new__(Game)
        game.screen = FakeSurface((800, 600))
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None

        Game.render_nlp_model_status(game)

        self.assertEqual("NLPモデル読み込み中", game.eval_result.rendered_text)
        self.assertEqual("入力は読み込み完了後に実行されます。", game.action_result.rendered_text)

    def test_game_warns_and_stops_safely_when_nlp_model_data_is_missing(self):
        install_fake_pygame()
        fake_eval = types.ModuleType("eval")
        fake_eval.WARMUP_STATE_LOADING = "loading"
        fake_eval.WARMUP_STATE_READY = "ready"
        fake_eval.WARMUP_STATE_ERROR = "error"
        fake_eval.get_warmup_state = lambda: fake_eval.WARMUP_STATE_ERROR
        fake_eval.get_warmup_error_message = lambda: "モデルファイルが存在しません: inference/model1_sklearn.joblib"
        fake_eval.get_warmup_error_code = lambda: "NLP_MODEL_LOAD_FAILED"
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        game = Game.__new__(Game)
        game.running = True
        game.screen = FakeSurface((800, 600))
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None

        with contextlib.redirect_stdout(io.StringIO()) as stdout_buffer:
            Game.render_nlp_model_status(game)

        self.assertFalse(game.running)
        self.assertIn("Warning:", stdout_buffer.getvalue())
        self.assertIn("[NLP_MODEL_LOAD_FAILED]", stdout_buffer.getvalue())
        self.assertIn("プログラムを安全に終了します", stdout_buffer.getvalue())
        self.assertEqual("NLPモデル読み込み失敗", game.eval_result.rendered_text)
        self.assertIn("[NLP_MODEL_LOAD_FAILED]", game.action_result.rendered_text)
        self.assertIn("安全に終了します", game.action_result.rendered_text)

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
        fake_eval.ERROR_CODE_NLP_MODEL_LOAD_FAILED = "NLP_MODEL_LOAD_FAILED"
        fake_eval.ModelLoadError = type("ModelLoadError", (RuntimeError,), {})

        def raise_model_error(text):
            raise fake_eval.ModelLoadError("モデルが見つかりません")

        fake_eval.predict_category = raise_model_error
        fake_eval.predict_type = raise_model_error
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = "スライムへ移動"
        game.running = True
        game.player = types.SimpleNamespace(target="old", action_type="combat")

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("スライムへ移動")

        self.assertFalse(result)
        self.assertFalse(game.running)
        self.assertIsNone(game.player.target)
        self.assertIsNone(game.player.action_type)
        self.assertIsInstance(game.action_result, FakeSurface)
        self.assertIn("[NLP_MODEL_LOAD_FAILED]", game.action_result.rendered_text)

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
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

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
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game
        from game.VoiceInput import VOICE_EVENT_RECOGNIZED_TEXT, VoiceInputEvent

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

    def test_movement_command_with_shop_alias_targets_shop_building(self):
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
        fake_eval.predict_category = lambda text: fake_eval.movement
        fake_eval.predict_type = lambda text: fake_eval.map
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        shop = types.SimpleNamespace(name="商店", x=200, y=200, position=(200, 200), alive=True)
        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = ""
        game.start_eval = False
        game.pending_choice = None
        game.player = types.SimpleNamespace(target=None, action_type=None)
        game.monsters = []
        game.buildings = [shop]

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("ショップに移動")

        self.assertIsNone(result)
        self.assertIs(shop, game.player.target)
        self.assertEqual("movement", game.player.action_type)
        self.assertEqual("商店:移動", game.action_result.rendered_text)

    def test_voice_combat_command_without_name_targets_nearest_monster(self):
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
        fake_eval.predict_category = lambda text: fake_eval.combat
        fake_eval.predict_type = lambda text: fake_eval.map
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game
        from game.VoiceInput import VOICE_EVENT_RECOGNIZED_TEXT, VoiceInputEvent

        class FakeVoiceInput:
            def __init__(self):
                self.events = [VoiceInputEvent(kind=VOICE_EVENT_RECOGNIZED_TEXT, text="倒して")]

            def poll_event(self):
                if len(self.events) == 0:
                    return None
                return self.events.pop(0)

        near_monster = types.SimpleNamespace(name="スライム", x=3, y=4, position=(3, 4), alive=True)
        far_monster = types.SimpleNamespace(name="ゴブリン", x=100, y=100, position=(100, 100), alive=True)
        game = Game.__new__(Game)
        game.voice_input = FakeVoiceInput()
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = ""
        game.start_eval = False
        game.pending_choice = None
        game.player = types.SimpleNamespace(target=None, action_type=None, x=0, y=0, position=(0, 0))
        game.monsters = [far_monster, near_monster]
        game.buildings = []

        with contextlib.redirect_stdout(io.StringIO()):
            game.consume_voice_input_events()

        self.assertIs(near_monster, game.player.target)
        self.assertEqual("combat", game.player.action_type)

    def test_combat_command_with_missing_named_target_does_not_fallback_to_nearest_monster(self):
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
        fake_eval.predict_category = lambda text: fake_eval.combat
        fake_eval.predict_type = lambda text: fake_eval.map
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        slime = types.SimpleNamespace(name="スライム", x=3, y=4, position=(3, 4), alive=True)
        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = ""
        game.start_eval = False
        game.pending_choice = None
        game.player = types.SimpleNamespace(target=None, action_type=None, x=0, y=0, position=(0, 0))
        game.monsters = [slime]
        game.buildings = []

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("ゴブリンを倒して")

        self.assertFalse(result)
        self.assertIsNone(game.player.target)
        self.assertIsNone(game.player.action_type)
        self.assertEqual("ゴブリンがマップにいませんでした。", game.action_result.rendered_text)

    def test_unknown_combat_command_retries_category_with_generic_monster_name(self):
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
        category_calls = []

        def predict_category(text):
            category_calls.append(text)
            if text == "モンスターを倒して":
                return fake_eval.combat
            return fake_eval.unknown

        fake_eval.predict_category = predict_category
        fake_eval.predict_type = lambda text: fake_eval.map
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        slime = types.SimpleNamespace(name="スライム", x=3, y=4, position=(3, 4), alive=True)
        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = ""
        game.start_eval = False
        game.pending_choice = None
        game.player = types.SimpleNamespace(target=None, action_type=None, x=0, y=0, position=(0, 0))
        game.monsters = [slime]
        game.buildings = []

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("スライムを倒して")

        self.assertTrue(result)
        self.assertEqual(["スライムを倒して", "モンスターを倒して"], category_calls)
        self.assertIs(slime, game.player.target)
        self.assertEqual("combat", game.player.action_type)

    def test_combat_command_with_similar_spoken_target_uses_best_alive_monster_match(self):
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
        fake_eval.predict_category = lambda text: fake_eval.combat
        fake_eval.predict_type = lambda text: fake_eval.map
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        goblin = types.SimpleNamespace(name="ゴブリン", x=100, y=100, position=(100, 100), alive=True)
        slime = types.SimpleNamespace(name="スライム", x=3, y=4, position=(3, 4), alive=True)
        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = ""
        game.start_eval = False
        game.pending_choice = None
        game.player = types.SimpleNamespace(target=None, action_type=None, x=0, y=0, position=(0, 0))
        game.monsters = [slime, goblin]
        game.buildings = []

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("オフリングを倒せ")

        self.assertTrue(result)
        self.assertIs(goblin, game.player.target)
        self.assertEqual("combat", game.player.action_type)

    def test_combat_command_with_low_similarity_target_does_not_attack_nearest_monster(self):
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
        fake_eval.predict_category = lambda text: fake_eval.combat
        fake_eval.predict_type = lambda text: fake_eval.map
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        goblin = types.SimpleNamespace(name="ゴブリン", x=3, y=4, position=(3, 4), alive=True)
        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = ""
        game.start_eval = False
        game.pending_choice = None
        game.player = types.SimpleNamespace(target=None, action_type=None, x=0, y=0, position=(0, 0))
        game.monsters = [goblin]
        game.buildings = []

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("ドラゴンを倒せ")

        self.assertFalse(result)
        self.assertIsNone(game.player.target)
        self.assertIsNone(game.player.action_type)
        self.assertEqual("ドラゴンがマップにいませんでした。", game.action_result.rendered_text)

    def test_combat_command_with_generic_target_uses_nearest_monster(self):
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
        fake_eval.predict_category = lambda text: fake_eval.combat
        fake_eval.predict_type = lambda text: fake_eval.map
        sys.modules["eval"] = fake_eval
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

        near_monster = types.SimpleNamespace(name="スライム", x=3, y=4, position=(3, 4), alive=True)
        far_monster = types.SimpleNamespace(name="ゴブリン", x=100, y=100, position=(100, 100), alive=True)
        game = Game.__new__(Game)
        game.nlp_result_font = FakeFont()
        game.eval_result = None
        game.action_result = None
        game.nlp_text = ""
        game.start_eval = False
        game.pending_choice = None
        game.player = types.SimpleNamespace(target=None, action_type=None, x=0, y=0, position=(0, 0))
        game.monsters = [far_monster, near_monster]
        game.buildings = []

        with contextlib.redirect_stdout(io.StringIO()):
            result = game.eval_text("敵を倒して")

        self.assertTrue(result)
        self.assertIs(near_monster, game.player.target)
        self.assertEqual("combat", game.player.action_type)

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
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game

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
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game
        from game.Item import HP_Potion, MP_Potion

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
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game
        from game.Item import HP_Potion, MP_Potion

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
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game
        from game.Item import HP_Potion, MP_Potion

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
        sys.modules["inference.eval"] = fake_eval

        from game.Game import Game
        from game.Item import HP_Potion, MP_Potion

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
