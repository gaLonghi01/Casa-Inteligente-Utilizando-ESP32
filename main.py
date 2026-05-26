import machine
import dht
import time
import network
import ujson
import urequests
from machine import Pin, SoftI2C, ADC, PWM
import ssd1306
from umqtt.simple import MQTTClient
import ntptime
import gc
import umail
import sys
import select

# ==========================================
# 1. CREDENCIAIS E CONFIGURAÇÕES
# ==========================================
WIFI_SSID = 'Wokwi-GUEST'
WIFI_PASSWORD = ''

# Credenciais HiveMQ Cloud
MQTT_BROKER = '85ea2ff2ae304602975571fd5ae2e49d.s1.eu.hivemq.cloud'
MQTT_PORT = 8883
MQTT_USER = 'GabrielLonghi'
MQTT_PASSWORD = 'Ga123456'
CLIENT_ID = 'esp32_casa_inteligente'

TOPICO_TELEMETRIA = b'casa/telemetria'
TOPICO_CMD_LUZ = b'casa/cmd/luz'
TOPICO_CMD_JANELA = b'casa/cmd/janela'
TOPICO_CMD_EXAUSTOR = b'casa/cmd/exaustor'
TOPICO_CMD_ALARME = b'casa/cmd/alarme'

URL_SHEETS = "https://script.google.com/macros/s/AKfycbxoT9jRupHwxXVEMCTm-21uyA42N2_iTePfa-oDPkV6Vi8oDyZrwYg2wzWWgOkEj5L0zg/exec"
EMAIL_REMETENTE = "gabriel.longhi02@gmail.com"
EMAIL_SENHA_APP = "rwpr igxg gilb igkb"
EMAIL_DESTINATARIO = "gabriel.longhi01@gmail.com"

LIMIAR_TEMP_ALTA = 45.0
LIMIAR_TEMP_REFRIG = 30.0
LIMIAR_UMID_BAIXA = 20.0
LUZ_CLAREOU = 7000 
LUZ_ANOITECEU = 6000  

# ==========================================
# 2. MAPEAMENTO DE HARDWARE (PINOUT)
# ==========================================
i2c = SoftI2C(scl=Pin(22), sda=Pin(21))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

sensor_dht = dht.DHT22(Pin(15))
ldr = ADC(Pin(34))
ldr.atten(ADC.ATTN_11DB)
mq2 = ADC(Pin(35))
mq2.atten(ADC.ATTN_11DB)
pir = Pin(13, Pin.IN)

led_luz = Pin(25, Pin.OUT)
rele_exaustor = Pin(26, Pin.OUT)
buzzer = PWM(Pin(12), freq=1000, duty=0)
servo_janela = PWM(Pin(14), freq=50)

# ==========================================
# 3. ESTADOS DO SISTEMA
# ==========================================
estado_luz = False
estado_exaustor = False
estado_janela = False 
estado_alarme = False
vazamento_detectado = False
perigo_incendio = False 

modo_manual_luz = False
modo_manual_exaustor = False

temp = 0.0
umid = 0.0

# ==========================================
# 4. FUNÇÕES DE CONTROLE (ATUADORES)
# ==========================================
def set_luz(estado):
    global estado_luz
    estado_luz = estado
    led_luz.value(1 if estado else 0)

def set_exaustor(estado):
    global estado_exaustor
    estado_exaustor = estado
    rele_exaustor.value(1 if estado else 0)

def set_alarme(estado):
    global estado_alarme
    estado_alarme = estado
    if estado:
        buzzer.duty(512) 
    else:
        buzzer.duty(0)

def set_janela(estado):
    global estado_janela
    estado_janela = estado
    if estado:
        servo_janela.duty(115) # Aberta
    else:
        servo_janela.duty(40)  # Fechada

# ==========================================
# 5. FUNÇÕES DE DADOS, SHEETS E E-MAIL
# ==========================================
def obter_data_hora_br():
    try:
        t = time.time() - (3 * 3600) 
        tm = time.localtime(t)
        return "{:02d}/{:02d}/{} {:02d}:{:02d}:{:02d}".format(tm[2], tm[1], tm[0], tm[3], tm[4], tm[5])
    except:
        return "00/00/0000 00:00:00"

