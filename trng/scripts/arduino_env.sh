# Подключите перед работой с портом (Linux):
#   export PATH="/home/vlad/Документы/cursorvaya/.local/bin:$PATH"
#
# Если «Permission denied» на /dev/ttyUSB0 или /dev/ttyACM0:
#   sudo usermod -aG dialout "$USER"
#   … перелогиньтесь …
# Либо на одну сессию (менее безопасно):
#   sudo chmod 666 /dev/ttyUSB0

export PATH="/home/vlad/Документы/cursorvaya/.local/bin:${PATH}"
