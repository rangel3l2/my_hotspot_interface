from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit
import subprocess
import json
import os
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

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

# Ativa o hotspot
@app.route("/api/ativar")
def ativar_hotspot():
    subprocess.run("netsh wlan set hostednetwork mode=allow ssid=MeuHotspot key=12345678", shell=True)
    subprocess.run("netsh wlan start hostednetwork", shell=True)
    return jsonify({"status": "Hotspot ativado"})

# Desativa o hotspot
@app.route("/api/desativar")
def desativar_hotspot():
    subprocess.run("netsh wlan stop hostednetwork", shell=True)
    return jsonify({"status": "Hotspot desativado"})

def check_hotspot_status():
    try:
        result = subprocess.run("netsh wlan show hostednetwork", 
                              capture_output=True, 
                              text=True, 
                              shell=True,
                              encoding='cp850')  # Encoding para Windows
        return "Iniciado" in result.stdout or "Started" in result.stdout
    except Exception as e:
        print(f"Erro ao verificar status do hotspot: {e}")
        return False

def check_device_online(ip):
    try:
        # Ping com timeout reduzido para resposta mais rápida
        result = subprocess.run(f"ping -n 1 -w 1000 {ip}", 
                              capture_output=True, 
                              shell=True,
                              encoding='cp850')
        return "TTL=" in result.stdout
    except:
        return False

# Lista os dispositivos conectados
@app.route("/api/dispositivos")
def listar_dispositivos():
    print("🔍 Verificando dispositivos...")
    dispositivos = []
    
    try:
        # Executa o comando ARP para listar dispositivos
        resultado = subprocess.run("arp -a", 
                                capture_output=True, 
                                text=True, 
                                shell=True,
                                encoding='cp850')
        
        linhas = resultado.stdout.splitlines()
        macs_encontrados = set()

        # Procura por dispositivos na faixa de IP do hotspot
        for linha in linhas:
            if "192.168.137." in linha:
                partes = linha.split()
                if len(partes) >= 2:
                    ip = partes[0].strip()
                    mac = partes[1].replace("-", ":").lower()
                    
                    # Verifica se o dispositivo está realmente online
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
            resultado = subprocess.run("arp -a", 
                                    capture_output=True, 
                                    text=True, 
                                    shell=True,
                                    encoding='cp850')
            
            dispositivos = []
            macs_encontrados = set()

            for linha in resultado.stdout.splitlines():
                if "192.168.137." in linha:
                    partes = linha.split()
                    if len(partes) >= 2:
                        ip = partes[0].strip()
                        mac = partes[1].replace("-", ":").lower()
                        
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

# Rota principal (frontend)
@app.route("/")
def index():
    return render_template("index.html")

if __name__ == '__main__':
    # Inicia o monitoramento em uma thread separada
    monitor_thread = threading.Thread(target=monitor_devices, daemon=True)
    monitor_thread.start()
    
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
