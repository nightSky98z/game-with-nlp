import math
import asyncio
import time

ATTACKABLE_RANGE_SQUARE = 25
BOX_POSITION = [(700, 560), (650, 560), (600, 560)]
ITEM_SHOW_COUNT_OFFSET = 20

def check_is_number(value):
    if type(value) == int or type(value) == float:
        return True
    else:
        return False

def normalize(vector:tuple, epsilon=1e-5):
    # dim=2
    length = calc_vector_length(vector)
    x = vector[0] / (length + epsilon)
    y = vector[1] / (length + epsilon)
    return (x, y)


def distance(vector1, vector2):
    # dim=2
    value_distance_square = distance_square(vector1, vector2)
    distance = math.sqrt(value_distance_square)
    return distance

def distance_square(vector1, vector2):
    # dim=2
    x_sub = vector1[0] - vector2[0]
    y_sub = vector1[1] - vector2[1]
    value = x_sub*x_sub + y_sub*y_sub
    return value

def calc_vector_length(vector):
    length_square = vector[0]*vector[0] + vector[1]*vector[1]
    return math.sqrt(length_square)

def can_attack(attacker, target):
    return distance_square(attacker.position, target.position) < ATTACKABLE_RANGE_SQUARE

async def delayed_function(delay, callback):
    await asyncio.sleep(delay)
    callback()
