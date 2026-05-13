import pygame

class SpriteSheet:
    """スプライトシート画像、または欠落時の矩形代替を保持する。

    引数:
        filename: 読み込み対象の画像パス。
        fallback_color: 画像が存在しない場合に生成する矩形の色。

    呼び出し側:
        `get_image` の返す Surface は呼び出し側が描画位置を管理する。
    """

    def __init__(self, filename, fallback_color=(255, 0, 0)):
        self.filename = filename
        self.fallback_color = fallback_color
        try:
            self.sprite_sheet = pygame.image.load(filename).convert_alpha()
        except (pygame.error, FileNotFoundError) as err:
            print(f"Warning: スプライトシートを読み込めません: {err}。デフォルトの矩形テクスチャを使用します。")
            self.sprite_sheet = None

    def get_image(self, x, y, width, height):
        image = pygame.Surface([width, height])
        if self.sprite_sheet is None:
            image.fill(self.fallback_color)
            return image
        image.set_colorkey((0, 0, 0))
        image.blit(self.sprite_sheet, (0, 0), (x, y, width, height))
        return image

    def get_all_sprites(self, width, height):
        sprites = []
        if self.sprite_sheet is None:
            sprites.append(self.get_image(0, 0, width, height))
            return sprites

        sheet_width = self.sprite_sheet.get_width()
        sheet_height = self.sprite_sheet.get_height()

        for y in range(0, sheet_height, height):
            for x in range(0, sheet_width, width):
                sprites.append(self.get_image(x, y, width, height))

        return sprites
