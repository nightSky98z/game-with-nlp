import pygame.image

from game.Building import Building
from game.Color import BLUE

class Shop(Building):
    def __init__(self, name="shop", x=10, y=10, sprite=None, game=None, item_type_list=None):
        """購入可能 item type を持つ商店を初期化する。

        Params:
        - name: マップ上の建造物名。内部の正規名として扱う。
        - x: 初期中心 x 座標。
        - y: 初期中心 y 座標。
        - sprite: pygame Surface。`None` の場合は画像を読み込み、失敗時は青い矩形を使う。
        - game: 描画先 screen を持つゲーム本体。
        - item_type_list: 販売する `Item` 派生 class の配列。

        Caller:
        - 販売可否は item instance ではなく item type で判定する。
        """
        if sprite is None:
            try:
                sprite = pygame.image.load("./resources/shop.png").convert_alpha()
            except (pygame.error, FileNotFoundError):
                sprite = pygame.Surface((40, 40))
                sprite.fill(BLUE)
        super().__init__(name, x, y, sprite, game)
        self.item_type_list = item_type_list if item_type_list is not None else []
        print("ショップ設置成功")
        print(self.item_type_list)

    def has_item(self, item_type):
        """商店が指定 item type を販売しているか返す。

        Params:
        - item_type: `HP_Potion` などの class。instance ではなく type を渡す。

        Returns:
        - `True`: `item_type_list` に同じ type が登録されている。
        - `False`: 販売対象ではない。
        """
        for type in self.item_type_list:
            if type == item_type:
                return True
        return False
