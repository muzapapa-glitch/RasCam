#!/bin/bash
# RasCam Installation Script (with Virtual Environment)
# Альтернативный вариант установки с использованием venv

set -e

echo "======================================"
echo "RasCam Installer (Virtual Environment)"
echo "======================================"
echo

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
   echo "Этот скрипт должен быть запущен с правами root"
   echo "Используйте: sudo ./install_venv.sh"
   exit 1
fi

# Получить текущего пользователя (не root)
REAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$REAL_USER)
INSTALL_DIR="$USER_HOME/RasCam"

echo "Установка в: $INSTALL_DIR"
echo "Пользователь: $REAL_USER"
echo

# Обновление системы
echo "[1/9] Обновление списка пакетов..."
apt-get update -qq

# Установка системных пакетов
echo "[2/9] Установка системных пакетов..."
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-picamera2 \
    python3-opencv \
    python3-numpy \
    libcamera-apps \
    ffmpeg \
    vlc

# Установка MediaMTX
echo "[3/9] Установка MediaMTX..."
MEDIAMTX_VERSION="v1.8.5"
MEDIAMTX_URL="https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/mediamtx_${MEDIAMTX_VERSION}_linux_arm64v8.tar.gz"

if [[ ! -f /usr/local/bin/mediamtx ]]; then
    cd /tmp
    wget -q $MEDIAMTX_URL -O mediamtx.tar.gz
    tar -xzf mediamtx.tar.gz
    mv mediamtx /usr/local/bin/
    chmod +x /usr/local/bin/mediamtx
    rm mediamtx.tar.gz
    echo "MediaMTX установлен"
else
    echo "MediaMTX уже установлен"
fi

# Создание конфигурации MediaMTX
echo "[4/9] Настройка MediaMTX..."
mkdir -p /etc/mediamtx
cat > /etc/mediamtx/mediamtx.yml <<EOF
paths:
  cam1:
    source: publisher
    publishUser: admin
    publishPass: changeme
    readUser: viewer
    readPass: changeme
EOF

# Создание виртуального окружения
echo "[5/9] Создание виртуального окружения Python..."
cd $INSTALL_DIR
sudo -u $REAL_USER python3 -m venv --system-site-packages venv

# Активация venv и установка пакетов
echo "[6/9] Установка Python пакетов в venv..."
sudo -u $REAL_USER $INSTALL_DIR/venv/bin/pip install --upgrade pip
sudo -u $REAL_USER $INSTALL_DIR/venv/bin/pip install Flask psutil av

# Настройка gpu_mem
echo "[7/9] Настройка GPU memory..."
if ! grep -q "gpu_mem=128" /boot/config.txt; then
    echo "gpu_mem=128" >> /boot/config.txt
    echo "GPU memory установлена на 128MB (требуется перезагрузка)"
fi

# Настройка директории USB SSD
echo "[8/9] Настройка хранилища..."
STORAGE_DIR="/media/usb_ssd"
mkdir -p $STORAGE_DIR/recordings
chown -R $REAL_USER:$REAL_USER $STORAGE_DIR

# Создание systemd services
echo "[9/9] Установка systemd services..."

# MediaMTX service
cat > /etc/systemd/system/mediamtx.service <<EOF
[Unit]
Description=MediaMTX RTSP Server
After=network.target

[Service]
Type=simple
User=$REAL_USER
ExecStart=/usr/local/bin/mediamtx /etc/mediamtx/mediamtx.yml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# RasCam service (использует venv)
cat > /etc/systemd/system/rascam.service <<EOF
[Unit]
Description=RasCam Surveillance System
After=network.target mediamtx.service
Wants=mediamtx.service

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/surveillance.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузка systemd
systemctl daemon-reload

echo
echo "======================================"
echo "Установка завершена!"
echo "======================================"
echo
echo "ВАЖНО: Используется виртуальное окружение Python"
echo "       Расположение: $INSTALL_DIR/venv"
echo
echo "Следующие шаги:"
echo
echo "1. Отредактируйте config.json:"
echo "   nano $INSTALL_DIR/config.json"
echo
echo "2. Измените пароли в /etc/mediamtx/mediamtx.yml"
echo
echo "3. Перезагрузите (если изменили gpu_mem):"
echo "   sudo reboot"
echo
echo "4. Запустите сервисы:"
echo "   sudo systemctl start mediamtx"
echo "   sudo systemctl start rascam"
echo
echo "5. Включите автозапуск:"
echo "   sudo systemctl enable mediamtx"
echo "   sudo systemctl enable rascam"
echo
echo "6. Веб-интерфейс:"
echo "   http://$(hostname -I | awk '{print $1}'):5000"
echo
