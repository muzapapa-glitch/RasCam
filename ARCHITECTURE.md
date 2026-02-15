# RasCam - Архитектура системы

## Обзор

RasCam - модульная система видеонаблюдения, оптимизированная для Raspberry Pi 4 + Camera Module 3.

## Компоненты

### 1. CameraManager (`camera_manager.py`)

**Функции:**
- Dual-stream захват (main 1080p + lores 320x240)
- Аппаратное H.264 кодирование через GPU
- Циркулярный буфер для предзаписи
- Управление FPS для thermal throttling

**API:**
```python
camera = CameraManager(config)
camera.initialize()
camera.start()
frame, metadata = camera.get_lores_frame()
camera.start_recording(filename)
camera.stop_recording()
camera.adjust_framerate(fps)
```

**Зависимости:** picamera2, libcamera

### 2. MotionDetector (`motion_detector.py`)

**Функции:**
- MSE (Mean Squared Error) алгоритм
- Множественные зоны детекции
- Фильтрация ложных срабатываний
- Динамическая настройка порога

**API:**
```python
detector = MotionDetector(config)
motion_detected, details = detector.process_frame(frame_buffer)
detector.add_zone(name, x, y, width, height)
detector.enable_zone(name, enabled)
detector.update_threshold(value)
```

**Алгоритм:**
1. Получить Y-канал из YUV420 (lores 320x240)
2. Для каждой активной зоны:
   - Извлечь регион
   - Вычислить MSE с предыдущим кадром
   - Сравнить с порогом
3. Требовать N последовательных кадров для триггера

**Производительность:** ~5-10% CPU, <10ms на кадр

### 3. RecordingManager (`recorder.py`)

**Функции:**
- Управление записями (старт/стоп)
- Автоматическая ротация файлов
- Очистка по retention policy
- Контроль дискового пространства

**API:**
```python
recorder = RecordingManager(config)
if recorder.should_start_recording(motion_detected):
    filename = recorder.start_recording()

if recorder.should_stop_recording(motion_detected, fps):
    recorder.stop_recording()

recordings = recorder.get_recordings_list()
recorder.cleanup_old_recordings()
```

**Логика записи:**
- Начало: детекция движения
- Продолжение: движение или post_record_seconds
- Остановка: нет движения N секунд
- Сегментация: каждые segment_duration секунд

### 4. ThermalMonitor (`thermal_monitor.py`)

**Функции:**
- Мониторинг температуры CPU
- Определение троттлинга системы
- Автоматическое управление нагрузкой
- История температур

**API:**
```python
monitor = ThermalMonitor(config)
monitor.set_callbacks(
    on_throttle=lambda temp: camera.adjust_framerate(10),
    on_critical=lambda temp: camera.adjust_framerate(5),
    on_normal=lambda temp: camera.adjust_framerate(15)
)
monitor.start()
status = monitor.get_status()
```

**Пороги:**
- 70°C: предупреждение
- 75°C: снижение FPS
- 80°C: критическое снижение нагрузки

**Мониторинг:** фоновый поток, проверка каждые 10 сек

### 5. SurveillanceSystem (`surveillance.py`)

**Функции:**
- Координация всех компонентов
- Главный цикл обработки
- Graceful shutdown
- Интеграция веб-интерфейса

**Главный цикл:**
```python
while running:
    # 1. Захват lores кадра
    frame, metadata = camera.get_lores_frame()

    # 2. Детекция движения
    motion, details = motion_detector.process_frame(frame)

    # 3. Управление записью
    if recorder.should_start_recording(motion):
        filename = recorder.start_recording()
        camera.start_recording(filename)

    if recorder.should_stop_recording(motion, fps):
        camera.stop_recording()
        recorder.stop_recording()

    # 4. Периодическая очистка
    if frame_count % cleanup_interval == 0:
        recorder.cleanup_old_recordings()
```

### 6. WebInterface (`web_interface/app.py`)

**Функции:**
- REST API для статуса системы
- Управление зонами детекции
- Просмотр/удаление записей
- Графики температуры

**Endpoints:**
- `GET /` - главная страница
- `GET /api/status` - статус системы
- `GET /api/recordings` - список записей
- `GET /api/recording/<filename>` - скачать запись
- `DELETE /api/recording/<filename>` - удалить запись
- `GET /api/zones` - получить зоны
- `POST /api/zones` - добавить зону
- `DELETE /api/zones/<name>` - удалить зону
- `POST /api/zones/<name>/toggle` - вкл/выкл зону
- `GET /api/thermal/history` - история температур

**Интеграция:**
Запускается в отдельном потоке через `threading.Thread`

## Поток данных

```
Camera Module 3
       ↓
   libcamera
       ↓
   picamera2 (dual stream)
       ├──────────────────┬──────────────────┐
       ↓                  ↓                  ↓
  Main Stream       Lores Stream      Metadata
  (1920x1080)        (320x240)
       ↓                  ↓
  H.264 Encoder    Motion Detector
  (GPU hardware)    (CPU software)
       ↓                  ↓
  Circular Buffer   Motion Decision
       ↓                  ↓
       └──────────┬───────┘
                  ↓
          Recording Manager
                  ↓
        ┌─────────┴─────────┐
        ↓                   ↓
   File Output         Statistics
   (MP4/H.264)          (Web API)
        ↓
   USB SSD Storage
```

