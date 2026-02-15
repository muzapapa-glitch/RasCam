#!/usr/bin/env python3
"""
Flask веб-интерфейс для RasCam
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file, Response

# Добавить родительскую директорию в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rascam-secret-key-change-in-production'

# Глобальная ссылка на систему (будет установлена при запуске)
surveillance_system = None


def set_surveillance_system(system):
    """Установить ссылку на систему наблюдения"""
    global surveillance_system
    surveillance_system = system


@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """API: получить статус системы"""
    if surveillance_system is None:
        return jsonify({'error': 'System not initialized'}), 500

    try:
        status = surveillance_system.get_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recordings')
def api_recordings():
    """API: список записей"""
    if surveillance_system is None or surveillance_system.recorder is None:
        return jsonify({'error': 'Recorder not initialized'}), 500

    try:
        recordings = surveillance_system.recorder.get_recordings_list()
        # Конвертация datetime в строки для JSON
        for rec in recordings:
            rec['created'] = rec['created'].isoformat()
            rec['modified'] = rec['modified'].isoformat()

        return jsonify(recordings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recording/<filename>')
def api_get_recording(filename):
    """API: скачать/воспроизвести запись"""
    if surveillance_system is None or surveillance_system.recorder is None:
        return jsonify({'error': 'Recorder not initialized'}), 500

    try:
        file_path = Path(surveillance_system.config['recording']['storage_path']) / filename

        if not file_path.exists() or file_path.suffix != '.mp4':
            return jsonify({'error': 'Recording not found'}), 404

        return send_file(file_path, mimetype='video/mp4')

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recording/<filename>', methods=['DELETE'])
def api_delete_recording(filename):
    """API: удалить запись"""
    if surveillance_system is None or surveillance_system.recorder is None:
        return jsonify({'error': 'Recorder not initialized'}), 500

    try:
        success = surveillance_system.recorder.delete_recording(filename)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to delete'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/thermal/history')
def api_thermal_history():
    """API: история температур"""
    if surveillance_system is None or surveillance_system.thermal_monitor is None:
        return jsonify({'error': 'Thermal monitor not initialized'}), 500

    try:
        minutes = request.args.get('minutes', 10, type=int)
        history = surveillance_system.thermal_monitor.get_temperature_history(minutes)
        return jsonify(history)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/zones')
def api_get_zones():
    """API: получить зоны детекции"""
    if surveillance_system is None or surveillance_system.motion_detector is None:
        return jsonify({'error': 'Motion detector not initialized'}), 500

    try:
        zones = [
            {
                'name': zone.name,
                'x': zone.x,
                'y': zone.y,
                'width': zone.width,
                'height': zone.height,
                'enabled': zone.enabled
            }
            for zone in surveillance_system.motion_detector.zones
        ]
        return jsonify(zones)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/zones', methods=['POST'])
def api_add_zone():
    """API: добавить зону детекции"""
    if surveillance_system is None or surveillance_system.motion_detector is None:
        return jsonify({'error': 'Motion detector not initialized'}), 500

    try:
        data = request.json
        success = surveillance_system.motion_detector.add_zone(
            name=data['name'],
            x=data['x'],
            y=data['y'],
            width=data['width'],
            height=data['height']
        )

        if success:
            # Сохранить в конфигурацию
            _save_zones_to_config()
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Invalid zone parameters'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/zones/<zone_name>', methods=['DELETE'])
def api_delete_zone(zone_name):
    """API: удалить зону детекции"""
    if surveillance_system is None or surveillance_system.motion_detector is None:
        return jsonify({'error': 'Motion detector not initialized'}), 500

    try:
        surveillance_system.motion_detector.remove_zone(zone_name)
        _save_zones_to_config()
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/zones/<zone_name>/toggle', methods=['POST'])
def api_toggle_zone(zone_name):
    """API: включить/выключить зону"""
    if surveillance_system is None or surveillance_system.motion_detector is None:
        return jsonify({'error': 'Motion detector not initialized'}), 500

    try:
        data = request.json
        enabled = data.get('enabled', True)
        success = surveillance_system.motion_detector.enable_zone(zone_name, enabled)

        if success:
            _save_zones_to_config()
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Zone not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config')
def api_get_config():
    """API: получить текущую конфигурацию"""
    if surveillance_system is None:
        return jsonify({'error': 'System not initialized'}), 500

    # Скрыть пароли
    config_copy = surveillance_system.config.copy()
    if 'streaming' in config_copy:
        config_copy['streaming']['password'] = '***'

    return jsonify(config_copy)


@app.route('/api/rtsp')
def api_get_rtsp():
    """API: получить RTSP URL для подключения"""
    if surveillance_system is None:
        return jsonify({'error': 'System not initialized'}), 500

    try:
        streaming_config = surveillance_system.config.get('streaming', {})

        # Получить IP адрес системы (реальный сетевой IP, не localhost)
        import socket
        local_ip = '0.0.0.0'

        try:
            # Создаём UDP соединение (не отправляем данные) чтобы узнать наш IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            # Fallback: пробуем получить IP через hostname
            try:
                local_ip = socket.gethostbyname(socket.gethostname())
                # Если получили localhost, пробуем найти другой интерфейс
                if local_ip.startswith('127.'):
                    # Получаем все IP адреса
                    hostname = socket.gethostname()
                    addrs = socket.getaddrinfo(hostname, None)
                    for addr in addrs:
                        ip = addr[4][0]
                        if not ip.startswith('127.') and ':' not in ip:  # IPv4, не localhost
                            local_ip = ip
                            break
            except Exception:
                local_ip = '0.0.0.0'

        # Сформировать RTSP URL
        username = streaming_config.get('username', 'admin')
        password = streaming_config.get('password', 'changeme')
        base_url = streaming_config.get('mediamtx_url', 'rtsp://localhost:8554/cam1')

        # Извлечь порт и путь из base_url
        if '://' in base_url:
            protocol, rest = base_url.split('://', 1)
            if '/' in rest:
                host_port, path = rest.split('/', 1)
                if ':' in host_port:
                    _, port = host_port.split(':', 1)
                else:
                    port = '8554'
                path = '/' + path
            else:
                port = '8554'
                path = '/cam1'
        else:
            port = '8554'
            path = '/cam1'

        # Сформировать полный URL с IP
        rtsp_url = f"rtsp://{username}:{password}@{local_ip}:{port}{path}"

        return jsonify({
            'rtsp_url': rtsp_url,
            'ip': local_ip,
            'port': port,
            'path': path,
            'username': username
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _save_zones_to_config():
    """Сохранить зоны в конфигурацию"""
    if surveillance_system is None:
        return

    zones_data = [
        {
            'name': zone.name,
            'x': zone.x,
            'y': zone.y,
            'width': zone.width,
            'height': zone.height,
            'enabled': zone.enabled
        }
        for zone in surveillance_system.motion_detector.zones
    ]

    surveillance_system.config['motion_detection']['zones'] = zones_data

    # Сохранить в файл
    with open('config.json', 'w') as f:
        json.dump(surveillance_system.config, f, indent=2)


def run_web_server(system, host='0.0.0.0', port=5000, debug=False):
    """Запустить веб-сервер"""
    set_surveillance_system(system)
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    print("Запускайте через surveillance.py, а не напрямую")
    sys.exit(1)
