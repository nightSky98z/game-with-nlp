from game.Sprite import Sprite
from game.GameUtils import BOX_POSITION, ITEM_SHOW_COUNT_OFFSET
from game.Color import BLUE, RED, WHITE

HP_POTION_PATH = "./resources/hp_potion.png"
MP_POTION_PATH = "./resources/mp_potion.png"
MEDICINE_PATH = "./resources/medicinal_plant.png"
DEFAULT_ITEM_SPRITE_SIZE = (25, 25)

class Item:
    def __init__(self, name="", sprite=None,count=1):
        """所持数と表示 sprite を持つ item を初期化する。

        Params:
        - name: UI とログに出す item 名。
        - sprite: `Sprite` instance。`None` または別型の場合は描画 sprite を持たない。
        - count: 所持数または購入数。

        Caller:
        - sprite がない item は box 表示や kill ができない。
        """
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
        """汎用 item を 1 個消費する。

        Params:
        - target: 使用対象。基底 item では参照しない。

        Returns:
        - 使用後の count。
        - `None`: count が 0 以下で使用できない。

        Caller:
        - 派生 item は回復などの効果を追加してから同じ count 境界を守る。
        """
        if self.count > 0:
            self.count -= 1
            self.check_count()
            return self.count
        return

    def check_count(self):
        """count が 0 になった item sprite を描画グループから外す。

        Returns:
        - 現在の count。

        Caller:
        - `item_box` から slot を空にする責任は呼び出し側が持つ。
        """
        if self.count < 1:
            if type(self.sprite) is Sprite:
                self.sprite.kill()
                #print('kill')
        return self.count

class HP_Potion(Item):
    def __init__(self, name="HPポーション", sprite=None, count=1, value=10):
        """HP 回復ポーションを初期化する。

        Params:
        - name: UI とログに出す item 名。
        - sprite: 表示用 sprite。`None` の場合は画像を読み、失敗時は赤い矩形を使う。
        - count: 所持数または購入数。
        - value: 1 回使用ごとの HP 回復量。
        """
        if sprite is None:
            sprite = Sprite(HP_POTION_PATH, 0, 0, DEFAULT_ITEM_SPRITE_SIZE, fallback_color=RED)
        super().__init__(name, sprite, count)
        self.value = value

    def use(self, target):
        """対象の HP を回復し、ポーションを 1 個消費する。

        Params:
        - target: `hp` / `hp_max` / `check_hp_limit()` を持つ対象。

        Returns:
        - 使用後の count。
        - `None`: count が 0 以下で使用できない。

        Caller:
        - HP 上限 clamp は target の `check_hp_limit()` に委ねる。
        """
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
        """HP ポーションの count 境界を基底 item と同じ規則で処理する。

        Returns:
        - 現在の count。
        """
        return super().check_count()

class MP_Potion(Item):
    def __init__(self, name="MPポーション", sprite=None, count=1, value=10):
        """MP 回復ポーションを初期化する。

        Params:
        - name: UI とログに出す item 名。
        - sprite: 表示用 sprite。`None` の場合は画像を読み、失敗時は青い矩形を使う。
        - count: 所持数または購入数。
        - value: 1 回使用ごとの MP 回復量。
        """
        if sprite is None:
            sprite = Sprite(MP_POTION_PATH, 0, 0, DEFAULT_ITEM_SPRITE_SIZE, fallback_color=BLUE)
        super().__init__(name, sprite, count)
        self.value = value

    def use(self, target):
        """対象の MP を回復し、ポーションを 1 個消費する。

        Params:
        - target: `mp` / `mp_max` / `check_mp_limit()` を持つ対象。

        Returns:
        - 使用後の count。
        - `None`: count が 0 以下で使用できない。

        Caller:
        - MP 上限 clamp は target の `check_mp_limit()` に委ねる。
        """
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
        """MP ポーションの count 境界を基底 item と同じ規則で処理する。

        Returns:
        - 現在の count。
        """
        return super().check_count()
