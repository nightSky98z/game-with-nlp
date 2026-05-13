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
        """スプライトシート画像を読み込み、失敗時は矩形 fallback を保持する。

        Params:
        - filename: 読み込み対象の画像パス。
        - fallback_color: 画像欠落時に生成する Surface の色。

        Caller:
        - 画像が読めない場合も `get_image()` は Surface を返す。
        """
        self.filename = filename
        self.fallback_color = fallback_color
        try:
            self.sprite_sheet = pygame.image.load(filename).convert_alpha()
        except (pygame.error, FileNotFoundError) as err:
            print(f"Warning: スプライトシートを読み込めません: {err}。デフォルトの矩形テクスチャを使用します。")
            self.sprite_sheet = None

    def get_image(self, x, y, width, height):
        """スプライトシートから指定矩形を切り出して返す。

        Params:
        - x: 切り出し元の左上 x。
        - y: 切り出し元の左上 y。
        - width: 切り出し幅。
        - height: 切り出し高さ。

        Returns:
        - pygame Surface。画像欠落時は `fallback_color` で塗った矩形。
        """
        image = pygame.Surface([width, height])
        if self.sprite_sheet is None:
            image.fill(self.fallback_color)
            return image
        image.set_colorkey((0, 0, 0))
        image.blit(self.sprite_sheet, (0, 0), (x, y, width, height))
        return image

    def get_all_sprites(self, width, height):
        """スプライトシート全体を固定サイズの Surface 配列へ分割する。

        Params:
        - width: 1 sprite の幅。
        - height: 1 sprite の高さ。

        Returns:
        - Surface 配列。画像欠落時は fallback Surface 1 枚だけを返す。
        """
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
