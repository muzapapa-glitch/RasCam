#!/usr/bin/env python3
"""
Thermal Monitor - мониторинг температуры и автоматическое управление нагрузкой
"""

import logging
import subprocess
import threading
import time
from typing import Dict, Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ThermalMonitor:
    """Монитор температуры CPU с автоматическим управлением"""

    def __init__(self, config: Dict):
        self.config = config
        self.check_interval = config['thermal']['check_interval']
        self.temp_warning = config['thermal']['temp_warning']
        self.temp_throttle = config['thermal']['temp_throttle']
        self.temp_critical = config['thermal']['temp_critical']
        self.throttle_reduce_fps = config['thermal']['throttle_reduce_fps']

        # Состояние
        self.current_temp = 0.0
        self.is_throttled = False
        self.throttle_state = {}
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Коллбэки для реакции на температуру
        self.on_warning: Optional[Callable] = None
        self.on_throttle: Optional[Callable] = None
        self.on_critical: Optional[Callable] = None
        self.on_normal: Optional[Callable] = None

        # История температур (последние 60 замеров)
        self.temp_history = []
        self.max_history = 60

    def get_temperature(self) -> float:
        """Получить текущую температуру CPU"""
        try:
            result = subprocess.run(
                ['vcgencmd', 'measure_temp'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Формат вывода: temp=62.3'C
                temp_str = result.stdout.strip()
                temp = float(temp_str.split('=')[1].split("'")[0])
                return temp
            else:
                logger.error(f"vcgencmd вернул ошибку: {result.stderr}")
                return 0.0

        except FileNotFoundError:
            # vcgencmd недоступен (не Raspberry Pi или не установлен)
            logger.warning("vcgencmd не найден, мониторинг температуры недоступен")
            return 0.0
        except Exception as e:
            logger.error(f"Ошибка получения температуры: {e}")
            return 0.0

    def get_throttled_status(self) -> Dict:
        """Проверить состояние троттлинга системы"""
        try:
            result = subprocess.run(
                ['vcgencmd', 'get_throttled'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Формат: throttled=0x0
                throttled_hex = result.stdout.strip().split('=')[1]
                throttled = int(throttled_hex, 16)

                return {
                    'undervoltage_now': bool(throttled & 0x1),
                    'freq_capped_now': bool(throttled & 0x2),
                    'throttled_now': bool(throttled & 0x4),
                    'soft_temp_limit': bool(throttled & 0x8),
                    'undervoltage_occurred': bool(throttled & 0x10000),
                    'freq_capped_occurred': bool(throttled & 0x20000),
                    'throttled_occurred': bool(throttled & 0x40000),
                    'soft_temp_limit_occurred': bool(throttled & 0x80000),
                    'raw': throttled_hex
                }
            return {}

        except Exception as e:
            logger.error(f"Ошибка получения throttled status: {e}")
            return {}

    def analyze_temperature(self, temp: float) -> str:
        """Анализ температуры и определение действий"""
        if temp >= self.temp_critical:
            return 'critical'
        elif temp >= self.temp_throttle:
            return 'throttle'
        elif temp >= self.temp_warning:
            return 'warning'
        else:
            return 'normal'

    def handle_thermal_state(self, state: str, temp: float):
        """Обработка теплового состояния"""
        if state == 'critical':
            if not self.is_throttled:
                logger.critical(f"КРИТИЧЕСКАЯ ТЕМПЕРАТУРА: {temp}°C - аварийное снижение нагрузки")
                self.is_throttled = True
                if self.on_critical:
                    self.on_critical(temp)

        elif state == 'throttle':
            if not self.is_throttled:
                logger.warning(f"Температура высокая: {temp}°C - снижение FPS")
                self.is_throttled = True
                if self.on_throttle:
                    self.on_throttle(temp)

        elif state == 'warning':
            logger.warning(f"Температура повышена: {temp}°C")
            if self.on_warning:
                self.on_warning(temp)

        else:  # normal
            if self.is_throttled:
                logger.info(f"Температура нормализована: {temp}°C - восстановление параметров")
                self.is_throttled = False
                if self.on_normal:
                    self.on_normal(temp)

    def monitor_loop(self):
        """Основной цикл мониторинга"""
        logger.info(f"Thermal monitor запущен (интервал: {self.check_interval}s)")

        while self.running:
            try:
                # Получить температуру
                self.current_temp = self.get_temperature()

                # Добавить в историю
                self.temp_history.append({
                    'timestamp': datetime.now(),
                    'temp': self.current_temp
                })
                if len(self.temp_history) > self.max_history:
                    self.temp_history.pop(0)

                # Получить состояние троттлинга
                self.throttle_state = self.get_throttled_status()

                # Предупреждения о проблемах питания
                if self.throttle_state.get('undervoltage_now'):
                    logger.error("⚡ НЕДОСТАТОЧНОЕ НАПРЯЖЕНИЕ! Проверьте блок питания")

                if self.throttle_state.get('throttled_now'):
                    logger.warning(f"⚠ Система в троттлинге (temp={self.current_temp}°C)")

                # Анализ и реакция на температуру
                if self.current_temp > 0:
                    state = self.analyze_temperature(self.current_temp)
                    self.handle_thermal_state(state, self.current_temp)

            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")

            # Ожидание следующей проверки
            time.sleep(self.check_interval)

        logger.info("Thermal monitor остановлен")

    def start(self):
        """Запустить мониторинг"""
        if self.running:
            logger.warning("Thermal monitor уже запущен")
            return

        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        """Остановить мониторинг"""
        logger.info("Остановка thermal monitor...")
        self.running = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

    def get_status(self) -> Dict:
        """Получить текущий статус"""
        avg_temp = 0.0
        if self.temp_history:
            avg_temp = sum(t['temp'] for t in self.temp_history) / len(self.temp_history)

        return {
            'current_temp': round(self.current_temp, 1),
            'average_temp': round(avg_temp, 1),
            'is_throttled': self.is_throttled,
            'throttle_state': self.throttle_state,
            'thresholds': {
                'warning': self.temp_warning,
                'throttle': self.temp_throttle,
                'critical': self.temp_critical
            },
            'history_size': len(self.temp_history)
        }

    def get_temperature_history(self, minutes: int = 10) -> list:
        """Получить историю температур за последние N минут"""
        if not self.temp_history:
            return []

        cutoff_time = datetime.now().timestamp() - (minutes * 60)
        return [
            {
                'timestamp': t['timestamp'].isoformat(),
                'temp': t['temp']
            }
            for t in self.temp_history
            if t['timestamp'].timestamp() >= cutoff_time
        ]

    def set_callbacks(self, on_warning=None, on_throttle=None, on_critical=None, on_normal=None):
        """Установить коллбэки для реакции на температурные события"""
        self.on_warning = on_warning
        self.on_throttle = on_throttle
        self.on_critical = on_critical
        self.on_normal = on_normal