## Многопоточность

```
Main Thread:
  - Главный цикл
  - Захват кадров
  - Детекция движения
  - Управление записью

Thermal Monitor Thread:
  - Периодическая проверка температуры
  - Коллбэки при изменении состояния

Web Server Thread:
  - Flask приложение
  - REST API
  - Статические файлы
```

## Управление памятью

**Циркулярный буфер:**
```
Размер = (bitrate * pre_record_seconds) / 8
Пример: (2500000 * 5) / 8 = 1.5 MB
```

**Общее использование памяти:**
- picamera2 buffers: ~100 MB
- Циркулярный буфер: ~200-500 MB
- Motion detector: ~50 MB
- Flask: ~50 MB
- Система: ~300 MB
- **Итого: ~600-800 MB**

## Файловая система

```
RasCam/
├── camera_manager.py       # Захват видео
├── motion_detector.py      # Детекция движения
├── recorder.py             # Управление записями
├── thermal_monitor.py      # Мониторинг температуры
├── surveillance.py         # Главный скрипт
├── config.json             # Конфигурация (не в git)
├── config.example.json     # Пример конфигурации
├── requirements.txt        # Python зависимости
├── install.sh              # Скрипт установки
├── check_system.sh         # Проверка системы
├── mediamtx.yml            # Конфигурация RTSP
├── README.md               # Документация
├── QUICKSTART.md           # Быстрый старт
├── ARCHITECTURE.md         # Этот файл
├── .gitignore              # Git исключения
├── logs/                   # Логи
│   └── surveillance.log
├── recordings/             # Локальные записи (или USB SSD)
│   └── YYYYMMDD_HHMMSS_motion_cam1.mp4
└── web_interface/
    ├── app.py              # Flask приложение
    ├── templates/
    │   └── index.html      # Веб-интерфейс
    └── static/
        ├── css/
        └── js/
```

## Конфигурация

Все параметры в `config.json`:

```json
{
  "camera": {
    "main_resolution": [1920, 1080],
    "framerate": 15
  },
  "motion_detection": {
    "threshold": 7.0,
    "zones": [...]
  },
  "recording": {
    "storage_path": "/media/usb_ssd/recordings",
    "retention_days": 30
  },
  "thermal": {
    "temp_throttle": 75
  }
}
```

## Производительность

### Профиль нагрузки

| Компонент | CPU | GPU | RAM |
|-----------|-----|-----|-----|
| picamera2 capture | 5-8% | Low | 100MB |
| H.264 encoding | 3-5% | High | 128MB |
| Motion detection | 5-10% | - | 50MB |
| Recording manager | 2-5% | - | 20MB |
| Thermal monitor | <1% | - | 10MB |
| Flask web | 2-5% | - | 50MB |
| Система | 5-10% | - | 300MB |

**Итого:** 25-45% CPU, ~600-800MB RAM

### Оптимизация

**Для снижения CPU:**
- Уменьшить FPS: 15 → 10
- Снизить разрешение: 1080p → 720p
- Увеличить min_frames: 3 → 5
- Уменьшить lores resolution: 320x240 → 160x120

**Для снижения использования диска:**
- Снизить bitrate: 2.5Mbps → 1.5Mbps
- Уменьшить retention_days: 30 → 14
- Увеличить threshold: 7.0 → 10.0

## Безопасность

### Локальная сеть
- Базовая HTTP аутентификация для RTSP
- Username/Password в config.json
- Без шифрования (WiFi WPA2/WPA3 достаточно)

### Удаленный доступ (если нужен)
- VPN (WireGuard) обязательно
- Firewall (ufw)
- Fail2ban для SSH
- Регулярные обновления

## Расширение системы

### Добавление новой камеры

1. Дублировать CameraManager
2. Добавить path в mediamtx.yml
3. Запустить отдельный процесс surveillance.py

### Интеграция с Home Assistant

```yaml
camera:
  - platform: generic
    still_image_url: http://PI_IP:8554/cam1/snapshot
    stream_source: rtsp://viewer:password@PI_IP:8554/cam1
```

### Уведомления при движении

Добавить в `motion_detector.py`:
```python
def send_notification(self):
    # Telegram, Email, Push notification
    pass
```

## Troubleshooting

### High CPU
1. Проверить аппаратное кодирование: `ps aux | grep picamera2`
2. Проверить 64-bit ОС: `uname -m` → aarch64
3. Снизить FPS или разрешение

### Перегрев
1. Добавить активное охлаждение
2. Снизить `temp_throttle` порог
3. Уменьшить нагрузку (FPS, разрешение)

### Камера не работает
1. `libcamera-hello --list-cameras`
2. Проверить gpu_mem >= 128
3. Отключить legacy camera в raspi-config

### Запись не срабатывает
1. Проверить логи: `journalctl -u rascam -n 50`
2. Снизить threshold: 7.0 → 5.0
3. Увеличить зону детекции

## Версионирование

- Python 3.11+
- picamera2 0.3.12+
- Raspberry Pi OS Bookworm 64-bit
- MediaMTX v1.8.0+

## Лицензия

MIT License - свободное использование и модификация.
