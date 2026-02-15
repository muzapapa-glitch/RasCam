#!/bin/bash
# Проверка системы перед запуском RasCam

echo "======================================"
echo "RasCam System Check"
echo "======================================"
echo

ERRORS=0
WARNINGS=0

# Цвета
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Проверка камеры
echo "[1/10] Проверка камеры..."
if libcamera-hello --list-cameras 2>/dev/null | grep -q "Available cameras"; then
    echo -e "${GREEN}✓${NC} Камера обнаружена"
else
    echo -e "${RED}✗${NC} Камера не обнаружена"
    ERRORS=$((ERRORS + 1))
fi

# Проверка GPU памяти
echo "[2/10] Проверка GPU памяти..."
GPU_MEM=$(vcgencmd get_mem gpu | cut -d'=' -f2 | cut -d'M' -f1)
if [ "$GPU_MEM" -ge 128 ]; then
    echo -e "${GREEN}✓${NC} GPU память: ${GPU_MEM}MB"
else
    echo -e "${YELLOW}⚠${NC} GPU память: ${GPU_MEM}MB (рекомендуется >= 128MB)"
    WARNINGS=$((WARNINGS + 1))
fi

# Проверка архитектуры
echo "[3/10] Проверка архитектуры..."
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
    echo -e "${GREEN}✓${NC} 64-bit ОС"
else
    echo -e "${YELLOW}⚠${NC} 32-bit ОС (рекомендуется 64-bit для лучшей производительности)"
    WARNINGS=$((WARNINGS + 1))
fi

# Проверка Python
echo "[4/10] Проверка Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"
else
    echo -e "${RED}✗${NC} Python 3 не найден"
    ERRORS=$((ERRORS + 1))
fi

# Проверка Python пакетов
echo "[5/10] Проверка Python пакетов..."
MISSING_PACKAGES=""

if ! python3 -c "import picamera2" 2>/dev/null; then
    MISSING_PACKAGES="$MISSING_PACKAGES picamera2"
fi

if ! python3 -c "import cv2" 2>/dev/null; then
    MISSING_PACKAGES="$MISSING_PACKAGES opencv"
fi

if ! python3 -c "import numpy" 2>/dev/null; then
    MISSING_PACKAGES="$MISSING_PACKAGES numpy"
fi

if ! python3 -c "import flask" 2>/dev/null; then
    MISSING_PACKAGES="$MISSING_PACKAGES flask"
fi

if [ -z "$MISSING_PACKAGES" ]; then
    echo -e "${GREEN}✓${NC} Все Python пакеты установлены"
else
    echo -e "${YELLOW}⚠${NC} Отсутствуют пакеты:$MISSING_PACKAGES"
    WARNINGS=$((WARNINGS + 1))
fi

# Проверка MediaMTX
echo "[6/10] Проверка MediaMTX..."
if command -v mediamtx &> /dev/null; then
    echo -e "${GREEN}✓${NC} MediaMTX установлен"
else
    echo -e "${YELLOW}⚠${NC} MediaMTX не найден"
    WARNINGS=$((WARNINGS + 1))
fi

# Проверка конфигурации
echo "[7/10] Проверка конфигурации..."
if [ -f "config.json" ]; then
    echo -e "${GREEN}✓${NC} config.json существует"

    # Проверка пароля
    if grep -q "changeme" config.json; then
        echo -e "${YELLOW}⚠${NC} Пароль по умолчанию не изменён!"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "${RED}✗${NC} config.json не найден"
    ERRORS=$((ERRORS + 1))
fi

# Проверка хранилища
echo "[8/10] Проверка хранилища..."
if [ -f "config.json" ]; then
    STORAGE_PATH=$(python3 -c "import json; print(json.load(open('config.json'))['recording']['storage_path'])" 2>/dev/null)

    if [ -d "$STORAGE_PATH" ]; then
        AVAILABLE=$(df -h "$STORAGE_PATH" | tail -1 | awk '{print $4}')
        echo -e "${GREEN}✓${NC} Хранилище доступно: $AVAILABLE свободно"
    else
        echo -e "${YELLOW}⚠${NC} Директория хранилища не существует: $STORAGE_PATH"
        echo "  Создать: sudo mkdir -p $STORAGE_PATH && sudo chown $USER:$USER $STORAGE_PATH"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

# Проверка температуры
echo "[9/10] Проверка температуры..."
TEMP=$(vcgencmd measure_temp | cut -d'=' -f2 | cut -d"'" -f1)
if (( $(echo "$TEMP < 70" | bc -l) )); then
    echo -e "${GREEN}✓${NC} Температура: ${TEMP}°C"
elif (( $(echo "$TEMP < 80" | bc -l) )); then
    echo -e "${YELLOW}⚠${NC} Температура повышена: ${TEMP}°C"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${RED}✗${NC} Температура критична: ${TEMP}°C"
    ERRORS=$((ERRORS + 1))
fi

# Проверка троттлинга
echo "[10/10] Проверка троттлинга..."
THROTTLED=$(vcgencmd get_throttled | cut -d'=' -f2)
if [ "$THROTTLED" = "0x0" ]; then
    echo -e "${GREEN}✓${NC} Троттлинг не обнаружен"
else
    echo -e "${YELLOW}⚠${NC} Обнаружен троттлинг: $THROTTLED"

    # Расшифровка
    THROTTLED_INT=$((THROTTLED))
    if (( THROTTLED_INT & 0x1 )); then
        echo "  - Недостаточное напряжение!"
    fi
    if (( THROTTLED_INT & 0x2 )); then
        echo "  - Частота ограничена"
    fi
    if (( THROTTLED_INT & 0x4 )); then
        echo "  - CPU троттлинг"
    fi
    if (( THROTTLED_INT & 0x8 )); then
        echo "  - Достигнут температурный лимит"
    fi

    WARNINGS=$((WARNINGS + 1))
fi

echo
echo "======================================"
echo "Итого:"
echo -e "${RED}Ошибок: $ERRORS${NC}"
echo -e "${YELLOW}Предупреждений: $WARNINGS${NC}"
echo "======================================"
echo

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}Обнаружены критические ошибки. Исправьте перед запуском.${NC}"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}Обнаружены предупреждения. Рекомендуется исправить.${NC}"
    exit 0
else
    echo -e "${GREEN}Все проверки пройдены! Система готова к запуску.${NC}"
    echo
    echo "Запуск:"
    echo "  sudo systemctl start mediamtx"
    echo "  sudo systemctl start rascam"
    exit 0
fi
