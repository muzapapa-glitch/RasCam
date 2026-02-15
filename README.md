# RasCam - Система видеонаблюдения для Raspberry Pi 4

Эффективная система видеонаблюдения с детекцией движения для Raspberry Pi 4 + Camera Module 3.

## Возможности

- **Детекция движения** с настраиваемыми зонами (MSE алгоритм)
- **Запись видео** по движению с предзаписью 5 секунд (H.264)
- **RTSP стриминг** через MediaMTX (WiFi/Ethernet)
- **Мониторинг температуры** с автоматическим управлением нагрузкой
- **Веб-интерфейс** для просмотра записей и настройки зон
- **Автоматическая ротация** файлов с контролем дискового пространства

## Технические характеристики

- Разрешение: 1920x1080 @ 15-30 fps
- Кодек: H.264 (аппаратное кодирование)
- Битрейт: 2-4 Mbps
- Нагрузка CPU: 25-40% (запись + стрим)
- Хранилище: ~2.6 GB/день (при 10% активности)

## Требования

### Оборудование
- Raspberry Pi 4 (4GB+ рекомендуется)
- Camera Module 3 (стандартная или широкоугольная)
- USB SSD 120GB+ (или SD карта A2)
- Охлаждение (радиатор + вентилятор рекомендуется)
- Блок питания 5V 3A

### Софт
- Raspberry Pi OS 64-bit Bookworm
- Python 3.11+
- MediaMTX v1.8+
- libcamera (включено в ОС)

## Установка

### Быстрая установка

```bash
# Клонировать репозиторий
git clone https://github.com/muzapapa-glitch/RasCam.git
cd RasCam

# Запустить скрипт установки
sudo ./install.sh

# Настроить конфигурацию
nano config.json

# Запустить систему
sudo systemctl start mediamtx
sudo systemctl start rascam

# Включить автозапуск
sudo systemctl enable mediamtx
sudo systemctl enable rascam
```

### Ручная установка

```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y

# Установить зависимости
sudo apt install -y python3-picamera2 python3-opencv \
    python3-numpy libcamera-apps ffmpeg

# Установить Python пакеты
pip3 install Flask psutil av

# Установить MediaMTX
wget https://github.com/bluenviron/mediamtx/releases/download/v1.8.5/mediamtx_v1.8.5_linux_arm64v8.tar.gz
tar -xzf mediamtx_v1.8.5_linux_arm64v8.tar.gz
sudo mv mediamtx /usr/local/bin/
```

## Настройка

### 1. Конфигурация системы

Отредактируйте `/boot/config.txt`:

```ini
gpu_mem=128
camera_auto_detect=1
dtoverlay=vc4-kms-v3d
```

### 2. Монтирование USB SSD

```bash
# Узнать UUID диска
sudo blkid

# Добавить в /etc/fstab
UUID=ваш-uuid /media/usb_ssd ext4 defaults,nofail 0 2

# Смонтировать
sudo mount -a
```

### 3. Настройка MediaMTX

Отредактируйте `/etc/mediamtx/mediamtx.yml`:

```yaml
paths:
  cam1:
    source: publisher
    publishUser: admin
    publishPass: ваш_пароль  # Измените!
    readUser: viewer
    readPass: ваш_пароль     # Измените!
```

### 4. Конфигурация RasCam

Отредактируйте `config.json`:

```json
{
  "camera": {
    "main_resolution": [1920, 1080],
    "framerate": 15
  },
  "recording": {
    "storage_path": "/media/usb_ssd/recordings",
    "retention_days": 30
  },
  "streaming": {
    "username": "admin",
    "password": "changeme"  // Измените!
  }
}
```

## Использование

### Запуск

```bash
# Вручную (для тестирования)
python3 surveillance.py

# Через systemd
sudo systemctl start rascam
sudo systemctl status rascam

# Логи
sudo journalctl -u rascam -f
```

### Веб-интерфейс

Откройте в браузере: `http://IP_адрес_Pi:5000`

Функции:
- Просмотр статуса системы
- Мониторинг температуры
- Список и воспроизведение записей
- Настройка зон детекции
- Статистика хранилища

### Просмотр RTSP стрима

**VLC Player:**
```
Media → Open Network Stream
rtsp://viewer:changeme@IP_адрес:8554/cam1
```

**FFplay:**
```bash
ffplay rtsp://viewer:changeme@IP_адрес:8554/cam1
```

**Python (OpenCV):**
```python
import cv2
cap = cv2.VideoCapture('rtsp://viewer:changeme@IP_адрес:8554/cam1')
```

## Управление зонами детекции

### Через веб-интерфейс
1. Откройте http://IP_адрес:5000
2. Раздел "Зоны детекции движения"
3. Нарисуйте прямоугольник на видео
4. Управляйте зонами (вкл/выкл/удалить)

