from abc import ABC, abstractmethod
from typing import Tuple, List
from pygame import Rect
from pygame import draw

from GameUtils import BOX_POSITION, check_is_number
from GameUtils import distance_square
from GameUtils import normalize
from GameUtils import calc_vector_length
from GameUtils import can_attack
from Shop import Shop
from Color import GREED, RED, WHITE
from Item import HP_Potion, Item
from Building import  Building
from SpriteSheet import SpriteSheet

slime_sprites = "./resources/Slime1_Idle_full.png"
orc_idle_full = "./resources/orc1_idle_full.png"
player_sprites = "./resources/characters.png"


class Character(ABC):
    def __init__(self, x, y, game, sprite_sheet=None, name=""):
        self.x = x
        self.y = y
        self.position: Tuple[float, float] = (x, y)
        self.game_ = game
        self.name = name
        self.is_moving = False
        self.BOX_LENGTH = 3
        if type(sprite_sheet) is SpriteSheet:
            self.sprite_sheet = sprite_sheet
            self.sprite = sprite_sheet.get_image(0, 0, 64, 64)
            self.rect = self.sprite.get_rect()
            self.rect.center = self.position
        else:
            self.sprite_sheet = None
            print("非適切なsprite_sheetでオブジェクトを生成しようとしている。")
            print(id(self))
            print(type(self))

    def move(self, speed_x, speed_y):
        if check_is_number(speed_x) and check_is_number(speed_y):
            Rect.move_ip(self.rect, speed_x, speed_y)

    def update(self):
        self.x = self.rect.centerx
        self.y = self.rect.centery
        self.position = (self.x, self.y)
        self.game_.screen.blit(self.sprite, self.rect)

    def move_to(self, target):
        self.is_moving = True
        stop_move_distance = 10
        value_distance_square = distance_square((self.x, self.y), (target.x, target.y))
        #print(value_distance_square)
        if value_distance_square > stop_move_distance and self.is_moving:
            direction = ((target.x - self.x), (target.y - self.y))
            direction_normalized = normalize(direction)
            self.move(direction_normalized[0]*3, direction_normalized[1]*3)
        elif self.is_moving:
            self.is_moving = False
        elif not self.is_moving:
            self.game_.target = None

    @abstractmethod
    def cleanup(self):
        pass