def enviar_google_sheets(t_val, u_val, gas_val, tipo_alerta):
    gc.collect() 
    dados = {
        "data_hora": obter_data_hora_br(),
        "temp": t_val,
        "umid": u_val,
        "gas": gas_val,
        "alerta": tipo_alerta
    }
    payload = ujson.dumps(dados)
    headers = {'Content-Type': 'application/json'}
    try:
        print("Enviando dados para o Sheets...")
        res = urequests.post(URL_SHEETS, data=payload, headers=headers)
        print("=> Sheets Status:", res.status_code)
        res.close()
        print("=> Dados gravados na nuvem com sucesso!")
    except Exception as e:
        print("=> Erro Crítico no Sheets:", e)
    gc.collect()

def enviar_email_alerta(t_val, gas_val):
    gc.collect()
    try:
        print("Enviando E-mail de Emergência (Gás)...")
        smtp = umail.SMTP('smtp.gmail.com', 465, ssl=True)
        smtp.login(EMAIL_REMETENTE, EMAIL_SENHA_APP)
        smtp.to(EMAIL_DESTINATARIO)
        
        data_atual = obter_data_hora_br()
        
        smtp.write("From: Casa Inteligente <{}>\n".format(EMAIL_REMETENTE))
        smtp.write("Subject: ALERTA CRITICO - Vazamento de Gas Detectado!\n")
        smtp.write("🚨 ALERTA DE SEGURANÇA RESIDENCIAL 🚨\n")
        smtp.write("----------------------------\n")
        smtp.write("Data/Hora: {}\n".format(data_atual))
        smtp.write("Nível de Gás: {}\n".format(gas_val))
        smtp.write("Temperatura Local: {:.1f} C\n".format(t_val))
        smtp.write("Ações Automáticas Realizadas:\n")
        smtp.write("- Janela de emergência ABERTA.\n")
        smtp.write("- Exaustor LIGADO.\n")
        smtp.write("----------------------------\n")
        smtp.write("Por favor, verifique a residência imediatamente!\n")
        
        smtp.send()
        smtp.quit()
        print("=> E-mail de alerta de gás enviado com sucesso!")
    except Exception as e:
        print("=> Erro ao enviar email de gás:", e)

def enviar_email_incendio(t_val, u_val):  
    gc.collect()
    try:
        print("Enviando E-mail de Emergência (Incêndio)...")
        smtp = umail.SMTP('smtp.gmail.com', 465, ssl=True)
        smtp.login(EMAIL_REMETENTE, EMAIL_SENHA_APP)
        smtp.to(EMAIL_DESTINATARIO)
        
        data_atual = obter_data_hora_br()
        
        smtp.write("From: Casa Inteligente <{}>\n".format(EMAIL_REMETENTE))
        smtp.write("Subject: ALERTA CRITICO - Perigo de Incendio Detectado!\n")
        smtp.write("🚨 ALERTA DE INCÊNDIO RESIDENCIAL 🚨\n")
        smtp.write("----------------------------\n")
        smtp.write("Data/Hora: {}\n".format(data_atual))
        smtp.write("Temperatura Atual: {:.1f} C\n".format(t_val))
        smtp.write("Umidade Atual: {:.1f} %\n".format(u_val))
        smtp.write("Condição Crítica Detectada devido a valores fora da normalidade.\n")
        smtp.write("Ações Automáticas Realizadas:\n")
        smtp.write("- Janela de emergência ABERTA automaticamente.\n")
        smtp.write("----------------------------\n")
        smtp.write("Por favor, olhe a casa imediatamente e tome providências!\n")
        
        smtp.send()
        smtp.quit()
        print("=> E-mail de alerta de incêndio enviado!")
    except Exception as e:
        print("=> Erro ao enviar email de incêndio:", e)

# ==========================================
# 6. REDE, MQTT E SERIAL
# ==========================================
def conecta_wifi_e_ntp():
    oled.fill(0)
    oled.text("Conectando WiFi", 0, 20)
    oled.show()
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    sta_if.connect(WIFI_SSID, WIFI_PASSWORD)
    while not sta_if.isconnected():
        time.sleep(0.5)
    print("WiFi OK. IP:", sta_if.ifconfig()[0])
    
    print("Sincronizando relógio NTP...")
    try:
        ntptime.settime()
    except:
        pass
    return sta_if.ifconfig()[0]

