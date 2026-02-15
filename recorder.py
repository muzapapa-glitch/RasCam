#!/usr/bin/env python3
"""
Recording Manager - управление записями с автоматической ротацией
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import time

logger = logging.getLogger(__name__)


class RecordingManager:
    """Менеджер записей видео"""

    def __init__(self, config: Dict):
        self.config = config
        self.storage_path = Path(config['recording']['storage_path'])
        self.segment_duration = config['recording']['segment_duration']
        self.retention_days = config['recording']['retention_days']
        self.max_storage_gb = config['recording']['max_storage_gb']
        self.post_record_seconds = config['recording']['post_record_seconds']

        # Состояние записи
        self.is_recording = False
        self.current_filename = None
        self.recording_start_time = None
        self.last_motion_time = None
        self.frames_since_motion = 0

        # Статистика
        self.stats = {
            'total_recordings': 0,
            'total_size_mb': 0,
            'last_cleanup': None
        }

        self._ensure_storage_path()

    def _ensure_storage_path(self):
        """Создать директорию для хранения, если не существует"""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Директория записей: {self.storage_path}")
        except Exception as e:
            logger.error(f"Ошибка создания директории: {e}")
            raise

    def generate_filename(self, event_type: str = "motion") -> str:
        """Генерация имени файла с timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{event_type}_cam1.mp4"
        full_path = self.storage_path / filename
        return str(full_path)

    def should_start_recording(self, motion_detected: bool) -> bool:
        """Определить, нужно ли начинать запись"""
        if motion_detected and not self.is_recording:
            logger.info("Обнаружено движение, начало записи")
            return True
        return False

    def should_stop_recording(self, motion_detected: bool, framerate: int = 15) -> bool:
        """Определить, нужно ли остановить запись"""
        if not self.is_recording:
            return False

        # Проверка сегментации по времени
        if self.recording_start_time:
            duration = time.time() - self.recording_start_time
            if duration >= self.segment_duration:
                logger.info(f"Сегмент завершён ({duration:.1f}s), ротация файла")
                return True

        # Проверка post-record таймера
        if motion_detected:
            self.last_motion_time = time.time()
            self.frames_since_motion = 0
        else:
            self.frames_since_motion += 1
            frames_threshold = framerate * self.post_record_seconds

            if self.frames_since_motion >= frames_threshold:
                logger.info(f"Нет движения {self.post_record_seconds}s, остановка записи")
                return True

        return False

    def start_recording(self) -> str:
        """Начать новую запись"""
        self.current_filename = self.generate_filename("motion")
        self.recording_start_time = time.time()
        self.last_motion_time = time.time()
        self.frames_since_motion = 0
        self.is_recording = True
        self.stats['total_recordings'] += 1

        logger.info(f"Запись начата: {Path(self.current_filename).name}")
        return self.current_filename

    def stop_recording(self):
        """Остановить текущую запись"""
        if self.current_filename and os.path.exists(self.current_filename):
            file_size = os.path.getsize(self.current_filename) / (1024 * 1024)
            duration = time.time() - self.recording_start_time
            self.stats['total_size_mb'] += file_size

            logger.info(f"Запись остановлена: {Path(self.current_filename).name} "
                       f"({duration:.1f}s, {file_size:.1f}MB)")

        self.is_recording = False
        self.current_filename = None
        self.recording_start_time = None

    def get_recordings_list(self) -> List[Dict]:
        """Получить список всех записей"""
        recordings = []

        try:
            for file_path in sorted(self.storage_path.glob("*.mp4"), reverse=True):
                stat = file_path.stat()
                recordings.append({
                    'filename': file_path.name,
                    'path': str(file_path),
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'created': datetime.fromtimestamp(stat.st_ctime),
                    'modified': datetime.fromtimestamp(stat.st_mtime)
                })

        except Exception as e:
            logger.error(f"Ошибка получения списка записей: {e}")

        return recordings

    def cleanup_old_recordings(self):
        """Удаление старых записей по retention policy"""
        try:
            cutoff_time = datetime.now() - timedelta(days=self.retention_days)
            deleted_count = 0
            freed_mb = 0

            for file_path in self.storage_path.glob("*.mp4"):
                file_time = datetime.fromtimestamp(file_path.stat().st_ctime)

                if file_time < cutoff_time:
                    file_size = file_path.stat().st_size / (1024 * 1024)
                    file_path.unlink()
                    deleted_count += 1
                    freed_mb += file_size
                    logger.info(f"Удалён старый файл: {file_path.name}")

            if deleted_count > 0:
                logger.info(f"Cleanup: удалено {deleted_count} файлов, освобождено {freed_mb:.1f}MB")

            self.stats['last_cleanup'] = datetime.now()

        except Exception as e:
            logger.error(f"Ошибка очистки старых записей: {e}")

    def check_storage_space(self) -> Dict:
        """Проверка доступного места"""
        try:
            # Общий размер всех записей
            total_size = sum(f.stat().st_size for f in self.storage_path.glob("*.mp4"))
            total_gb = total_size / (1024 ** 3)

            # Доступное место на диске
            stat_vfs = os.statvfs(self.storage_path)
            free_gb = (stat_vfs.f_bavail * stat_vfs.f_frsize) / (1024 ** 3)

            usage_percent = (total_gb / self.max_storage_gb) * 100 if self.max_storage_gb > 0 else 0

            storage_info = {
                'total_gb': round(total_gb, 2),
                'free_gb': round(free_gb, 2),
                'max_gb': self.max_storage_gb,
                'usage_percent': round(usage_percent, 1),
                'recordings_count': len(list(self.storage_path.glob("*.mp4")))
            }

            # Предупреждение при малом свободном месте
            if free_gb < 5:
                logger.warning(f"Мало свободного места: {free_gb:.1f}GB")

            # Принудительная очистка при превышении лимита
            if total_gb > self.max_storage_gb * 0.9:
                logger.warning(f"Достигнут лимит хранилища ({usage_percent:.1f}%), запуск cleanup")
                self.cleanup_old_recordings()

            return storage_info

        except Exception as e:
            logger.error(f"Ошибка проверки хранилища: {e}")
            return {}

    def delete_recording(self, filename: str) -> bool:
        """Удалить конкретную запись"""
        try:
            file_path = self.storage_path / filename
            if file_path.exists() and file_path.suffix == '.mp4':
                file_path.unlink()
                logger.info(f"Запись удалена: {filename}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления записи {filename}: {e}")
            return False

    def get_stats(self) -> Dict:
        """Получить статистику записей"""
        storage_info = self.check_storage_space()

        return {
            'is_recording': self.is_recording,
            'current_filename': Path(self.current_filename).name if self.current_filename else None,
            'total_recordings': self.stats['total_recordings'],
            'storage': storage_info,
            'last_cleanup': self.stats['last_cleanup']
        }
