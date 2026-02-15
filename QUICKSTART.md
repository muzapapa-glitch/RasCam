# Быстрый старт RasCam

## Минимальная установка (5 минут)

### 1. Подготовка Raspberry Pi

```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y

# Установить git
sudo apt install git -y
```

### 2. Скачать и установить

```bash
# Клонировать репозиторий
cd ~
git clone https://github.com/muzapapa-glitch/RasCam.git
cd RasCam

# Запустить установку
sudo ./install.sh
```

### 3. Настройка

```bash
# Скопировать пример конфигурации
cp config.example.json config.json

# Отредактировать (минимум - изменить пароли)
nano config.json
```

**Обязательные изменения:**
- `streaming.password` - пароль для RTSP
- `recording.storage_path` - путь к хранилищу

### 4. Настройка MediaMTX

```bash
# Отредактировать пароли
sudo nano /etc/mediamtx/mediamtx.yml
```

Измените `publishPass` и `readPass`.

### 5. Запуск

```bash
# Запустить сервисы
sudo systemctl start mediamtx
sudo systemctl start rascam

# Проверить статус
sudo systemctl status rascam
```

### 6. Проверка работы

**Веб-интерфейс:**
```
http://IP_вашего_Pi:5000
```

**RTSP стрим (VLC):**
```
rtsp://viewer:ваш_пароль@IP_вашего_Pi:8554/cam1
```

**Логи:**
```bash
# В реальном времени
sudo journalctl -u rascam -f

# Последние 50 строк
sudo journalctl -u rascam -n 50
```

## Тестирование камеры

Перед установкой проверьте камеру:

```bash
# Проверка обнаружения
libcamera-hello --list-cameras

# Тестовый снимок
libcamera-still -o test.jpg

# Тестовое видео 10 сек
libcamera-vid -t 10000 -o test.h264
```

## Типичные проблемы

### Камера не обнаружена

```bash
# Проверить подключение
vcgencmd get_camera

# Включить камеру в raspi-config
sudo raspi-config
# Interface Options → Camera → Enable
sudo reboot
```

### Мало GPU памяти

```bash
# Добавить в /boot/config.txt
echo "gpu_mem=128" | sudo tee -a /boot/config.txt
sudo reboot
```

### Не хватает места на SD карте

Используйте USB SSD:

```bash
# Подключить USB SSD
# Узнать UUID
sudo blkid

# Добавить в /etc/fstab
UUID=ваш-uuid /media/usb_ssd ext4 defaults,nofail 0 2

# Смонтировать
sudo mkdir -p /media/usb_ssd
sudo mount -a

# Создать директорию для записей
sudo mkdir -p /media/usb_ssd/recordings
sudo chown $USER:$USER /media/usb_ssd/recordings
```

## Автозапуск

```bash
# Включить автозапуск при загрузке
sudo systemctl enable mediamtx
sudo systemctl enable rascam

# Проверить
sudo systemctl is-enabled rascam
```

## Остановка и перезапуск

```bash
# Остановить
sudo systemctl stop rascam

# Перезапустить
sudo systemctl restart rascam

# Отключить автозапуск
sudo systemctl disable rascam
```

## Просмотр записей

```bash
# Список записей
ls -lh /media/usb_ssd/recordings/

# Воспроизвести в VLC
vlc /media/usb_ssd/recordings/название_файла.mp4

# Или через веб-интерфейс
# http://IP_Pi:5000
```

## Мониторинг

### Температура

```bash
# Текущая температура
vcgencmd measure_temp

# Непрерывный мониторинг
watch -n 1 vcgencmd measure_temp
```

### Система

```bash
# CPU, память
htop

# Использование диска
df -h

# Нагрузка сети
iftop
```

## Оптимизация для слабого Pi

Если CPU перегружен, в `config.json`:

```json
{
  "camera": {
    "main_resolution": [1280, 720],
    "framerate": 10
  },
  "video": {
    "bitrate": 1500000
  }
}
```

## Полезные команды

```bash
# Перезагрузить Pi
sudo reboot

# Выключить Pi
sudo shutdown -h now

# Проверить версию ОС
cat /etc/os-release

# Проверить архитектуру (должно быть aarch64)
uname -m

# Статус всех сервисов
systemctl status
```

## Получение помощи

1. Проверьте логи: `sudo journalctl -u rascam -n 100`
2. Проверьте конфигурацию: `cat config.json`
3. Проверьте температуру: `vcgencmd measure_temp`
4. Создайте Issue на GitHub с логами

## Следующие шаги

После успешного запуска:

1. Настройте зоны детекции через веб-интерфейс
2. Протестируйте запись при движении
3. Настройте время хранения записей
4. Добавьте охлаждение если температура >70°C
5. Настройте резервное копирование на NAS (опционально)
