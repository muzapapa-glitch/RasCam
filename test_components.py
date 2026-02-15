#!/usr/bin/env python3
"""
Тестовый скрипт для проверки компонентов RasCam без камеры
Полезно для проверки логики перед развертыванием на Pi
"""

import json
import sys
import tempfile
from pathlib import Path

print("=" * 60)
print("RasCam Components Test (без камеры)")
print("=" * 60)
print()

# Загрузка конфигурации
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    print("✓ Конфигурация загружена")
except Exception as e:
    print(f"✗ Ошибка загрузки конфигурации: {e}")
    sys.exit(1)

# Тест MotionDetector
print("\n[1/4] Тестирование MotionDetector...")
try:
    from motion_detector import MotionDetector
    import numpy as np

    detector = MotionDetector(config)
    print(f"  ✓ Инициализация: threshold={detector.threshold}")
    print(f"  ✓ Зон: {len(detector.zones)}")

    # Симуляция кадров
    fake_frame = np.random.randint(0, 255, (240 * 320,), dtype=np.uint8)
    motion, details = detector.process_frame(fake_frame)
    print(f"  ✓ Обработка кадра: motion={motion}")

    # Добавление зоны
    success = detector.add_zone("test_zone", 50, 50, 100, 100)
    print(f"  ✓ Добавление зоны: {success}")

except Exception as e:
    print(f"  ✗ Ошибка: {e}")

# Тест RecordingManager
print("\n[2/4] Тестирование RecordingManager...")
try:
    from recorder import RecordingManager

    # Используем временную директорию
    temp_dir = tempfile.mkdtemp()
    test_config = config.copy()
    test_config['recording']['storage_path'] = temp_dir

    recorder = RecordingManager(test_config)
    print(f"  ✓ Инициализация")
    print(f"  ✓ Хранилище: {temp_dir}")

    # Тест генерации имени файла
    filename = recorder.generate_filename("test")
    print(f"  ✓ Генерация имени: {Path(filename).name}")

    # Тест статистики
    stats = recorder.get_stats()
    print(f"  ✓ Статистика: {stats['total_recordings']} записей")

    # Тест проверки хранилища
    storage = recorder.check_storage_space()
    print(f"  ✓ Проверка места: {storage.get('free_gb', 0)}GB свободно")

except Exception as e:
    print(f"  ✗ Ошибка: {e}")

# Тест ThermalMonitor
print("\n[3/4] Тестирование ThermalMonitor...")
try:
    from thermal_monitor import ThermalMonitor

    monitor = ThermalMonitor(config)
    print(f"  ✓ Инициализация")
    print(f"  ✓ Пороги: {monitor.temp_warning}°C / {monitor.temp_throttle}°C / {monitor.temp_critical}°C")

    # Тест получения температуры (может не работать на не-Pi системах)
    temp = monitor.get_temperature()
    if temp > 0:
        print(f"  ✓ Температура: {temp}°C")
    else:
        print(f"  ⚠ Температура недоступна (нормально на не-Pi системе)")

    # Тест анализа
    state = monitor.analyze_temperature(60.0)
    print(f"  ✓ Анализ 60°C: {state}")

    state = monitor.analyze_temperature(80.0)
    print(f"  ✓ Анализ 80°C: {state}")

    # Тест статуса
    status = monitor.get_status()
    print(f"  ✓ Статус: throttled={status['is_throttled']}")

except Exception as e:
    print(f"  ✗ Ошибка: {e}")

# Тест веб-интерфейса
print("\n[4/4] Тестирование Web Interface...")
try:
    from web_interface.app import app

    print(f"  ✓ Flask приложение импортировано")
    print(f"  ✓ Routes:")

    for rule in app.url_map.iter_rules():
        if not rule.endpoint.startswith('static'):
            print(f"    - {rule.endpoint}: {rule.rule}")

except Exception as e:
    print(f"  ✗ Ошибка: {e}")

print("\n" + "=" * 60)
print("Тестирование завершено")
print("=" * 60)
print()
print("Примечание: для полного теста требуется:")
print("  - Raspberry Pi 4")
print("  - Camera Module 3")
print("  - Установленный libcamera")
print()
print("Для запуска на Pi:")
print("  python3 surveillance.py")
