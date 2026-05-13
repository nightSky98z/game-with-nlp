from typing import Tuple

from pygame import draw
from pygame import Rect

class Building:
    def __init__(self, name, x, y, sprite, game) -> None:
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
        #draw.rect(self.game_.screen, self.draw_color, self.rect)
        self.game_.screen.blit(self.sprite, self.rect)