class Player(Character):
    def __init__(self, x, y, game, sprite_sheet=None, name="player"):
        if sprite_sheet is None:
            self.sprite_sheet = SpriteSheet(player_sprites, fallback_color=WHITE)
        else:
            self.sprite_sheet = sprite_sheet
        self.sprite = self.sprite_sheet.get_image(96, 0, 16, 16)
        self.x = x
        self.y = y
        self.position: Tuple[float, float] = (x, y)
        self.game_ = game
        self.name = name
        self.is_moving = False
        self.BOX_LENGTH = 3
        self.rect = self.sprite.get_rect()
        self.rect.center = self.position
        self.item_box: List[Item | None] = []
        for _ in range(self.BOX_LENGTH):
            self.item_box.append(None)
        self._init_status()
        self.setup_default_item()
        # 移動あるいは戦闘のターゲット
        self.target = None
        # 戦闘か移動かを判断する変数
        self.action_type = None

    def _init_status(self) -> None:
        """プレイヤーの初期ステータス"""
        self.hp = 100
        self.hp_max = 200
        self.mp = 100
        self.mp_max = 250

    def attack(self, target: 'Monster'):
        if isinstance(target, Monster) and can_attack(self, target):
            target.damage(value=100)
            #print(f'attack !')

    def take(self, item):
        # 同じアイテムがすでに所持している場合:
        # アイテムの数を増やす
        if self.have_item(item=item, add_item=True):
            #print('True')
            return True
        # 同じアイテムを所持していない場合:
        # かばんの容量をチェックしてアイテムを追加
        else:
            # アイテムボックスに追加
            for idx, my_item in enumerate(self.item_box):
                if my_item == None:
                    # spriteを追加
                    item.sprite.change_position(BOX_POSITION[idx])
                    # spriteの位置を修正
                    self.game_.all_sprites.add(item.sprite)
                    self.item_box[idx] = item
                    print(f"{item.name}をゲットしました。(所持数: {item.count})")
                    # nlpの評価が画面に表示させる
                    txt = f"{item.name}をゲットしました。(所持数: {item.count})"
                    self.game_.action_result = self.game_.nlp_result_font.render(txt, True, WHITE)
                    return True

            print('ボックスがいっぱいです。')
            txt = 'ボックスがいっぱいです。'
            self.game_.action_result = self.game_.nlp_result_font.render(txt, True, WHITE)
            return False

    def use(self, index):
        try:
            if self.have_item(index=index):
                if isinstance(self.item_box[index], Item):
                    after_count = self.item_box[index].use(self)
                    print(after_count)
                    if after_count <= 0:
                        self.item_box[index].check_count()
                        #self.item_box.remove(self.item_box[index])
                        self.item_box[index] = None
                    return True
            txt = '使用できません。'
            print(txt)
            self.game_.action_result = self.game_.nlp_result_font.render(txt, True, WHITE)
            return False
        except IndexError:
            print("無効なインデックスです。")
            return False

    def buy(self, item=None, shop=None):
        if isinstance(item, Item) == False:
            return False
        if isinstance(shop, Shop):
            if shop.has_item(type(item)):
                if self.take(item):
                    print('購入が成功しました。')
                    txt = '購入が成功しました。'
                    self.game_.action_result = self.game_.nlp_result_font.render(txt, True, WHITE)
                    return True
                else:
                    print('ボックスがいっぱいです。')
                    txt = 'ボックスがいっぱいです。'
                    self.game_.action_result = self.game_.nlp_result_font.render(txt, True, WHITE)
                    return False
            return False
        return False

    def check_hp_limit(self):
        if self.hp > self.hp_max:
            self.hp = self.hp_max
        elif self.hp < 0:
            self.hp = 0

    def check_mp_limit(self):
        if self.mp > self.mp_max:
            self.mp = self.mp_max
        elif self.mp < 0:
            self.mp = 0

    def setup_default_item(self):

        hp_potion = HP_Potion(count=5)
        self.take(hp_potion)

    def have_item(self, item=None, index=None, add_item=False):
        """itemあるいはindexを渡して、アイテムの所持をチェックする"""
        def check():
            for i in self.item_box:
                # 同じアイテムの種類で
                if type(i) == type(item) and isinstance(i, Item) and isinstance(item, Item):
                    print("同じタイプのアイテムを見つけた。")
                    # アイテムを追加したい場合
                    if add_item:
                        i.count += item.count
                        print(f"{item.name}をゲットしました。(所持数: {i.count})")
                        txt = f"{item.name}をゲットしました。(所持数: {i.count})"
                        self.game_.action_result = self.game_.nlp_result_font.render(txt, True, WHITE)
                    return True

        if item is not None:
            return check()

        if index is not None:
            item = self.item_box[index]
            return check()

        print("アイテムが見つかりませんでした。")
        txt = 'アイテムが見つかりませんでした。'
        self.game_.action_result = self.game_.nlp_result_font.render(txt, True, WHITE)
        return False


    def is_attack_action(self):
        return self.target and isinstance(self.target, Monster) and self.action_type == "combat"


    def is_move_action(self):
        return self.target and \
            (isinstance(self.target, Monster) or isinstance(self.target, Building)) and \
            self.action_type == "movement"

    def cleanup(self):
        super().cleanup()


class Monster(Character):
    def __init__(self, x, y, game, sprite_sheet=None, name='monster'):
        super().__init__(x, y, game, sprite_sheet, name)
        self.hp: int = 100
        self.name: str = name
        self.alive: bool = True

    def damage(self, value: int):
        self.hp = max(0, self.hp - value)
        if self.hp <= 0 and self.alive:
            self.alive = False
            self.die()

    def cleanup(self):
        self.rect = None
        pass

    def die(self):
        print(f'[{self.name}]が死亡しました。')
        txt = f'[{self.name}]が死亡しました。'
        self.game_.action_result = self.game_.nlp_result_font.render(txt, True, WHITE)
        self.cleanup()

class Goblin(Monster):
    def __init__(self, x, y, game, sprite_sheet=None, name="ゴブリン"):
        if sprite_sheet is None:
            sprite_sheet = SpriteSheet(orc_idle_full, fallback_color=RED)
        super().__init__(x, y, game, sprite_sheet, name)


class Slime(Monster):
    def __init__(self, x, y, game, sprite_sheet=None, name="スライム"):
        if sprite_sheet is None:
            sprite_sheet = SpriteSheet(slime_sprites, fallback_color=RED)
        super().__init__(x, y, game, sprite_sheet, name)
