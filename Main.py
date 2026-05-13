from game.Game import Game

def main():
    """pygame ゲームを生成し、終了時に必ず shutdown 境界を通す。

    Caller:
    - Ctrl-C またはウィンドウ終了後も `Game.shutdown()` で音声 worker と pygame を閉じる。
    """
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
