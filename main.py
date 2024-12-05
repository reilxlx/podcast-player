
import sys
from PyQt5.QtWidgets import QApplication
from player import PodcastPlayer

def main():
    app = QApplication(sys.argv)


    font = app.font()
    font.setFamily(".AppleSystemUIFont")               
    app.setFont(font)

    app.setStyle('Fusion')
    player = PodcastPlayer()
    player.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
