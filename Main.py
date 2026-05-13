from game.Game import Game

def main():
    game = None
    try:
        game = Game()
        while game.running:
            game.update()
    except KeyboardInterrupt:
        pass
    finally:
        if game is not None:
            game.shutdown()

if __name__ == '__main__':
    main()
