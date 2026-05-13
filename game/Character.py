from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Literal, Tuple
from pygame import Rect
from pygame import draw

from game.GameUtils import BOX_POSITION, check_is_number
from game.GameUtils import distance_square
from game.GameUtils import normalize
from game.GameUtils import calc_vector_length
from game.GameUtils import can_attack
from game.Shop import Shop
from game.Color import GREED, RED, WHITE
from game.Item import HP_Potion, Item
from game.Building import Building
from game.SpriteSheet import SpriteSheet

slime_sprites = "./resources/Slime1_Idle_full.png"
orc_idle_full = "./resources/orc1_idle_full.png"
player_sprites = "./resources/characters.png"


class Character(ABC):
    def __init__(self, x, y, game, sprite_sheet=None, name=""):
        """描画 sprite と map 上の位置を持つキャラクター基底状態を作る。

        Params:
        - x: 初期中心 x 座標。
        - y: 初期中心 y 座標。
        - game: 描画先 screen とゲーム状態を持つ本体。
        - sprite_sheet: `SpriteSheet` instance。基底 class は先頭 sprite を使う。
        - name: UI とログに出す名前。

        Caller:
        - `sprite_sheet` が `SpriteSheet` でない場合、sprite/rect は保証されない。
        """
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
        """rect を指定速度分だけ移動する。

        Params:
        - speed_x: x 方向の移動量。数値以外は無視する。
        - speed_y: y 方向の移動量。数値以外は無視する。

        Caller:
        - `update()` で rect center から `position` を同期する。
        """
        if check_is_number(speed_x) and check_is_number(speed_y):
            Rect.move_ip(self.rect, speed_x, speed_y)

    def update(self):
        """rect から論理座標を同期し、sprite を描画する。

        Caller:
        - pygame main thread から毎フレーム呼ぶ。
        - `rect` と `sprite` が有効な状態である必要がある。
        """
        self.x = self.rect.centerx
        self.y = self.rect.centery
        self.position = (self.x, self.y)
        self.game_.screen.blit(self.sprite, self.rect)

    def move_to(self, target):
        """対象へ近づくように 1 フレーム分だけ移動する。

        Params:
        - target: `x` / `y` を持つ移動先 object。

        Caller:
        - 到達後は `is_moving` を落とす。さらに次回呼び出しで `game_.target` を空にする既存挙動を持つ。
        """
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
        """キャラクター破棄時の派生 class 用 cleanup 境界。

        Caller:
        - 派生 class は描画参照や状態をここで解放する。
        """
        pass

class Player(Character):
    def __init__(self, x, y, game, sprite_sheet=None, name="player"):
        """プレイヤーの描画、所持 box、初期ステータスを作る。

        Params:
        - x: 初期中心 x 座標。
        - y: 初期中心 y 座標。
        - game: 描画先 screen と UI font を持つゲーム本体。
        - sprite_sheet: プレイヤー用 `SpriteSheet`。`None` の場合は既定画像または白矩形を使う。
        - name: ログに出すプレイヤー名。

        Caller:
        - 初期 item 追加で `item_box` と action_result が更新される。
        """
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
        self.target: Monster | Building | None = None
        # 戦闘か移動かを判断する変数
        self.action_type: Literal["movement", "combat"] | None = None

    def _init_status(self) -> None:
        """プレイヤーの初期ステータス"""
        self.hp = 100
        self.hp_max = 200
        self.mp = 100
        self.mp_max = 250

    def attack(self, target: 'Monster'):
        """攻撃可能範囲内の monster に固定ダメージを与える。

        Params:
        - target: 攻撃対象 monster。

        Returns:
        - 戻り値は使わない。範囲外または monster 以外なら何もしない。
        """
        if isinstance(target, Monster) and can_attack(self, target):
            target.damage(value=100)
            #print(f'attack !')

    def take(self, item):
        """item を所持 box に追加、または同型 item に count を加算する。

        Params:
        - item: 取得対象 item instance。

        Returns:
        - `True`: 追加または count 加算に成功した。
        - `False`: item box に空きがない。

        Caller:
        - 成功時は item sprite を `all_sprites` に登録し、UI 表示を更新する場合がある。
        """
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
        """item box の指定 slot にある item を 1 回使用する。

        Params:
        - index: `item_box` の slot index。

        Returns:
        - `True`: item を使用した。
        - `False`: index が無効、空 slot、または使用できない。

        Caller:
        - count が 0 以下になった slot は `None` に戻す。
        """
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
        """shop が販売する item を購入して所持 box へ追加する。

        Params:
        - item: 購入する item instance。
        - shop: `Shop` instance。販売可否は item type で判定する。

        Returns:
        - `True`: 購入して所持に追加できた。
        - `False`: item/shop が不正、販売していない、または box が満杯。

        Caller:
        - お金の概念はまだない。購入成功は所持追加成功と同義。
        """
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
        """HP を `0..hp_max` の範囲へ clamp する。

        Caller:
        - HP を直接変更した後に呼ぶ。
        """
        if self.hp > self.hp_max:
            self.hp = self.hp_max
        elif self.hp < 0:
            self.hp = 0

    def check_mp_limit(self):
        """MP を `0..mp_max` の範囲へ clamp する。

        Caller:
        - MP を直接変更した後に呼ぶ。
        """
        if self.mp > self.mp_max:
            self.mp = self.mp_max
        elif self.mp < 0:
            self.mp = 0

    def setup_default_item(self):
        """初期所持 item として HP ポーションを追加する。

        Caller:
        - `item_box` 初期化後に呼ぶ。`take()` 経由なので UI 表示も更新される。
        """
        hp_potion = HP_Potion(count=5)
        self.take(hp_potion)

    def have_item(self, item=None, index=None, add_item=False):
        """所持中アイテムを型で探し、必要なら同型アイテム数を加算する。

        Params:
        - item: 探す対象の item。`add_item=True` の場合は、この item の count を既存 item に移す。
        - index: 所持スロット index。指定時はそのスロットの item 型を使って同型 item を探す。
        - add_item: `True` の場合、同型 item が見つかれば count と UI 表示を更新する。

        Returns:
        - `True`: 同型 item を所持している。
        - `False`: `item` も `index` も指定されていない。
        - `None`: 探したが同型 item が見つからない。

        Caller:
        - 純粋な確認関数ではない。`add_item=True` では item_box と action_result を変更する。
        """
        def check():
            """現在の `item` と同型の所持 item を探し、必要なら count を加算する。

            Returns:
            - `True`: 同型 item が見つかった。
            - `None`: 同型 item が見つからない。
            """
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
        """現在の player 状態が戦闘 target を持つか返す。

        Returns:
        - `True`: target が `Monster` で、action_type が `combat`。
        - `False` または `None`: target がない、または戦闘状態ではない。
        """
        return self.target and isinstance(self.target, Monster) and self.action_type == "combat"


    def is_move_action(self):
        """現在の player 状態が移動 target を持つか返す。

        Returns:
        - `True`: target が `Monster` または `Building` で、action_type が `movement`。
        - `False` または `None`: target がない、または移動状態ではない。
        """
        return self.target and \
            (isinstance(self.target, Monster) or isinstance(self.target, Building)) and \
            self.action_type == "movement"

    def cleanup(self):
        """プレイヤー破棄時の cleanup 境界。

        Caller:
        - 現時点で追加解放はないが、基底 cleanup 境界を通す。
        """
        super().cleanup()


