import pygame
import sys
import os
from TextUtils import normalize_ascii_width

os.environ['SDL_IM_MODULE'] = 'fcitx'

class TextInput:
    def __init__(self, x, y, width, height):
        # 初期設定
        self.rect = pygame.Rect(x, y, width, height)
        self.text = ""
        self.active = False # 入力ボックスのアクティブ状態

        try:
            self.font = pygame.font.SysFont("notosansmonocjkjp", 24)
        except:
            print("Warninig: Japanese font not found. Using default font.")
            self.font = pygame.font.Font(None, 24)

        self.color_inactive = pygame.Color('lightskyblue3')
        self.color_active = pygame.Color('dodgerblue2')
        self.color = self.color_inactive

        # IME入力用
        self.composition = ""
        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(self.rect)

    def handle_event(self, event, game_object=None):
        # マウスクリックの処理
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.active = True
                pygame.key.set_text_input_rect(self.rect)
            else:
                self.active = False
            self.color = self.color_active if self.active else self.color_inactive

        # キー入力の処理
        if self.active:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    submitted_text = normalize_ascii_width(self.text)
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
                self.text += normalize_ascii_width(event.text)

            elif event.type == pygame.TEXTEDITING:
                # IME入力中のテキスト
                self.composition = normalize_ascii_width(event.text)
        return ""

    def draw(self, screen):
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
