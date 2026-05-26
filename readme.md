# Sistema de Automação Residencial IoT - ESP32, MicroPython, Flask e Node-RED

Este projeto consiste em um sistema completo de IoT para controle e monitoramento residencial estruturado para ambiente acadêmico. Integra a simulação de hardware do ESP32 via Wokwi no VS Code, um servidor web intermediário em Flask para controle local por porta serial virtual, e um ecossistema em nuvem baseado em MQTT (HiveMQ) integrado ao Node-RED, Google Sheets e alertas por e-mail.

## Como rodar o projeto

Após iniciar a simulação wokwi por meio do diagram.json, espere um ">>>" aparecer no terminal, e abra um novo terminal powershell na pasta onde o projeto está. Depois disso cole esse comando no terminal powershell e mande:

python -m mpremote connect port:rfc2217://localhost:4000 fs cp main.py :main.py + fs cp ssd1306.py :ssd1306.py + fs cp umail.py :umail.py + reset

Esse comando manda a main para o ESP32

Assim que o terminal ficar livre para digitar, cole isso no terminal powershell e mande:

python app.py

Isso roda a página web

## Pré-requisitos e Dependências

Antes de rodar a aplicação, instale os pacotes necessários no terminal do sistema operacional:

```bash
pip install flask pyserial mpremote