class Monster(Character):
    def __init__(self, x, y, game, sprite_sheet=None, name='monster'):
        """monster の HP と生存状態を初期化する。

        Params:
        - x: 初期中心 x 座標。
        - y: 初期中心 y 座標。
        - game: 描画先 screen と UI font を持つゲーム本体。
        - sprite_sheet: monster 用 `SpriteSheet`。
        - name: UI とログに出す monster 名。
        """
        super().__init__(x, y, game, sprite_sheet, name)
        self.hp: int = 100
        self.name: str = name
        self.alive: bool = True

    def damage(self, value: int):
        """monster にダメージを与え、HP 0 で死亡処理へ進める。

        Params:
        - value: 減算する HP。負値は想定していない。

        Caller:
        - 死亡処理は 1 回だけ実行されるよう `alive` で守る。
        """
        self.hp = max(0, self.hp - value)
        if self.hp <= 0 and self.alive:
            self.alive = False
            self.die()

    def cleanup(self):
        """monster の描画 rect 参照を外す。

        Caller:
        - 死亡後に呼ぶ。以後 `update()` しない前提で、Game 側が dead monster を配列から外す。
        """
        self.rect = None
        pass

    def die(self):
        """monster を死亡状態として UI とログへ反映する。

        Caller:
        - `damage()` から呼ぶ。直接呼ぶ場合も重複死亡には注意する。
        """
        print(f'[{self.name}]が死亡しました。')
        txt = f'[{self.name}]が死亡しました。'
        self.game_.action_result = self.game_.nlp_result_font.render(txt, True, WHITE)
        self.cleanup()

class Goblin(Monster):
    def __init__(self, x, y, game, sprite_sheet=None, name="ゴブリン"):
        """ゴブリン monster を初期化する。

        Params:
        - x: 初期中心 x 座標。
        - y: 初期中心 y 座標。
        - game: 描画先 screen と UI font を持つゲーム本体。
        - sprite_sheet: 指定時はその sprite sheet を使う。`None` なら既定画像または赤矩形を使う。
        - name: UI とログに出す monster 名。
        """
        if sprite_sheet is None:
            sprite_sheet = SpriteSheet(orc_idle_full, fallback_color=RED)
        super().__init__(x, y, game, sprite_sheet, name)


class Slime(Monster):
    def __init__(self, x, y, game, sprite_sheet=None, name="スライム"):
        """スライム monster を初期化する。

        Params:
        - x: 初期中心 x 座標。
        - y: 初期中心 y 座標。
        - game: 描画先 screen と UI font を持つゲーム本体。
        - sprite_sheet: 指定時はその sprite sheet を使う。`None` なら既定画像または赤矩形を使う。
        - name: UI とログに出す monster 名。
        """
        if sprite_sheet is None:
            sprite_sheet = SpriteSheet(slime_sprites, fallback_color=RED)
        super().__init__(x, y, game, sprite_sheet, name)
