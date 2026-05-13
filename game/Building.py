from typing import Tuple

from pygame import draw
from pygame import Rect

class Building:
    def __init__(self, name, x, y, sprite, game) -> None:
        """マップ上の建造物表示オブジェクトを初期化する。

        Params:
        - name: ゲーム内の正規建造物名。移動対象解決の表示名として使う。
        - x: 初期中心 x 座標。
        - y: 初期中心 y 座標。
        - sprite: pygame Surface。rect はこの Surface から作る。
        - game: 描画先 screen を持つゲーム本体。

        Caller:
        - `sprite` と `game.screen` は有効な pygame 初期化後オブジェクトである必要がある。
        """
        self.name = name
        self.x = x
        self.y = y
        self.position: Tuple[float, float] = (x, y)
        self.half_width = 10
        self.sprite = sprite
        self.game_ = game
        self.rect = self.sprite.get_rect()
        self.rect.center = self.position

    #def _create_rect(self) -> Rect:
    #    rect_pos = (self.x - self.half_width,   # left-top position x
    #                self.y - self.half_width,   # left-top position y
    #                self.half_width*2,          # width
    #                self.half_width*2)          # height
    #    return draw.rect(self.game_.screen, self.draw_color, rect_pos)

    def update(self):
        """現在の rect 位置へ建造物 sprite を描画する。

        Caller:
        - 毎フレーム main thread から呼ぶ。座標更新はこの関数では行わない。
        """
        #draw.rect(self.game_.screen, self.draw_color, self.rect)
        self.game_.screen.blit(self.sprite, self.rect)
