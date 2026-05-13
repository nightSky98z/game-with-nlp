import pygame
from inference.TextUtils import normalize_ascii_width
from game.UIFont import create_ui_font

class TextInput:
    def __init__(self, x, y, width, height):
        """pygame のテキスト入力欄と IME composition 状態を初期化する。

        Params:
        - x: 入力欄左上 x。
        - y: 入力欄左上 y。
        - width: 初期幅。描画時は入力文字幅に応じて広がる。
        - height: 入力欄高さ。

        Caller:
        - pygame 初期化後に作る。日本語入力の環境設定は上位で済ませる。
        """
        # 初期設定
        self.rect = pygame.Rect(x, y, width, height)
        self.text = ""
        self.active = False # 入力ボックスのアクティブ状態

        self.font = create_ui_font(24)

        self.color_inactive = pygame.Color('lightskyblue3')
        self.color_active = pygame.Color('dodgerblue2')
        self.color = self.color_inactive

        # IME入力用
        self.composition = ""
        self.submitted_composition_text = ""
        self.submitted_full_text = ""

    def handle_event(self, event, game_object=None):
        """pygame event を入力欄状態へ反映し、Return で送信文字列を返す。

        Params:
        - event: pygame event。mouse / key / text input / text editing を処理する。
        - game_object: `nlp_text` を持つゲーム本体。`None` の場合は戻り値だけ返す。

        Returns:
        - 送信された文字列。
        - 空文字列: 送信なし、または送信直後の IME 後追い commit を捨てた。

        Caller:
        - active 状態でないキー入力は無視する。
        - Return 送信時に入力欄と composition は空にする。
        """
        # マウスクリックの処理
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.active = True
                pygame.key.start_text_input()
                pygame.key.set_text_input_rect(self.rect)
            else:
                self.active = False
                pygame.key.stop_text_input()
            self.color = self.color_active if self.active else self.color_inactive

        # キー入力の処理
        if self.active:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    # macOS IME は確定前 composition を描画には渡すが、Return の順序によって TEXTINPUT が来ないことがある。
                    submitted_text = normalize_ascii_width(self.text + self.composition)
                    submitted_composition_text = normalize_ascii_width(self.composition)
                    if submitted_composition_text != "":
                        self.submitted_composition_text = submitted_composition_text
                        self.submitted_full_text = submitted_text
                    else:
                        self.clear_submitted_text_guard()
                    print(submitted_text)
                    if game_object is not None:
                        game_object.nlp_text = submitted_text
                    self.text = ""
                    self.composition = ""
                    return submitted_text
                elif event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]

            elif event.type == pygame.TEXTINPUT:
                # IME確定後の入力は、表示と送信の境界で英数字の幅だけ揃える。
                input_text = normalize_ascii_width(event.text)
                if self.should_ignore_textinput_after_submit(input_text):
                    self.clear_submitted_text_guard()
                    return ""
                self.clear_submitted_text_guard()
                self.text += input_text
                self.composition = ""

            elif event.type == pygame.TEXTEDITING:
                # IME入力中のテキスト
                self.composition = normalize_ascii_width(event.text)
        return ""

    def should_ignore_textinput_after_submit(self, input_text):
        """Return 送信直後に IME が遅れて返す確定文字列か判定する。

        Params:
        - input_text: `TEXTINPUT` から来た正規化済み文字列。

        Returns:
        - `True`: 直前の Return で送信済みの composition/full text と同じなので入力欄へ戻さない。
        - `False`: 通常の新規入力として扱う。

        Caller:
        - Return 送信時に `submitted_composition_text` と `submitted_full_text` を保存してから呼ぶ。
        """
        if input_text == "":
            return False
        if self.submitted_composition_text != "" and input_text == self.submitted_composition_text:
            return True
        if self.submitted_full_text != "" and input_text == self.submitted_full_text:
            return True
        return False

    def clear_submitted_text_guard(self):
        """Return 後の IME 後追い commit を 1 回だけ判定する状態を消す。

        Caller:
        - `TEXTINPUT` を処理した後に呼ぶ。guard を残し続けると次の同じ文字列入力を誤って捨てる。
        """
        self.submitted_composition_text = ""
        self.submitted_full_text = ""

    def draw(self, screen):
        """入力中テキストと IME composition を画面へ描画する。

        Params:
        - screen: pygame の描画先 Surface。

        Caller:
        - 毎フレーム main thread から呼ぶ。表示幅は現在の文字列幅に合わせて更新される。
        """
        # テキストを描画
        display_text = self.text + self.composition
        txt_surface = self.font.render(display_text, True, self.color)

        # テキストの幅を制限
        width = max(200, txt_surface.get_width()+10)
        self.rect.w = width

        # 描画
        screen.blit(txt_surface, (self.rect.x+5, self.rect.y+5))
        pygame.draw.rect(screen, self.color, self.rect, 2)

def main():
    """TextInput 単体確認用の pygame ループを起動する。

    Caller:
    - モジュールを直接実行した場合だけ使う。ゲーム本体の起動経路では呼ばない。
    """
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    clock = pygame.time.Clock()

    # IMEの有効化
    pygame.key.start_text_input()

    text_input = TextInput(100, 100, 200, 40)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            r = text_input.handle_event(event)
            if r != None and r != "":
                if type(r) == str:
                    print(r)

        screen.fill((30, 30, 30))
        text_input.draw(screen)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
