#!/usr/bin/env python3
"""
RasCam - Система видеонаблюдения для Raspberry Pi 4 + Camera Module 3
Главный скрипт координации всех модулей
"""

import json
import logging
import signal
import sys
import time
import threading
from pathlib import Path
from logging.handlers import RotatingFileHandler

from camera_manager import CameraManager
from motion_detector import MotionDetector
from recorder import RecordingManager
from thermal_monitor import ThermalMonitor


class SurveillanceSystem:
    """Главный класс системы видеонаблюдения"""

    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self._setup_logging()

        # Компоненты системы
        self.camera = None
        self.motion_detector = None
        self.recorder = None
        self.thermal_monitor = None

        # Состояние
        self.running = False
        self.original_fps = self.config['camera']['framerate']

        # Регистрация обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 60)
        self.logger.info("RasCam Surveillance System")
        self.logger.info("=" * 60)

    def _load_config(self, config_path: str) -> dict:
        """Загрузка конфигурации из JSON"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config
        except FileNotFoundError:
            print(f"Ошибка: файл конфигурации '{config_path}' не найден")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга конфигурации: {e}")
            sys.exit(1)

    def _setup_logging(self):
        """Настройка логирования"""
        log_config = self.config['logging']
        log_file = Path(log_config['file'])
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Уровень логирования
        level = getattr(logging, log_config['level'].upper(), logging.INFO)

        # Формат логов
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Ротация файлов логов
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=log_config['max_bytes'],
            backupCount=log_config['backup_count']
        )
        file_handler.setFormatter(formatter)

        # Вывод в консоль
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # Настройка root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    def _signal_handler(self, signum, frame):
        """Обработчик сигналов завершения"""
        self.logger.info(f"Получен сигнал {signum}, завершение работы...")
        self.stop()

    def initialize(self):
        """Инициализация всех компонентов"""
        try:
            self.logger.info("Инициализация компонентов...")

            # Камера
            self.logger.info("Инициализация камеры...")
            self.camera = CameraManager(self.config)
            self.camera.initialize()

            # Детектор движения
            self.logger.info("Инициализация детектора движения...")
            self.motion_detector = MotionDetector(self.config)

            # Менеджер записи
            self.logger.info("Инициализация менеджера записи...")
            self.recorder = RecordingManager(self.config)

            # Температурный монитор
            self.logger.info("Инициализация теплового монитора...")
            self.thermal_monitor = ThermalMonitor(self.config)

            # Настройка коллбэков для thermal monitor
            self.thermal_monitor.set_callbacks(
                on_throttle=self._on_thermal_throttle,
                on_critical=self._on_thermal_critical,
                on_normal=self._on_thermal_normal
            )

            # Веб-интерфейс (опционально)
            if self.config['web_interface']['enabled']:
                self.logger.info("Подготовка веб-интерфейса...")
                self.web_thread = None

            self.logger.info("Все компоненты инициализированы")

        except Exception as e:
            self.logger.error(f"Ошибка инициализации: {e}", exc_info=True)
            raise

    def _on_thermal_throttle(self, temp: float):
        """Реакция на повышенную температуру"""
        reduced_fps = self.config['thermal']['throttle_reduce_fps']
        self.logger.warning(f"Thermal throttle: снижение FPS до {reduced_fps}")
        self.camera.adjust_framerate(reduced_fps)

    def _on_thermal_critical(self, temp: float):
        """Реакция на критическую температуру"""
        self.logger.critical(f"Критическая температура {temp}°C - минимальная нагрузка")
        # Снижаем FPS до минимума
        self.camera.adjust_framerate(5)

    def _on_thermal_normal(self, temp: float):
        """Восстановление после нормализации температуры"""
        self.logger.info("Температура нормализована, восстановление FPS")
        self.camera.adjust_framerate(self.original_fps)

    def _start_web_interface(self):
        """Запуск веб-интерфейса в отдельном потоке"""
        try:
            from web_interface.app import run_web_server

            host = self.config['web_interface']['host']
            port = self.config['web_interface']['port']
            debug = self.config['web_interface']['debug']

            self.logger.info(f"Запуск веб-интерфейса на {host}:{port}")

            self.web_thread = threading.Thread(
                target=run_web_server,
                args=(self, host, port, debug),
                daemon=True
            )
            self.web_thread.start()

        except Exception as e:
            self.logger.error(f"Ошибка запуска веб-интерфейса: {e}")
            self.logger.warning("Продолжение без веб-интерфейса")

    def start(self):
        """Запуск системы наблюдения"""
        try:
            self.logger.info("Запуск системы...")
            self.running = True

            # Запуск камеры
            self.camera.start()

            # Запуск теплового монитора
            self.thermal_monitor.start()

            # Запуск веб-интерфейса в отдельном потоке
            if self.config['web_interface']['enabled']:
                self._start_web_interface()

            self.logger.info("Система запущена, начало мониторинга")
            self.logger.info(f"Разрешение: {self.config['camera']['main_resolution']}")
            self.logger.info(f"FPS: {self.config['camera']['framerate']}")
            self.logger.info(f"Хранилище: {self.config['recording']['storage_path']}")

            # Главный цикл обработки
            self.main_loop()

        except KeyboardInterrupt:
            self.logger.info("Получен Ctrl+C, завершение...")
            self.stop()
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}", exc_info=True)
            self.stop()
            sys.exit(1)

    def main_loop(self):
        """Главный цикл обработки кадров"""
        frame_count = 0
        cleanup_counter = 0
        cleanup_interval = 300  # Cleanup каждые 5 минут (300 секунд * FPS)

        while self.running:
            try:
                # Захват low-res кадра для детекции
                lores_frame, metadata = self.camera.get_lores_frame()

                if lores_frame is None:
                    time.sleep(0.01)
                    continue

                # Детекция движения
                motion_detected, zone_details = self.motion_detector.process_frame(lores_frame)

                # Логирование детекции
                if motion_detected:
                    self.logger.debug(f"Движение обнаружено: {zone_details}")

                # Управление записью
                if self.recorder.should_start_recording(motion_detected):
                    filename = self.recorder.start_recording()
                    self.camera.start_recording(filename)

                elif self.recorder.should_stop_recording(
                    motion_detected,
                    self.config['camera']['framerate']
                ):
                    self.camera.stop_recording()
                    self.recorder.stop_recording()

                    # Проверка хранилища после остановки записи
                    storage_info = self.recorder.check_storage_space()
                    self.logger.info(f"Хранилище: {storage_info.get('usage_percent', 0)}% "
                                   f"({storage_info.get('recordings_count', 0)} файлов)")

                # Периодическая очистка старых файлов
                frame_count += 1
                if frame_count % cleanup_interval == 0:
                    self.recorder.cleanup_old_recordings()

                # Небольшая задержка для снижения нагрузки CPU
                time.sleep(0.01)

            except Exception as e:
                self.logger.error(f"Ошибка в главном цикле: {e}", exc_info=True)
                time.sleep(1)

    def stop(self):
        """Остановка системы"""
        if not self.running:
            return

        self.logger.info("Остановка системы...")
        self.running = False

        # Остановка компонентов
        if self.thermal_monitor:
            self.thermal_monitor.stop()

        if self.camera:
            self.camera.stop()

        # Финальная статистика
        if self.recorder:
            stats = self.recorder.get_stats()
            self.logger.info(f"Всего записей: {stats.get('total_recordings', 0)}")

        if self.thermal_monitor:
            thermal_status = self.thermal_monitor.get_status()
            self.logger.info(f"Средняя температура: {thermal_status.get('average_temp', 0)}°C")

        self.logger.info("Система остановлена")
        sys.exit(0)

    def get_status(self) -> dict:
        """Получить полный статус системы"""
        return {
            'running': self.running,
            'camera': self.camera.get_camera_info() if self.camera else None,
            'motion': self.motion_detector.get_motion_state() if self.motion_detector else None,
            'recorder': self.recorder.get_stats() if self.recorder else None,
            'thermal': self.thermal_monitor.get_status() if self.thermal_monitor else None
        }


def main():
    """Точка входа"""
    print("RasCam Surveillance System v1.0")
    print("Нажмите Ctrl+C для остановки")
    print()

    # Проверка наличия конфигурации
    if not Path("config.json").exists():
        print("Ошибка: config.json не найден")
        print("Скопируйте config.example.json в config.json и настройте параметры")
        sys.exit(1)

    # Создание и запуск системы
    system = SurveillanceSystem()
    system.initialize()
    system.start()


if __name__ == "__main__":
    main()
