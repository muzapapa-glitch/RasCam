#!/usr/bin/env python3
"""
Примеры использования настройки чувствительности детектора движения RasCam
"""

import requests
import json


# Базовый URL веб-интерфейса RasCam
BASE_URL = "http://localhost:5000"


def get_current_sensitivity():
    """Получить текущую чувствительность"""
    response = requests.get(f"{BASE_URL}/api/motion/sensitivity")
    data = response.json()

    print("Текущая чувствительность:")
    print(f"  Уровень: {data['sensitivity']}")
    print(f"  Порог: {data['threshold']}")
    return data


def set_preset_sensitivity(level):
    """
    Установить предустановленный уровень чувствительности

    Args:
        level: 'low', 'medium', 'high', 'very_high'
    """
    response = requests.post(
        f"{BASE_URL}/api/motion/sensitivity",
        json={"sensitivity": level}
    )
    data = response.json()

    if data.get('success'):
        print(f"Чувствительность установлена на '{level}'")
        print(f"  Новый порог: {data['threshold']}")
    else:
        print(f"Ошибка: {data.get('error')}")

    return data


def set_custom_threshold(threshold):
    """
    Установить точное значение порога

    Args:
        threshold: float от 0 до 50
    """
    response = requests.post(
        f"{BASE_URL}/api/motion/threshold",
        json={"threshold": threshold}
    )
    data = response.json()

    if data.get('success'):
        print(f"Порог установлен на {threshold}")
        print(f"  Уровень: {data['sensitivity']}")
    else:
        print(f"Ошибка: {data.get('error')}")

    return data


def get_full_status():
    """Получить полный статус системы"""
    response = requests.get(f"{BASE_URL}/api/status")
    data = response.json()

    if 'motion' in data:
        print("\nСтатус детектора движения:")
        print(f"  Порог: {data['motion'].get('threshold')}")
        print(f"  Чувствительность: {data['motion'].get('sensitivity')}")
        print(f"  Зон детекции: {data['motion'].get('zones_count')}")
        print(f"  Активных зон: {data['motion'].get('zones_enabled')}")

    return data


def example_scenario_indoor():
    """Пример сценария настройки для помещения"""
    print("\n=== Сценарий: Настройка для помещения ===")

    # Начинаем со средней чувствительности
    print("\n1. Устанавливаем среднюю чувствительность...")
    set_preset_sensitivity('medium')

    # Проверяем результат
    print("\n2. Проверяем настройки...")
    get_current_sensitivity()


def example_scenario_outdoor():
    """Пример сценария настройки для улицы"""
    print("\n=== Сценарий: Настройка для улицы ===")

    # Для улицы обычно нужна пониженная чувствительность
    print("\n1. Устанавливаем низкую чувствительность...")
    set_preset_sensitivity('low')

    # Или устанавливаем точное значение
    print("\n2. Точная настройка порога на 12...")
    set_custom_threshold(12.0)


def example_scenario_night():
    """Пример сценария настройки для ночной съемки"""
    print("\n=== Сценарий: Настройка для ночной съемки ===")

    # Ночью из-за шума матрицы нужна пониженная чувствительность
    print("\n1. Устанавливаем порог 12 для ночи...")
    set_custom_threshold(12.0)


def example_scenario_testing():
    """Пример тестирования разных уровней"""
    print("\n=== Сценарий: Тестирование уровней чувствительности ===")

    levels = ['low', 'medium', 'high', 'very_high']

    for level in levels:
        print(f"\nТестируем уровень '{level}'...")
        set_preset_sensitivity(level)
        input(f"Понаблюдайте за работой детектора на уровне '{level}'. Нажмите Enter для продолжения...")


def example_gradual_adjustment():
    """Пример постепенной подстройки чувствительности"""
    print("\n=== Сценарий: Постепенная подстройка ===")

    # Начинаем с текущего значения
    current = get_current_sensitivity()
    current_threshold = current['threshold']

    print(f"\nТекущий порог: {current_threshold}")

    # Увеличиваем на 2
    new_threshold = current_threshold + 2.0
    print(f"\nУвеличиваем порог до {new_threshold} (понижаем чувствительность)...")
    set_custom_threshold(new_threshold)

    input("\nПонаблюдайте за работой. Нажмите Enter для возврата...")

    # Возвращаем обратно
    print(f"\nВозвращаем порог обратно на {current_threshold}...")
    set_custom_threshold(current_threshold)


def example_monitoring():
    """Пример мониторинга состояния детектора"""
    print("\n=== Мониторинг детектора движения ===")

    import time

    print("\nМониторинг на 30 секунд (обновление каждые 5 сек)...")

    for i in range(6):
        status = get_full_status()

        if i < 5:
            time.sleep(5)


if __name__ == "__main__":
    print("RasCam - Примеры настройки чувствительности детектора движения")
    print("=" * 70)

    # Показываем текущее состояние
    print("\n1. Получаем текущую чувствительность...")
    get_current_sensitivity()

    # Выбор примера
    print("\n\nВыберите пример для запуска:")
    print("1. Настройка для помещения")
    print("2. Настройка для улицы")
    print("3. Настройка для ночной съемки")
    print("4. Тестирование всех уровней")
    print("5. Постепенная подстройка")
    print("6. Мониторинг состояния")
    print("7. Установить высокую чувствительность")
    print("8. Установить среднюю чувствительность")
    print("9. Установить низкую чувствительность")
    print("0. Выход")

    choice = input("\nВаш выбор: ").strip()

    if choice == '1':
        example_scenario_indoor()
    elif choice == '2':
        example_scenario_outdoor()
    elif choice == '3':
        example_scenario_night()
    elif choice == '4':
        example_scenario_testing()
    elif choice == '5':
        example_gradual_adjustment()
    elif choice == '6':
        example_monitoring()
    elif choice == '7':
        set_preset_sensitivity('high')
    elif choice == '8':
        set_preset_sensitivity('medium')
    elif choice == '9':
        set_preset_sensitivity('low')
    elif choice == '0':
        print("\nВыход.")
    else:
        print("\nНеверный выбор")

    # Показываем финальное состояние
    print("\n\nФинальное состояние:")
    get_current_sensitivity()