def mqtt_callback(topic, msg):
    global modo_manual_luz, modo_manual_exaustor
    print("Comando MQTT recebido:", topic, msg)
    comando = msg.decode('utf-8').upper()
    estado = (comando == "ON" or comando == "1" or comando == "TRUE")
    
    if topic == TOPICO_CMD_LUZ: 
        modo_manual_luz = True
        set_luz(estado)
    elif topic == TOPICO_CMD_EXAUSTOR: 
        modo_manual_exaustor = True
        set_exaustor(estado)
    elif topic == TOPICO_CMD_JANELA: 
        set_janela(estado)
    elif topic == TOPICO_CMD_ALARME: 
        set_alarme(estado)

def conecta_mqtt():
    client = MQTTClient(
        CLIENT_ID, 
        MQTT_BROKER, 
        port=MQTT_PORT, 
        user=MQTT_USER, 
        password=MQTT_PASSWORD, 
        keepalive=60, 
        ssl=True, 
        ssl_params={'server_hostname': MQTT_BROKER}
    )
    client.set_callback(mqtt_callback)
    client.connect()
    print("MQTT Conectado! Inscrevendo nos tópicos...")
    client.subscribe(TOPICO_CMD_LUZ)
    client.subscribe(TOPICO_CMD_JANELA)
    client.subscribe(TOPICO_CMD_EXAUSTOR)
    client.subscribe(TOPICO_CMD_ALARME)
    return client

# Configuração da leitura serial
poll_obj = select.poll()
poll_obj.register(sys.stdin, select.POLLIN)

# ==========================================
# 7. INICIALIZAÇÃO
# ==========================================
ip_local = conecta_wifi_e_ntp()
cliente_mqtt = conecta_mqtt()

set_luz(False)
set_exaustor(False)
set_janela(False)
set_alarme(False)

ultimo_envio_mqtt = 0
ultimo_leitura_dht = 0
ultimo_envio_sheets = time.ticks_ms()
ultima_atualizacao_oled = 0
tempo_inicio_alarme = 0
pir_disparado = False

INTERVALO_DHT = 2000     
INTERVALO_OLED = 1000    
INTERVALO_MQTT = 1500    
INTERVALO_SHEETS = 10000  

print("Sistema Casa Inteligente Iniciado!")

