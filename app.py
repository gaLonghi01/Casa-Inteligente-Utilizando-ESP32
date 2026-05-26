from flask import Flask, render_template, jsonify, request
import serial
import serial.tools.list_ports
import time
import os

app = Flask(__name__)

SERIAL_BAUDRATE = 115200
serial_conn = None
serial_port_name = None
last_status = "Desconectado"

def listar_portas():
    # Insere forçadamente a porta virtual do simulador Wokwi no topo da lista
    portas = [{"device": "rfc2217://127.0.0.1:4000", "description": "Simulador Wokwi (TCP 4000)"}]
    
    # Mantém a listagem física caso o código vá para um ESP32 real depois
    portas += [{"device": p.device, "description": p.description} for p in serial.tools.list_ports.comports()]
    return portas

def conectar(porta):
    global serial_conn, serial_port_name, last_status
    if serial_conn and serial_conn.is_open:
        serial_conn.close()

    try:
        # Pyserial tem tratamento especial para conexões via rede virtual
        if porta.startswith("rfc2217://"):
            serial_conn = serial.serial_for_url(porta, baudrate=SERIAL_BAUDRATE, timeout=1)
        else:
            serial_conn = serial.Serial(porta, SERIAL_BAUDRATE, timeout=1)
            
        serial_port_name = porta
        time.sleep(1) 
        
        if hasattr(serial_conn, 'reset_input_buffer'):
            serial_conn.reset_input_buffer()
            
        last_status = f"Conectado em {porta}"
        return last_status
    except Exception as e:
        last_status = f"Erro de conexão: {str(e)}"
        raise e

def enviar_comando(cmd):
    global last_status
    if not serial_conn or not serial_conn.is_open:
        last_status = "ESP32 não conectado. Selecione a porta e conecte."
        return last_status

    serial_conn.write((cmd + "\n").encode("utf-8"))
    time.sleep(0.15)

    linhas = []
    while serial_conn.in_waiting:
        linhas.append(serial_conn.readline().decode("utf-8", errors="ignore").strip())

    resposta = " | ".join([l for l in linhas if l])
    last_status = resposta if resposta else f"Comando enviado: {cmd}"
    return last_status

@app.route("/")
def index():
    return render_template("index.html", portas=listar_portas(), porta_atual=serial_port_name, status=last_status)

@app.route("/connect", methods=["POST"])
def connect():
    porta = request.json.get("porta")
    try:
        msg = conectar(porta)
        return jsonify({"ok": True, "status": msg})
    except Exception as e:
        return jsonify({"ok": False, "status": f"Erro: {e}"}), 500

@app.route("/cmd", methods=["POST"])
def cmd():
    comando = request.json.get("cmd", "").upper()
    permitidos = {"LUZ_ON", "LUZ_OFF", "EXAUST_ON", "EXAUST_OFF", "JANELA_ON", "JANELA_OFF", "ALARME_OFF", "STATUS"}

    if comando not in permitidos:
        return jsonify({"ok": False, "status": "Comando inválido"}), 400

    try:
        resposta = enviar_comando(comando)
        return jsonify({"ok": True, "status": resposta})
    except Exception as e:
        return jsonify({"ok": False, "status": f"Erro ao enviar: {e}"}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)