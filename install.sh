#!/bin/bash
# RasCam Installation Script
# Скрипт установки для Raspberry Pi OS 64-bit

set -e

echo "======================================"
echo "RasCam Surveillance System Installer"
echo "======================================"
echo

# Проверка ОС
if [[ ! -f /etc/os-release ]]; then
    echo "Ошибка: не удалось определить ОС"
    exit 1
fi

source /etc/os-release
if [[ "$ID" != "raspbian" && "$ID" != "debian" ]]; then
    echo "Предупреждение: этот скрипт предназначен для Raspberry Pi OS"
    read -p "Продолжить? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
   echo "Этот скрипт должен быть запущен с правами root"
   echo "Используйте: sudo ./install.sh"
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
echo "[1/8] Обновление списка пакетов..."
apt-get update -qq

# Установка системных пакетов
echo "[2/8] Установка системных пакетов..."
apt-get install -y \
    python3-pip \
    python3-picamera2 \
    python3-opencv \
    python3-numpy \
    libcamera-apps \
    ffmpeg \
    vlc

# Установка MediaMTX
echo "[3/8] Установка MediaMTX..."
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
echo "[4/8] Настройка MediaMTX..."
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

# Установка Python пакетов
echo "[5/8] Установка Python пакетов..."
pip3 install --upgrade pip
pip3 install Flask psutil av

# Настройка gpu_mem
echo "[6/8] Настройка GPU memory..."
if ! grep -q "gpu_mem=128" /boot/config.txt; then
    echo "gpu_mem=128" >> /boot/config.txt
    echo "GPU memory установлена на 128MB (требуется перезагрузка)"
fi

# Настройка директории USB SSD
echo "[7/8] Настройка хранилища..."
STORAGE_DIR="/media/usb_ssd"
mkdir -p $STORAGE_DIR/recordings
chown -R $REAL_USER:$REAL_USER $STORAGE_DIR

echo ""
echo "Для автоматического монтирования USB SSD:"
echo "1. Подключите USB SSD"
echo "2. Узнайте UUID: sudo blkid"
echo "3. Добавьте в /etc/fstab:"
echo "   UUID=ваш-uuid /media/usb_ssd ext4 defaults,nofail 0 2"
echo ""

# Создание systemd services
echo "[8/8] Установка systemd services..."

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

# RasCam service
cat > /etc/systemd/system/rascam.service <<EOF
[Unit]
Description=RasCam Surveillance System
After=network.target mediamtx.service
Wants=mediamtx.service

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/surveillance.py
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
echo "Следующие шаги:"
echo
echo "1. Отредактируйте config.json:"
echo "   nano $INSTALL_DIR/config.json"
echo
echo "2. Измените пароли в /etc/mediamtx/mediamtx.yml"
echo
echo "3. Запустите сервисы:"
echo "   sudo systemctl start mediamtx"
echo "   sudo systemctl start rascam"
echo
echo "4. Включите автозапуск:"
echo "   sudo systemctl enable mediamtx"
echo "   sudo systemctl enable rascam"
echo
echo "5. Проверьте статус:"
echo "   sudo systemctl status rascam"
echo
echo "6. Веб-интерфейс доступен по адресу:"
echo "   http://$(hostname -I | awk '{print $1}'):5000"
echo
echo "7. RTSP stream:"
echo "   rtsp://viewer:changeme@$(hostname -I | awk '{print $1}'):8554/cam1"
echo
echo "ВАЖНО: Если изменили gpu_mem, перезагрузите систему: sudo reboot"
echo
