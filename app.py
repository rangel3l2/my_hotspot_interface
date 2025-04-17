from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit
import subprocess
import json
import os
import threading
import time
import platform

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

SYSTEM = platform.system().lower()

class HotspotManager:
    def __init__(self):
        self.commands = {
            'windows': {
                'start': 'netsh wlan start hostednetwork',
                'stop': 'netsh wlan stop hostednetwork',
                'setup': 'netsh wlan set hostednetwork mode=allow ssid=MeuHotspot key=12345678',
                'status': 'netsh wlan show hostednetwork',
                'list_devices': 'arp -a',
                'encoding': 'cp850'
            },
            'darwin': {  # macOS
                'start': 'networksetup -createnetworkservice MeuHotspot Wi-Fi && networksetup -setairportpower Wi-Fi on',
                'stop': 'networksetup -setairportpower Wi-Fi off',
                'setup': None,
                'status': '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I',
                'list_devices': 'arp -a',
                'encoding': 'utf-8'
            },
            'linux': {
                'start': 'nmcli device wifi hotspot ifname wlan0 ssid MeuHotspot password 12345678',
                'stop': 'nmcli device disconnect wlan0',
                'setup': None,
                'status': 'nmcli device show wlan0',
                'list_devices': 'arp -a',
                'encoding': 'utf-8'
            }
        }

    def execute_command(self, cmd_type):
        if SYSTEM not in self.commands:
            raise Exception(f"Sistema operacional {SYSTEM} não suportado")
        
        cmd = self.commands[SYSTEM][cmd_type]
        if not cmd:
            return True
            
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding=self.commands[SYSTEM]['encoding']
            )
            return result
        except Exception as e:
            print(f"Erro ao executar comando {cmd_type}: {e}")
            return None

    def start_hotspot(self):
        if SYSTEM == 'windows':
            self.execute_command('setup')
        return self.execute_command('start')

    def stop_hotspot(self):
        return self.execute_command('stop')

    def check_status(self):
        result = self.execute_command('status')
        if not result:
            return False

        status_indicators = {
            'windows': ('Started', 'Iniciado'),
            'darwin': ('state: running',),
            'linux': ('GENERAL.STATE: activated',)
        }
        
        return any(indicator in result.stdout for indicator in status_indicators[SYSTEM])

    def get_connected_devices(self):
        result = self.execute_command('list_devices')
        if not result:
            return []

        devices = []
        if SYSTEM == 'windows':
            network_prefix = '192.168.137.'
        elif SYSTEM == 'darwin':
            network_prefix = '192.168.2.'
        else:  # linux
            network_prefix = '192.168.1.'

        for line in result.stdout.splitlines():
            if network_prefix in line:
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0].strip()
                    mac = parts[1].replace('-', ':').lower()
                    devices.append((ip, mac))

        return devices

hotspot = HotspotManager()

apelidos_path = "apelidos.json"
apelidos = {}

# Carrega apelidos previamente salvos
if os.path.exists(apelidos_path):
    with open(apelidos_path, "r") as f:
        apelidos = json.load(f)

# Salva apelidos
def salvar_apelidos():
    with open(apelidos_path, "w") as f:
        json.dump(apelidos, f)

@app.route("/api/ativar")
def ativar_hotspot():
    hotspot.start_hotspot()
    return jsonify({"status": "Hotspot ativado"})

@app.route("/api/desativar")
def desativar_hotspot():
    hotspot.stop_hotspot()
    return jsonify({"status": "Hotspot desativado"})

def check_device_online(ip):
    ping_cmd = "ping -n 1 -w 1000" if SYSTEM == "windows" else "ping -c 1 -W 1"
    try:
        result = subprocess.run(f"{ping_cmd} {ip}", 
                              capture_output=True, 
                              shell=True,
                              encoding=hotspot.commands[SYSTEM]['encoding'])
        return "TTL=" in result.stdout or "ttl=" in result.stdout
    except:
        return False

@app.route("/api/dispositivos")
def listar_dispositivos():
    print("🔍 Verificando dispositivos...")
    dispositivos = []
    
    try:
        devices = hotspot.get_connected_devices()
        macs_encontrados = set()

        for ip, mac in devices:
            is_online = check_device_online(ip)
            nome = apelidos.get(mac, "Desconhecido")
            
            dispositivos.append({
                "ip": ip,
                "mac": mac,
                "nome": nome,
                "status": "online" if is_online else "offline"
            })
            if is_online:
                macs_encontrados.add(mac)
            print(f"Dispositivo {ip} ({mac}) - {'online' if is_online else 'offline'}")

        # Adiciona dispositivos conhecidos que não foram encontrados
        for mac, nome in apelidos.items():
            if not any(d["mac"] == mac for d in dispositivos):
                dispositivos.append({
                    "mac": mac,
                    "nome": nome,
                    "status": "offline"
                })
                print(f"Dispositivo conhecido offline: MAC={mac}, Nome={nome}")

    except Exception as e:
        print(f"Erro ao listar dispositivos: {e}")
    
    print(f"Total de dispositivos: {len(dispositivos)} (Online: {len(macs_encontrados)})")
    return jsonify(dispositivos)

@app.route("/api/apelido", methods=["POST"])
def definir_apelido():
    data = request.json
    print("Dados recebidos para salvar apelido:", data)  # Log para depuração
    mac = data.get("mac")
    apelido_nome = data.get("apelido")
    if mac and apelido_nome:
        apelidos[mac] = apelido_nome
        salvar_apelidos()
        print(f"Apelido '{apelido_nome}' salvo para {mac}")  # Log de sucesso
        return jsonify({"status": f"Apelido '{apelido_nome}' salvo para {mac}"})
    print("Erro ao definir apelido. Dados incompletos.")  # Log de erro
    return jsonify({"status": "Erro ao definir apelido."}), 400

def monitor_devices():
    while True:
        try:
            devices = hotspot.get_connected_devices()
            dispositivos = []
            macs_encontrados = set()

            for ip, mac in devices:
                is_online = check_device_online(ip)
                nome = apelidos.get(mac, "Desconhecido")
                
                dispositivos.append({
                    "ip": ip,
                    "mac": mac,
                    "nome": nome,
                    "status": "online" if is_online else "offline"
                })
                if is_online:
                    macs_encontrados.add(mac)

            for mac, nome in apelidos.items():
                if not any(d["mac"] == mac for d in dispositivos):
                    dispositivos.append({
                        "mac": mac,
                        "nome": nome,
                        "status": "offline"
                    })

            socketio.emit('devices_update', dispositivos)
        except Exception as e:
            print(f"Erro no monitoramento: {e}")
        
        time.sleep(1)  # Atualiza a cada segundo

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == '__main__':
    monitor_thread = threading.Thread(target=monitor_devices, daemon=True)
    monitor_thread.start()
    
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
