from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit
import subprocess
import json
import os
import threading
import time
import platform
import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

SYSTEM = platform.system().lower()

class HotspotManager:
    def __init__(self):
        self.known_devices = set()  # Track known devices
        self.ip_reservations = {}  # MAC -> IP mapping
        self.last_ip = 100  # Start from 192.168.137.100
        self.status_changes = {}  # Track device status changes and times
        self.internet_enabled = False
        self.tempos_file = "tempos_aula.json"
        self.load_tempos()
        self.commands = {
            'windows': {
                'start': 'netsh wlan start hostednetwork',
                'stop': 'netsh wlan stop hostednetwork',
                'setup': 'netsh wlan set hostednetwork mode=allow ssid=MeuHotspot key=12345678',
                'status': 'netsh wlan show hostednetwork',
                'list_devices': 'arp -a',
                'encoding': 'cp850',
                'enable_internet': 'netsh interface set interface "Ethernet" enabled && netsh interface set interface "Local Area Connection* 1" enabled && netsh routing ip nat add interface "Ethernet" "Local Area Connection* 1" enable=yes',
                'disable_internet': 'netsh interface set interface "Local Area Connection* 1" disabled',
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
        self.last_reset_file = "last_reset.json"
        self.last_reset = self.load_last_reset()
        self.ip_reservations_file = "ip_reservations.json"
        self.load_ip_reservations()
        self.aula_start_time = None
        self.aula_duration = 0

    def load_last_reset(self):
        try:
            if os.path.exists(self.last_reset_file):
                with open(self.last_reset_file, 'r') as f:
                    data = json.load(f)
                    return datetime.datetime.strptime(data['last_reset'], '%Y-%m-%d').date()
            return datetime.datetime.now().date()
        except:
            return datetime.datetime.now().date()

    def save_last_reset(self):
        with open(self.last_reset_file, 'w') as f:
            json.dump({'last_reset': self.last_reset.strftime('%Y-%m-%d')}, f)

    def load_ip_reservations(self):
        """Load saved IP reservations from file"""
        try:
            if os.path.exists(self.ip_reservations_file):
                with open(self.ip_reservations_file, 'r') as f:
                    self.ip_reservations = json.load(f)
            else:
                self.ip_reservations = {}
        except:
            self.ip_reservations = {}
        
        # Encontra o último IP usado
        self.last_ip = 100
        for ip in self.ip_reservations.values():
            try:
                last_octet = int(ip.split('.')[-1])
                self.last_ip = max(self.last_ip, last_octet)
            except:
                continue

    def save_ip_reservations(self):
        """Save current IP reservations to file"""
        with open(self.ip_reservations_file, 'w') as f:
            json.dump(self.ip_reservations, f)

    def load_tempos(self):
        """Carrega os tempos salvos do arquivo"""
        try:
            if os.path.exists(self.tempos_file):
                with open(self.tempos_file, 'r') as f:
                    self.status_changes = json.load(f)
        except:
            self.status_changes = {}

    def save_tempos(self):
        """Salva os tempos no arquivo"""
        with open(self.tempos_file, 'w') as f:
            json.dump(self.status_changes, f)

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

    def execute_command_as_admin(self, cmd):
        try:
            subprocess.run(
                ['runas', '/user:Administrator', cmd],
                shell=True,
                capture_output=True,
                text=True,
                encoding=self.commands[SYSTEM]['encoding']
            )
        except Exception as e:
            print(f"Erro ao executar comando como admin: {e}")

    def get_or_assign_ip(self, mac):
        mac = mac.lower()  # Normaliza o MAC address
        
        # Verifica se já existe uma reserva para este MAC
        if mac in self.ip_reservations:
            return self.ip_reservations[mac]
        
        # Se não existe, cria uma nova reserva
        self.last_ip += 1
        new_ip = f"192.168.137.{self.last_ip}"
        self.ip_reservations[mac] = new_ip
        
        # Salva as reservas atualizadas
        self.save_ip_reservations()
        
        # Configura a reserva no Windows
        if SYSTEM == 'windows':
            cmd = f'netsh dhcp server \\\\local add reservedip 192.168.137.0 {new_ip} {mac} "Reserved for {mac}"'
            self.execute_command_as_admin(cmd)
        
        print(f"Nova reserva de IP: {mac} -> {new_ip}")
        return new_ip

    def start_hotspot(self):
        if SYSTEM == 'windows':
            print("Setting up hotspot...")  # Debug log
            setup_result = self.execute_command('setup')
            print(f"Setup result: {setup_result.stdout if setup_result else 'None'}")  # Debug log
            
            print("Starting hotspot...")  # Debug log
            start_result = self.execute_command('start')
            print(f"Start result: {start_result.stdout if start_result else 'None'}")  # Debug log
            
            return start_result
        return self.execute_command('start')

    def stop_hotspot(self):
        if SYSTEM == 'windows':
            # Save IP reservations
            self.save_ip_reservations()
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
        network_prefix = '192.168.137.'

        # IPs to ignore
        ignore_ips = {
            '192.168.137.1',  # System interface
            '192.168.137.255'  # Broadcast
        }

        # MACs to ignore
        ignore_macs = {
            'ff:ff:ff:ff:ff:ff',  # Broadcast
            '00:00:00:00:00:00'   # Invalid
        }

        for line in result.stdout.splitlines():
            if network_prefix in line:
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0].strip()
                    mac = parts[1].replace('-', ':').lower()
                    
                    # Skip system and broadcast addresses
                    if ip in ignore_ips or mac in ignore_macs:
                        continue
                    
                    # Skip interfaces
                    if "interface" in line.lower():
                        continue
                    
                    devices.append((ip, mac))
                    print(f"Found external device: IP={ip}, MAC={mac}")  # Debug log

        print(f"Total external devices found: {len(devices)}")  # Debug log
        return devices

    def check_daily_reset(self):
        current_date = datetime.datetime.now().date()
        days_difference = (current_date - self.last_reset).days
        
        if days_difference > 0:
            print(f"Resetting offline times. Days since last reset: {days_difference}")
            # Reset for each missed day
            for mac in self.status_changes:
                self.status_changes[mac]['total_offline'] = 0
                if self.status_changes[mac]['last_status'] == 'offline':
                    self.status_changes[mac]['offline_start'] = time.time()
            
            self.last_reset = current_date
            self.save_last_reset()
            print(f"Reset completed. New reset date: {self.last_reset}")

    def iniciar_aula(self):
        self.aula_start_time = time.time()
        self.status_changes = {}
        
        # Inicializa todos os dispositivos conhecidos com tempo zero
        devices = self.get_connected_devices()
        devices_online = set()
        
        # Primeiro identifica quais dispositivos estão online
        for ip, mac in devices:
            if check_device_online(ip):
                devices_online.add(mac)
        
        # Inicializa dispositivos conectados e com apelidos
        all_devices = set(mac for _, mac in devices) | set(apelidos.keys())
        
        for mac in all_devices:
            is_online = mac in devices_online
            self.status_changes[mac] = {
                'last_status': 'online' if is_online else 'offline',
                'last_change': time.time(),
                'tempo_conectado': 0,
                'tempo_desconectado': 0,
                'ultima_conexao': time.time() if is_online else None,
                'offline_start': None,
                'total_offline': 0,
                'ever_connected': is_online  # New field to track if device was ever online
            }
        
        self.save_tempos()

    def finalizar_aula(self):
        """Finaliza a aula e retorna os resultados"""
        if not self.aula_start_time:
            return []
        
        try:
            tempo_final = time.time()
            tempo_total = tempo_final - self.aula_start_time
            self.aula_duration = tempo_total
            resultados = []
            
            # Processa os resultados de todos os dispositivos conhecidos
            for mac in list(self.status_changes.keys()):
                dados = self.status_changes[mac]
                nome = apelidos.get(mac, mac)
                ip = self.ip_reservations.get(mac, "N/A")
                
                # Calcula tempo conectado final
                tempo_conectado = dados.get('tempo_conectado', 0)
                if dados['last_status'] == 'online' and dados.get('ultima_conexao'):
                    tempo_conectado += tempo_final - dados['ultima_conexao']
                
                # Calcula percentual e nota
                percentual = (tempo_conectado / tempo_total * 100) if tempo_total > 0 else 0
                nota = min(8.0, (percentual * 8.0 / 100.0))
                
                resultado = {
                    'nome': nome,
                    'mac': mac,
                    'ip': ip,
                    'tempo_conectado': tempo_conectado,
                    'tempo_desconectado': dados.get('tempo_desconectado', 0),
                    'percentual': percentual,
                    'nota': nota
                }
                resultados.append(resultado)
                print(f"Processado resultado para {nome}:", resultado)
            
            # Ordena e finaliza
            resultados.sort(key=lambda x: x['tempo_conectado'], reverse=True)
            self.aula_start_time = None
            self.save_tempos()
            
            return resultados
            
        except Exception as e:
            print(f"Erro ao finalizar aula: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def update_status_time(self, mac, status):
        if not self.aula_start_time:
            return
        
        current_time = time.time()
        
        if mac not in self.status_changes:
            # Novo dispositivo
            self.status_changes[mac] = {
                'last_status': status,
                'last_change': current_time,
                'tempo_conectado': 0,
                'tempo_desconectado': 0,
                'ultima_conexao': current_time if status == 'online' else None,
                'offline_start': None,
                'total_offline': 0,
                'ever_connected': status == 'online'  # Set true if device starts online
            }
        else:
            dados = self.status_changes[mac]
            
            if status != dados['last_status']:
                if status == 'online':
                    # Device connected
                    dados['ever_connected'] = True  # Mark as having connected at least once
                    if dados.get('offline_start'):
                        # Only count offline time if device was previously connected
                        if dados['ever_connected']:
                            dados['tempo_desconectado'] += current_time - dados['offline_start']
                        dados['offline_start'] = None
                    dados['ultima_conexao'] = current_time
                else:
                    # Device disconnected
                    dados['offline_start'] = current_time if dados['ever_connected'] else None
                    if dados['ultima_conexao']:
                        dados['tempo_conectado'] += current_time - dados['ultima_conexao']
                        dados['ultima_conexao'] = None

                dados['last_status'] = status
                dados['last_change'] = current_time
                print(f"Device {mac} status changed to {status}. Connected: {dados['tempo_conectado']}, Disconnected: {dados['tempo_desconectado']}, Ever connected: {dados['ever_connected']}")

        self.save_tempos()

    def get_offline_time(self, mac):
        if not self.aula_start_time:
            return 0
            
        if mac not in self.status_changes:
            return 0
            
        dados = self.status_changes[mac]
        
        # Only return offline time if device was ever connected
        if not dados.get('ever_connected'):
            return 0
            
        total = dados.get('tempo_desconectado', 0)
        
        # Add current offline time if device is offline and was previously connected
        if dados['last_status'] == 'offline' and dados.get('offline_start'):
            total += time.time() - dados['offline_start']
            
        return int(total)

    def toggle_internet(self, enable=True):
        if SYSTEM == 'windows':
            cmd_type = 'enable_internet' if enable else 'disable_internet'
            self.execute_command_as_admin(self.commands[SYSTEM][cmd_type])
            self.internet_enabled = enable
            return True
        return False

    def get_internet_status(self):
        return self.internet_enabled

    def resetar_tempos(self):
        """Reseta todos os tempos offline"""
        for mac in self.status_changes:
            self.status_changes[mac]['total_offline'] = 0
            self.status_changes[mac]['offline_start'] = None
        self.save_tempos()

hotspot = HotspotManager()

apelidos_path = "apelidos.json"
apelidos = {}

# Carrega apelidos previamente salvos
if os.path.exists(apelidos_path):
    try:
        with open(apelidos_path, "r") as f:
            content = f.read().strip()
            if content:
                apelidos = json.loads(content)
            else:
                # Se o arquivo estiver vazio, cria um novo com objeto vazio
                with open(apelidos_path, "w") as f:
                    json.dump({}, f)
    except json.JSONDecodeError:
        # Se houver erro no JSON, reinicia o arquivo
        with open(apelidos_path, "w") as f:
            json.dump({}, f)
else:
    # Se o arquivo não existir, cria um novo
    with open(apelidos_path, "w") as f:
        json.dump({}, f)

# Salva apelidos
def salvar_apelidos():
    with open(apelidos_path, "w") as f:
        json.dump(apelidos, f)

def check_device_online(ip):
    """Check if device is online using a simpler and more reliable method for Windows"""
    if SYSTEM == "windows":
        try:
            # Use netstat to check active connections
            netstat_result = subprocess.run(
                f'netstat -n | findstr "{ip}"',
                capture_output=True,
                shell=True,
                encoding=hotspot.commands[SYSTEM]['encoding']
            )
            if ip in netstat_result.stdout:
                return True

            # If not found in netstat, try a quick ping
            ping_result = subprocess.run(
                f'ping -n 1 -w 1000 {ip}',
                capture_output=True,
                shell=True,
                encoding=hotspot.commands[SYSTEM]['encoding']
            )
            return "TTL=" in ping_result.stdout
            
        except Exception as e:
            print(f"Erro ao verificar status do dispositivo {ip}: {e}")
            return False  # Assume offline em caso de erro
    else:
        try:
            ping_cmd = f"ping -c 1 -W 1 {ip}"
            result = subprocess.run(
                ping_cmd,
                capture_output=True,
                shell=True,
                encoding=hotspot.commands[SYSTEM]['encoding']
            )
            return result.returncode == 0
        except:
            return False

@app.route("/api/ativar")
def ativar_hotspot():
    hotspot.start_hotspot()
    return jsonify({"status": "Hotspot ativado"})

@app.route("/api/desativar")
def desativar_hotspot():
    hotspot.stop_hotspot()
    return jsonify({"status": "Hotspot desativado"})

@app.route("/api/dispositivos")
def listar_dispositivos():
    print("🔍 Verificando dispositivos...")
    dispositivos = []
    
    try:
        devices = hotspot.get_connected_devices()
        macs_encontrados = set()
        status_cache = {}

        # First pass: Check all devices status
        for ip, mac in devices:
            is_online = check_device_online(ip)
            status_cache[mac] = is_online
            print(f"Device status check: {ip} ({mac}): {'online' if is_online else 'offline'}")

        # Second pass: Process devices with verified status
        for ip, mac in devices:
            is_online = status_cache.get(mac, False)  # Default to offline if not checked
            nome = apelidos.get(mac, "Desconhecido")
            status = "online" if is_online else "offline"
            
            # Only use grace period for devices that were recently online
            previous_status = hotspot.status_changes.get(mac, {}).get('last_status')
            last_change = hotspot.status_changes.get(mac, {}).get('last_change', 0)
            
            # 30 second grace period only for devices that were actually online before
            if not is_online and previous_status == 'online' and time.time() - last_change < 30:
                status = 'online'
                is_online = True
                print(f"Grace period applied for {nome} ({mac})")

            hotspot.update_status_time(mac, status)
            offline_time = hotspot.get_offline_time(mac)
            
            dispositivos.append({
                "ip": ip,
                "mac": mac,
                "nome": nome,
                "status": status,
                "offline_time": offline_time,
                "total_offline": format_time(offline_time)
            })
            
            if is_online:
                macs_encontrados.add(mac)

        # Adiciona dispositivos conhecidos que não foram encontrados
        for mac, nome in apelidos.items():
            if not any(d["mac"] == mac for d in dispositivos):
                hotspot.update_status_time(mac, "offline")
                offline_time = hotspot.get_offline_time(mac)
                dispositivos.append({
                    "mac": mac,
                    "nome": nome,
                    "status": "offline",
                    "offline_time": offline_time,
                    "total_offline": format_time(offline_time)
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
        # Reserve IP when nickname is set
        hotspot.get_or_assign_ip(mac)
        print(f"Apelido '{apelido_nome}' salvo para {mac}")  # Log de sucesso
        return jsonify({"status": f"Apelido '{apelido_nome}' salvo para {mac}"})
    print("Erro ao definir apelido. Dados incompletos.")  # Log de erro
    return jsonify({"status": "Erro ao definir apelido."}), 400

@app.route("/api/apelido/deletar", methods=["POST"])
def deletar_dispositivo():
    data = request.json
    mac = data.get("mac")
    if mac in apelidos:
        del apelidos[mac]
        if mac in hotspot.ip_reservations:
            del hotspot.ip_reservations[mac]
        salvar_apelidos()
        return jsonify({"status": "Dispositivo removido com sucesso"})
    return jsonify({"status": "Dispositivo não encontrado"}), 404

@app.route("/api/internet", methods=["POST"])
def toggle_internet():
    data = request.json
    enable = data.get("enable", True)
    if hotspot.toggle_internet(enable):
        return jsonify({"status": "Internet " + ("enabled" if enable else "disabled")})
    return jsonify({"status": "Failed to toggle internet"}), 400

@app.route("/api/internet/status")
def get_internet_status():
    return jsonify({"enabled": hotspot.get_internet_status()})

@app.route("/api/resetar_tempos", methods=["POST"])
def resetar_tempos():
    hotspot.resetar_tempos()
    return jsonify({"status": "Tempos resetados com sucesso"})

@app.route("/api/aula/iniciar", methods=["POST"])
def iniciar_aula():
    try:
        print("Iniciando aula...")
        hotspot.iniciar_aula()
        return jsonify({
            "status": "success",
            "mensagem": "Aula iniciada com sucesso"
        })
    except Exception as e:
        print(f"Erro ao iniciar aula: {str(e)}")
        return jsonify({
            "status": "error",
            "mensagem": str(e)
        }), 500

@app.route("/api/aula/finalizar", methods=["POST"])
def finalizar_aula():
    try:
        print("Verificando status da aula...")
        if not hotspot.aula_start_time:
            return jsonify({
                "status": "error",
                "mensagem": "Nenhuma aula em andamento"
            }), 400

        # Força uma última atualização dos status
        devices = hotspot.get_connected_devices()
        for ip, mac in devices:
            is_online = check_device_online(ip)
            status = "online" if is_online else "offline"
            hotspot.update_status_time(mac, status)

        print("Gerando resultados finais...")
        resultados = hotspot.finalizar_aula()
        
        if not resultados:
            print("Nenhum resultado gerado")
            return jsonify({
                "status": "error",
                "mensagem": "Nenhum resultado disponível"
            }), 404
            
        print(f"Processados {len(resultados)} resultados")
        response = {
            "status": "success",
            "mensagem": "Aula finalizada com sucesso",
            "duracao_total": hotspot.aula_duration,
            "resultados": resultados
        }
        print("Resposta:", response)
        return jsonify(response)
        
    except Exception as e:
        print(f"Erro ao finalizar aula: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "mensagem": "Erro interno ao finalizar aula",
            "error": str(e)
        }), 500

def monitor_devices():
    while True:
        try:
            if hotspot.aula_start_time:  # Só monitora se tiver aula em andamento
                devices = hotspot.get_connected_devices()
                dispositivos = []
                macs_encontrados = set()

                for ip, mac in devices:
                    is_online = check_device_online(ip)
                    nome = apelidos.get(mac, "Desconhecido")
                    status = "online" if is_online else "offline"
                    
                    # Atualiza tempo mesmo se estiver offline
                    hotspot.update_status_time(mac, status)
                    offline_time = hotspot.get_offline_time(mac)
                    
                    dispositivo = {
                        "ip": ip,
                        "mac": mac,
                        "nome": nome,
                        "status": status,
                        "offline_time": offline_time,
                        "total_offline": format_time(offline_time)
                    }
                    dispositivos.append(dispositivo)
                    
                    if is_online:
                        macs_encontrados.add(mac)
                        print(f"Monitorando {nome} ({mac}): online")
                    else:
                        print(f"Monitorando {nome} ({mac}): offline por {format_time(offline_time)}")

                socketio.emit('devices_update', dispositivos)
                
        except Exception as e:
            print(f"Erro no monitoramento: {e}")
        
        time.sleep(1)  # Atualiza a cada segundo

def format_time(seconds):
    """Format seconds into human readable string"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours}h {minutes}m {seconds}s"

@app.route('/')
def index():
    return render_template("index.html")

if __name__ == '__main__':
    # Inicia o monitoramento em uma thread separada
    monitor_thread = threading.Thread(target=monitor_devices, daemon=True)
    monitor_thread.start()
    
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