# ==========================================
# 8. LOOP PRINCIPAL
# ==========================================
while True:
    try:
        gc.collect() 
        agora = time.ticks_ms()
        
        # --- LER SENSORES LENTOS (DHT22) ---
        if time.ticks_diff(agora, ultimo_leitura_dht) > INTERVALO_DHT:
            try:
                sensor_dht.measure()
                temp = sensor_dht.temperature()
                umid = sensor_dht.humidity()
            except OSError:
                pass 
            ultimo_leitura_dht = agora

        # --- LER SENSORES RÁPIDOS ---
        leitura_luz = ldr.read_u16() 
        leitura_gas = mq2.read()
        movimento = pir.value()

        # --- LÓGICA DO SENSOR DE LUMINOSIDADE (LDR) ---
        if not modo_manual_luz:
            if leitura_luz <= LUZ_ANOITECEU:
                if estado_luz:
                    set_luz(False)  
            elif leitura_luz >= LUZ_CLAREOU: 
                if not estado_luz:
                    set_luz(True)  

        # --- LÓGICA DO SENSOR DE MOVIMENTO (PIR) ---
        if movimento == 1:
            if not estado_alarme and not pir_disparado:
                set_alarme(True)
                tempo_inicio_alarme = agora
                pir_disparado = True
        else:
            pir_disparado = False

        if estado_alarme and not (vazamento_detectado or perigo_incendio) and time.ticks_diff(agora, tempo_inicio_alarme) > 3000:
            set_alarme(False)

        # --- GERENCIAMENTO DO EXAUSTOR ---
        if not modo_manual_exaustor:
            if temp > LIMIAR_TEMP_REFRIG and temp <= LIMIAR_TEMP_ALTA:
                if not estado_exaustor:
                    set_exaustor(True)
            elif temp <= LIMIAR_TEMP_REFRIG and not vazamento_detectado:
                if estado_exaustor:
                    set_exaustor(False)

        # --- LÓGICA DE EMERGÊNCIA GÁS ---
        if leitura_gas > 3000 and not vazamento_detectado:
            vazamento_detectado = True
            set_janela(True)
            set_exaustor(True)
            set_alarme(True) 
            print("!!! VAZAMENTO DETECTADO !!!")
            enviar_email_alerta(temp, leitura_gas)
            enviar_google_sheets(temp, umid, leitura_gas, "VAZAMENTO DE GAS")
            
        elif leitura_gas < 2500 and vazamento_detectado:
            vazamento_detectado = False
            if temp <= LIMIAR_TEMP_REFRIG and not modo_manual_exaustor:
                set_exaustor(False)

        # --- LÓGICA DE INCÊNDIO ---
        if (temp > LIMIAR_TEMP_ALTA or umid < LIMIAR_UMID_BAIXA) and not perigo_incendio:
            perigo_incendio = True
            set_janela(True)  
            set_alarme(True) 
            print("!!! PERIGO DE INCÊNDIO !!!")
            enviar_email_incendio(temp, umid)
            enviar_google_sheets(temp, umid, leitura_gas, "PERIGO DE INCENDIO")
            
        elif (temp <= (LIMIAR_TEMP_ALTA - 5) and umid >= (LIMIAR_UMID_BAIXA + 5)) and perigo_incendio:
            perigo_incendio = False

        # --- LER COMANDOS VIA SERIAL (DO FLASK) ---
        if poll_obj.poll(0):
            linha = sys.stdin.readline().strip()
            if linha:
                cmd = linha.upper()
                if cmd == "LUZ_ON":
                    modo_manual_luz = True
                    set_luz(True)
                    print("OK | Luz Ligada")
                elif cmd == "LUZ_OFF":
                    modo_manual_luz = True
                    set_luz(False)
                    print("OK | Luz Desligada")
                elif cmd == "EXAUST_ON":
                    modo_manual_exaustor = True
                    set_exaustor(True)
                    print("OK | Exaustor Ligado")
                elif cmd == "EXAUST_OFF":
                    modo_manual_exaustor = True
                    set_exaustor(False)
                    print("OK | Exaustor Desligado")
                elif cmd == "JANELA_ON":
                    set_janela(True)
                    print("OK | Janela Aberta")
                elif cmd == "JANELA_OFF":
                    set_janela(False)
                    print("OK | Janela Fechada")
                elif cmd == "ALARME_OFF":
                    set_alarme(False)
                    print("OK | Alarme Silenciado")
                elif cmd == "STATUS":
                    print("Luz: {} | Exaustor: {} | Janela: {} | Alarme: {}".format(
                        "ON" if estado_luz else "OFF",
                        "ON" if estado_exaustor else "OFF",
                        "ABERTA" if estado_janela else "FECHADA",
                        "ATIVO" if estado_alarme else "OK"
                    ))

        # --- ATUALIZAR OLED ---
        if time.ticks_diff(agora, ultima_atualizacao_oled) > INTERVALO_OLED:
            oled.fill(0)
            if vazamento_detectado:
                oled.text("!!! PERIGO !!!", 15, 10)
                oled.text("VAZAMENTO DE GAS", 0, 30)
                oled.text("JANELA ABERTA", 15, 50)
            elif perigo_incendio:  
                oled.text("!!! PERIGO !!!", 15, 10)
                oled.text("RISCO DE INCENDIO", 0, 30)
                oled.text("JANELA ABERTA", 15, 50)
            else:
                oled.text("T:{}C U:{}%".format(temp, umid), 0, 0)
                oled.text("Luz:{} Mov:{}".format('ON' if estado_luz else 'OFF', 'SIM' if movimento else 'NAO'), 0, 15)
                oled.text("Janela:{}".format('ABERTA' if estado_janela else 'FECH.'), 0, 30)
                oled.text("IP: {}".format(ip_local), 0, 50)
            oled.show()
            ultima_atualizacao_oled = agora

        cliente_mqtt.check_msg()

        # --- PUBLICAR TELEMETRIA MQTT ---
        if time.ticks_diff(agora, ultimo_envio_mqtt) > INTERVALO_MQTT:
            payload = ujson.dumps({
                "temperatura": temp,
                "umidade": umid,
                "luminosidade": leitura_luz,
                "gas": leitura_gas,
                "movimento": movimento,
                "status_luz": estado_luz,
                "status_janela": estado_janela,
                "status_alarme": estado_alarme,
                "status_exaustor": estado_exaustor,
                "status_incendio": perigo_incendio  
            })
            cliente_mqtt.publish(TOPICO_TELEMETRIA, payload)
            ultimo_envio_mqtt = agora

        if time.ticks_diff(agora, ultimo_envio_sheets) > INTERVALO_SHEETS:
            enviar_google_sheets(temp, umid, leitura_gas, "NAO")
            ultimo_envio_sheets = agora

    except Exception as e:
        print("Erro Loop:", e)
    
    time.sleep(0.1)