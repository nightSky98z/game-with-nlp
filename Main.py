from game.Game import Game

def main():
    game = Game()
    while game.running:
        game.update()
    game.shutdown()

if __name__ == '__main__':
    main()
