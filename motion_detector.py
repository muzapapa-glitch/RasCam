#!/usr/bin/env python3
"""
Motion Detector с поддержкой зон детекции
Использует MSE (Mean Squared Error) алгоритм на low-resolution потоке
"""

import logging
import numpy as np
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class DetectionZone:
    """Зона детекции движения"""
    def __init__(self, name: str, x: int, y: int, width: int, height: int, enabled: bool = True):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.enabled = enabled
        self.prev_frame = None

    def extract_region(self, frame: np.ndarray) -> np.ndarray:
        """Извлечь регион из кадра"""
        return frame[self.y:self.y + self.height, self.x:self.x + self.width]

    def calculate_mse(self, current_region: np.ndarray) -> float:
        """Вычислить MSE между текущим и предыдущим кадром"""
        if self.prev_frame is None:
            self.prev_frame = current_region.copy()
            return 0.0

        # Mean Squared Error
        mse = np.square(np.subtract(current_region.astype(float),
                                     self.prev_frame.astype(float))).mean()

        self.prev_frame = current_region.copy()
        return mse

    def reset(self):
        """Сброс состояния зоны"""
        self.prev_frame = None


class MotionDetector:
    """Детектор движения с поддержкой множественных зон"""

    def __init__(self, config: Dict):
        self.config = config
        self.threshold = config['motion_detection']['threshold']
        self.min_frames = config['motion_detection']['min_frames']
        self.lores_size = tuple(config['camera']['lores_resolution'])

        # Счётчики для фильтрации ложных срабатываний
        self.motion_frame_count = 0
        self.no_motion_frame_count = 0

        # Зоны детекции
        self.zones: List[DetectionZone] = []
        self._load_zones()

        logger.info(f"Motion detector инициализирован: threshold={self.threshold}, zones={len(self.zones)}")

    def _load_zones(self):
        """Загрузка зон детекции из конфигурации"""
        zones_config = self.config['motion_detection'].get('zones', [])

        if not zones_config:
            # Зона по умолчанию - весь кадр
            zones_config = [{
                "name": "full_frame",
                "enabled": True,
                "x": 0,
                "y": 0,
                "width": self.lores_size[0],
                "height": self.lores_size[1]
            }]

        for zone_cfg in zones_config:
            if zone_cfg.get('enabled', True):
                zone = DetectionZone(
                    name=zone_cfg['name'],
                    x=zone_cfg['x'],
                    y=zone_cfg['y'],
                    width=zone_cfg['width'],
                    height=zone_cfg['height'],
                    enabled=zone_cfg.get('enabled', True)
                )
                self.zones.append(zone)
                logger.info(f"Зона '{zone.name}': ({zone.x},{zone.y}) {zone.width}x{zone.height}")

    def process_frame(self, frame_buffer) -> Tuple[bool, Dict]:
        """
        Обработать кадр и определить наличие движения

        Args:
            frame_buffer: YUV420 буфер из picamera2

        Returns:
            (motion_detected, details) где details содержит информацию о зонах
        """
        try:
            # Преобразовать буфер в numpy array (берём только Y-канал из YUV420)
            h, w = self.lores_size[1], self.lores_size[0]
            frame = np.frombuffer(frame_buffer, dtype=np.uint8, count=w * h)
            frame = frame.reshape((h, w))

            motion_detected = False
            zone_details = {}

            # Проверка каждой активной зоны
            for zone in self.zones:
                if not zone.enabled:
                    continue

                region = zone.extract_region(frame)
                mse = zone.calculate_mse(region)

                zone_motion = mse > self.threshold
                zone_details[zone.name] = {
                    'mse': round(mse, 2),
                    'motion': zone_motion
                }

                if zone_motion:
                    motion_detected = True

            # Фильтрация: требуется N последовательных кадров с движением
            if motion_detected:
                self.motion_frame_count += 1
                self.no_motion_frame_count = 0

                # Триггер только после min_frames подряд
                should_trigger = self.motion_frame_count >= self.min_frames
            else:
                self.motion_frame_count = 0
                self.no_motion_frame_count += 1
                should_trigger = False

            return should_trigger, zone_details

        except Exception as e:
            logger.error(f"Ошибка обработки кадра: {e}")
            return False, {}

    def get_motion_state(self) -> Dict:
        """Получить текущее состояние детектора"""
        return {
            'motion_frames': self.motion_frame_count,
            'no_motion_frames': self.no_motion_frame_count,
            'threshold': self.threshold,
            'sensitivity': self.get_sensitivity_level(),
            'zones_count': len(self.zones),
            'zones_enabled': sum(1 for z in self.zones if z.enabled)
        }

    def update_threshold(self, new_threshold: float):
        """Динамическое изменение порога чувствительности"""
        old_threshold = self.threshold
        self.threshold = new_threshold
        logger.info(f"Порог изменён: {old_threshold} -> {new_threshold}")

    def set_sensitivity(self, sensitivity: str):
        """
        Установить чувствительность по предустановленному уровню

        Args:
            sensitivity: 'low', 'medium', 'high', 'very_high'
        """
        sensitivity_map = {
            'low': 15.0,        # Только крупные объекты
            'medium': 7.0,      # Баланс между точностью и ложными срабатываниями
            'high': 4.0,        # Чувствительный к мелким движениям
            'very_high': 2.0    # Максимальная чувствительность
        }

        if sensitivity not in sensitivity_map:
            logger.error(f"Неизвестный уровень чувствительности: {sensitivity}")
            return False

        new_threshold = sensitivity_map[sensitivity]
        self.update_threshold(new_threshold)
        logger.info(f"Установлена чувствительность '{sensitivity}' (порог={new_threshold})")
        return True

    def get_sensitivity_level(self) -> str:
        """
        Получить текущий уровень чувствительности

        Returns:
            Строковое представление уровня чувствительности
        """
        if self.threshold >= 15.0:
            return 'low'
        elif self.threshold >= 7.0:
            return 'medium'
        elif self.threshold >= 4.0:
            return 'high'
        else:
            return 'very_high'

    def enable_zone(self, zone_name: str, enabled: bool = True):
        """Включить/выключить зону детекции"""
        for zone in self.zones:
            if zone.name == zone_name:
                zone.enabled = enabled
                logger.info(f"Зона '{zone_name}': {'включена' if enabled else 'выключена'}")
                return True
        return False

    def add_zone(self, name: str, x: int, y: int, width: int, height: int):
        """Добавить новую зону детекции"""
        # Проверка границ
        if x < 0 or y < 0 or x + width > self.lores_size[0] or y + height > self.lores_size[1]:
            logger.error(f"Зона '{name}' выходит за границы кадра")
            return False

        zone = DetectionZone(name, x, y, width, height, enabled=True)
        self.zones.append(zone)
        logger.info(f"Добавлена зона '{name}': ({x},{y}) {width}x{height}")
        return True

    def remove_zone(self, zone_name: str):
        """Удалить зону детекции"""
        self.zones = [z for z in self.zones if z.name != zone_name]
        logger.info(f"Зона '{zone_name}' удалена")

    def reset(self):
        """Сброс всех состояний детектора"""
        self.motion_frame_count = 0
        self.no_motion_frame_count = 0
        for zone in self.zones:
            zone.reset()
        logger.info("Motion detector сброшен")
