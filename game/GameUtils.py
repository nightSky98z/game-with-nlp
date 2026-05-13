import math
import asyncio
import time

ATTACKABLE_RANGE_SQUARE = 25
BOX_POSITION = [(700, 560), (650, 560), (600, 560)]
ITEM_SHOW_COUNT_OFFSET = 20

def check_is_number(value):
    """値が移動量として使える数値型か返す。

    Params:
    - value: 判定対象。

    Returns:
    - `True`: `int` または `float`。
    - `False`: それ以外。
    """
    if type(value) == int or type(value) == float:
        return True
    else:
        return False

def normalize(vector:tuple, epsilon=1e-5):
    """2D vector を正規化して返す。

    Params:
    - vector: `x, y` の 2 要素 tuple。
    - epsilon: 長さ 0 付近で 0 除算を避けるために足す値。

    Returns:
    - 正規化後の `(x, y)`。
    """
    # dim=2
    length = calc_vector_length(vector)
    x = vector[0] / (length + epsilon)
    y = vector[1] / (length + epsilon)
    return (x, y)


def distance(vector1, vector2):
    """2 点間のユークリッド距離を返す。

    Params:
    - vector1: `x, y` の 2 要素 tuple。
    - vector2: `x, y` の 2 要素 tuple。

    Returns:
    - 2 点間距離。
    """
    # dim=2
    value_distance_square = distance_square(vector1, vector2)
    distance = math.sqrt(value_distance_square)
    return distance

def distance_square(vector1, vector2):
    """2 点間距離の二乗を返す。

    Params:
    - vector1: `x, y` の 2 要素 tuple。
    - vector2: `x, y` の 2 要素 tuple。

    Returns:
    - 2 点間距離の二乗。sqrt を避けたい判定で使う。
    """
    # dim=2
    x_sub = vector1[0] - vector2[0]
    y_sub = vector1[1] - vector2[1]
    value = x_sub*x_sub + y_sub*y_sub
    return value

def calc_vector_length(vector):
    """2D vector の長さを返す。

    Params:
    - vector: `x, y` の 2 要素 tuple。

    Returns:
    - vector のユークリッド長。
    """
    length_square = vector[0]*vector[0] + vector[1]*vector[1]
    return math.sqrt(length_square)

def can_attack(attacker, target):
    """攻撃者と対象の距離が攻撃可能範囲内か返す。

    Params:
    - attacker: `position` を持つ攻撃者。
    - target: `position` を持つ攻撃対象。

    Returns:
    - `True`: 距離二乗が `ATTACKABLE_RANGE_SQUARE` 未満。
    - `False`: 攻撃範囲外。
    """
    return distance_square(attacker.position, target.position) < ATTACKABLE_RANGE_SQUARE

async def delayed_function(delay, callback):
    """指定秒数後に callback を 1 回呼ぶ。

    Params:
    - delay: `asyncio.sleep()` に渡す秒数。
    - callback: delay 後に同期的に呼ぶ関数。

    Caller:
    - callback の例外は呼び出し側の task に伝播する。
    """
    await asyncio.sleep(delay)
    callback()