### Через config.json
```json
{
  "motion_detection": {
    "threshold": 7.0,
    "zones": [
      {
        "name": "entrance",
        "enabled": true,
        "x": 50,
        "y": 50,
        "width": 220,
        "height": 140
      }
    ]
  }
}
```

## Мониторинг

### Проверка статуса

```bash
# Статус сервисов
sudo systemctl status rascam
sudo systemctl status mediamtx

# Температура
vcgencmd measure_temp

# Троттлинг
vcgencmd get_throttled

# Использование диска
df -h /media/usb_ssd
```

### Логи

```bash
# RasCam логи
tail -f logs/surveillance.log

# Systemd логи
sudo journalctl -u rascam -f

# Ошибки
sudo journalctl -u rascam -p err
```

## Оптимизация производительности

### Снижение нагрузки CPU

```json
{
  "camera": {
    "framerate": 10,  // Уменьшить с 15
    "main_resolution": [1280, 720]  // Вместо 1080p
  },
  "video": {
    "bitrate": 1500000  // Снизить битрейт
  }
}
```

### Управление температурой

Система автоматически снижает FPS при перегреве:
- 70-75°C: предупреждение
- 75-80°C: снижение FPS до 10
- 80°C+: минимальная нагрузка (FPS 5)

Рекомендуется активное охлаждение для стабильной работы.

## Устранение неполадок

### Камера не обнаружена

```bash
# Проверка камеры
libcamera-hello --list-cameras

# Если не видит
sudo raspi-config
# Interface Options → Legacy Camera → Disable

# Перезагрузка
sudo reboot
```

### Аппаратное кодирование не работает

```bash
# Проверка GPU memory
vcgencmd get_mem gpu

# Должно быть >= 128MB
# Если нет, добавить в /boot/config.txt:
gpu_mem=128
```

### Высокая нагрузка CPU

```bash
# Проверить 64-bit ОС
uname -m  # Должно быть: aarch64

# Проверить аппаратное кодирование
ps aux | grep picamera2

# Снизить FPS или разрешение в config.json
```

### Недостаток места на диске

```bash
# Проверка
df -h /media/usb_ssd

# Ручная очистка старых файлов
find /media/usb_ssd/recordings -name "*.mp4" -mtime +7 -delete

# Или уменьшить retention_days в config.json
```

## Архитектура

```
┌─────────────────────────────────────────────┐
│         surveillance.py (Main)              │
│                                             │
│  ┌──────────────┐  ┌──────────────┐        │
│  │camera_manager│  │motion_detector│       │
│  │  (picamera2) │  │  (MSE zones) │        │
│  └──────┬───────┘  └──────┬───────┘        │
│         │                 │                 │
│         └────────┬────────┘                 │
│                  │                          │
│         ┌────────▼────────┐                 │
│         │    recorder     │                 │
│         │  (MP4 files)    │                 │
│         └────────┬────────┘                 │
│                  │                          │
│  ┌───────────────▼──────────────┐           │
│  │    thermal_monitor           │           │
│  │  (temp control, throttling)  │           │
│  └──────────────────────────────┘           │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴───────┐
       │               │
   ┌───▼────┐    ┌─────▼─────┐
   │MediaMTX│    │   Flask   │
   │ (RTSP) │    │(Web UI)   │
   └────────┘    └───────────┘
```

## Компоненты

- **camera_manager.py** - захват видео с dual-stream (main + lores)
- **motion_detector.py** - детекция движения с зонами
- **recorder.py** - управление записями и хранилищем
- **thermal_monitor.py** - мониторинг температуры
- **surveillance.py** - главный координатор
- **web_interface/app.py** - Flask веб-сервер

## Безопасность

### Базовая защита (локальная сеть)

1. Измените пароли в config.json и mediamtx.yml
2. Используйте сильные пароли (12+ символов)
3. Регулярно обновляйте систему

### Дополнительно (для удаленного доступа)

1. Настройте VPN (WireGuard)
2. Используйте firewall (ufw)
3. Отключите ненужные сервисы
4. Регулярно проверяйте логи

```bash
# Настройка firewall
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 5000/tcp    # Web UI (только локально!)
sudo ufw enable
```

## Производительность

Типичные показатели на Raspberry Pi 4 (4GB):

| Режим | CPU | Температура | Память |
|-------|-----|-------------|--------|
| Idle (стрим) | 15-25% | 55-60°C | 600MB |
| Запись движения | 30-40% | 60-65°C | 700MB |
| Запись + стрим | 35-45% | 62-68°C | 800MB |

## Лицензия

MIT License

## Автор

RasCam Surveillance System

## Поддержка

Для вопросов и багов создайте Issue на GitHub.
