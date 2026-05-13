import os
import pygame

class Sprite(pygame.sprite.Sprite):
    def __init__(self, image_path, x, y, size, fallback_color=(255, 0, 0)):
        """画像ファイルまたは欠落時の矩形 Surface を持つ sprite。

        引数:
            image_path: 読み込み対象の画像パス。
            x: sprite 左上の初期 x 座標。
            y: sprite 左上の初期 y 座標。
            size: 画像読み込み成功時の拡大縮小サイズ、または矩形代替のサイズ。
            fallback_color: 画像が存在しない場合に pygame で生成する矩形色。

        呼び出し側:
            画像ファイルがない環境でも `image` と `rect` は必ず生成される。
        """
        super().__init__()
        #print('画像を作る')
        self.load_and_scale_image(image_path, size, fallback_color)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

    def load_and_scale_image(self, image_path, size, fallback_color):
        try:
            # 画像が存在するか確認
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"画像ファイルが見つかりません: {image_path}")

            # 画像の読み込みと最適化
            original_image = pygame.image.load(image_path).convert_alpha()

            # 画像のリサイズ
            self.image = pygame.transform.scale(original_image, size)
        except (pygame.error, FileNotFoundError) as e:
            print(f"Warning: テクスチャを読み込めません: {e}。デフォルトの矩形テクスチャを使用します。")
            self.image = pygame.Surface(size)
            self.image.fill(fallback_color)

    def resize(self, new_size):
        """画像を新しいサイズにリサイズするメソッド"""
        self.image = pygame.transform.scale(self.image, new_size)
        original_center = self.rect.center
        self.rect = self.image.get_rect()
        self.rect.center = original_center

    def change_position(self, position):
        self.rect.x = position[0]
        self.rect.y = position[1]
