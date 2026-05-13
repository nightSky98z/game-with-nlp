import pygame.image

from Building import Building
from Color import BLUE

class Shop(Building):
    def __init__(self, name="shop", x=10, y=10, sprite=None, game=None, item_type_list=None):
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
        for type in self.item_type_list:
            if type == item_type:
                return True
        return False
