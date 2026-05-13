from game.Sprite import Sprite
from game.GameUtils import BOX_POSITION, ITEM_SHOW_COUNT_OFFSET
from game.Color import BLUE, RED, WHITE

HP_POTION_PATH = "./resources/hp_potion.png"
MP_POTION_PATH = "./resources/mp_potion.png"
MEDICINE_PATH = "./resources/medicinal_plant.png"
DEFAULT_ITEM_SPRITE_SIZE = (25, 25)

class Item:
    def __init__(self, name="", sprite=None,count=1):
        self.name = name
        if type(sprite) is Sprite:
            self.sprite = sprite
        else:
            self.sprite = None
            print("非適切なspriteでオブジェクトを生成しようとしている。")
            print(id(self))
            print(type(self))

        self.count = count

    def use(self, target):
        if self.count > 0:
            self.count -= 1
            self.check_count()
            return self.count
        return

    def check_count(self):
        if self.count < 1:
            if type(self.sprite) is Sprite:
                self.sprite.kill()
                #print('kill')
        return self.count

class HP_Potion(Item):
    def __init__(self, name="HPポーション", sprite=None, count=1, value=10):
        if sprite is None:
            sprite = Sprite(HP_POTION_PATH, 0, 0, DEFAULT_ITEM_SPRITE_SIZE, fallback_color=RED)
        super().__init__(name, sprite, count)
        self.value = value

    def use(self, target):
        if self.count > 0:
            self.count -= 1
            pre_hp = target.hp
            target.hp += self.value
            target.check_hp_limit()
            after_hp = target.hp
            print(f"{target.name}:hp {pre_hp}->{after_hp} (max:{target.hp_max})")
            self.check_count()
            return self.count
        else:
            print(f"アイテム{self.name}が存在しません")
            self.check_count()
            return

    def check_count(self):
        return super().check_count()

class MP_Potion(Item):
    def __init__(self, name="MPポーション", sprite=None, count=1, value=10):
        if sprite is None:
            sprite = Sprite(MP_POTION_PATH, 0, 0, DEFAULT_ITEM_SPRITE_SIZE, fallback_color=BLUE)
        super().__init__(name, sprite, count)
        self.value = value

    def use(self, target):
        if self.count > 0:
            self.count -= 1
            pre_mp = target.mp
            target.mp += self.value
            target.check_mp_limit()
            after_mp = target.mp
            print(f"{target.name}:mp {pre_mp}->{after_mp} (max:{target.mp_max})")
            self.check_count()
            return self.count
        else:
            print(f"アイテム{self.name}が存在しません")
            self.check_count()
            return

    def check_count(self):
        return super().check_count()
