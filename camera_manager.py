#!/usr/bin/env python3
"""
Camera Manager для Raspberry Pi Camera Module 3
Использует picamera2 для dual-stream захвата с аппаратным H.264 кодированием
"""

import logging
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, Quality
from picamera2.outputs import CircularOutput, FileOutput
from libcamera import Transform
import time

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, config):
        self.config = config
        self.picam2 = None
        self.encoder = None
        self.circular_output = None
        self.current_output = None
        self.current_file = None

    def initialize(self):
        """Инициализация камеры с dual-stream конфигурацией"""
        try:
            logger.info("Инициализация Camera Module 3...")
            self.picam2 = Picamera2()

            # Настройка трансформации (поворот, отражение)
            transform = Transform(
                hflip=self.config['camera'].get('hflip', False),
                vflip=self.config['camera'].get('vflip', False)
            )

            # Dual stream: main для записи, lores для детекции движения
            video_config = self.picam2.create_video_configuration(
                main={
                    "size": tuple(self.config['camera']['main_resolution']),
                    "format": "YUV420"
                },
                lores={
                    "size": tuple(self.config['camera']['lores_resolution']),
                    "format": "YUV420"
                },
                transform=transform,
                encode="main",
                buffer_count=6
            )

            self.picam2.configure(video_config)

            # Настройка H.264 энкодера (аппаратное ускорение через GPU)
            bitrate = self.config['video']['bitrate']
            self.encoder = H264Encoder(bitrate=bitrate)

            # Циркулярный буфер для предзаписи
            pre_record_seconds = self.config['recording']['pre_record_seconds']
            buffer_size = int((bitrate * pre_record_seconds) / 8)
            self.circular_output = CircularOutput(buffersize=buffer_size)

            logger.info(f"Камера настроена: {self.config['camera']['main_resolution']} @ {self.config['camera']['framerate']}fps")
            logger.info(f"Циркулярный буфер: {pre_record_seconds}s ({buffer_size / 1024 / 1024:.1f} MB)")

        except Exception as e:
            logger.error(f"Ошибка инициализации камеры: {e}")
            raise

    def start(self):
        """Запуск захвата видео"""
        try:
            if self.picam2 is None:
                raise RuntimeError("Камера не инициализирована")

            logger.info("Запуск камеры...")
            self.picam2.start()
            time.sleep(2)  # Дать время на автонастройку экспозиции/баланса белого

            # Запуск энкодера с циркулярным буфером
            self.encoder.output = self.circular_output
            self.picam2.start_encoder(self.encoder)

            logger.info("Камера запущена, захват видео активен")

        except Exception as e:
            logger.error(f"Ошибка запуска камеры: {e}")
            raise

    def get_lores_frame(self):
        """Получить кадр низкого разрешения для детекции движения"""
        try:
            metadata = self.picam2.capture_metadata()
            frame = self.picam2.capture_buffer("lores")
            return frame, metadata
        except Exception as e:
            logger.error(f"Ошибка захвата lores кадра: {e}")
            return None, None

    def start_recording(self, filename):
        """Начать запись в файл"""
        try:
            logger.info(f"Начало записи: {filename}")

            # Используем FfmpegOutput для надёжной записи
            from picamera2.outputs import FfmpegOutput
            self.current_output = FfmpegOutput(filename)

            # Остановить энкодер, сменить output, запустить снова
            self.picam2.stop_encoder()
            self.encoder.output = self.current_output
            self.picam2.start_encoder(self.encoder)

            return True

        except Exception as e:
            logger.error(f"Ошибка начала записи: {e}")
            return False

    def stop_recording(self):
        """Остановить текущую запись"""
        try:
            if self.current_output:
                logger.info("Остановка записи")

                # Остановить энкодер, сменить output обратно, запустить снова
                self.picam2.stop_encoder()
                self.current_output = None
                self.encoder.output = self.circular_output
                self.picam2.start_encoder(self.encoder)

                return True
            return False

        except Exception as e:
            logger.error(f"Ошибка остановки записи: {e}")
            return False

    def is_recording(self):
        """Проверка, идёт ли сейчас запись"""
        return self.current_output is not None

    def adjust_framerate(self, new_fps):
        """Динамическая настройка FPS (для thermal throttling)"""
        try:
            logger.info(f"Изменение FPS: {new_fps}")
            controls = {"FrameRate": new_fps}
            self.picam2.set_controls(controls)
            return True
        except Exception as e:
            logger.error(f"Ошибка изменения FPS: {e}")
            return False

    def get_camera_info(self):
        """Получить информацию о камере"""
        if self.picam2:
            return {
                "model": self.picam2.camera_properties.get('Model', 'Unknown'),
                "resolution": self.config['camera']['main_resolution'],
                "framerate": self.config['camera']['framerate'],
                "is_recording": self.is_recording()
            }
        return None

    def stop(self):
        """Остановка камеры и освобождение ресурсов"""
        try:
            logger.info("Остановка камеры...")

            if self.is_recording():
                self.stop_recording()

            if self.encoder:
                self.picam2.stop_encoder()

            if self.picam2:
                self.picam2.stop()
                self.picam2.close()

            logger.info("Камера остановлена")

        except Exception as e:
            logger.error(f"Ошибка при остановке камеры: {e}")
