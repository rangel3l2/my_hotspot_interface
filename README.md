# 🛜 Hotspot Manager

Uma interface gráfica web para gerenciar o Hotspot do Windows, monitorar dispositivos conectados e receber notificações em tempo real.

## 📋 Funcionalidades

- Ativar/Desativar Hotspot do Windows
- Monitoramento em tempo real dos dispositivos conectados
- Notificações sonoras quando dispositivos conectam/desconectam
- Atribuir apelidos para dispositivos
- Interface intuitiva e responsiva
- Separação entre dispositivos online e offline
- Indicadores visuais de status (verde para online, vermelho para offline)

## 🚀 Como Instalar

1. Certifique-se de ter Python 3.8+ instalado
2. Clone este repositório:
```bash
git clone https://github.com/seu-usuario/my_hotspot_interface.git
cd my_hotspot_interface
```

3. Crie um ambiente virtual:
```bash
python -m venv venv
```

4. Ative o ambiente virtual:
- Windows:
```bash
venv\Scripts\activate
```
- Linux/Mac:
```bash
source venv/bin/activate
```

5. Instale as dependências:
```bash
pip install -r requirements.txt
```

## 💻 Como Usar

1. Execute o aplicativo:
```bash
python app.py
```

2. Abra seu navegador e acesse:
```
http://localhost:5000
```

3. Use os botões na interface para:
- Ativar/Desativar o Hotspot
- Ver dispositivos conectados
- Atribuir apelidos aos dispositivos
- Monitorar status em tempo real

## 🔧 Requisitos

### Windows 10/11
- Python 3.8 ou superior
- Adaptador WiFi com suporte a Hosted Network
- Permissões de administrador

### macOS
- Python 3.8 ou superior
- Permissões de administrador
- Command Line Tools instalado

### Linux
- Python 3.8 ou superior
- NetworkManager
- Permissões de administrador (sudo)
- Adaptador WiFi compatível

## 🔑 Configurações Padrão

- SSID: MeuHotspot
- Senha: 12345678
- Porta: 5000
- Intervalo de atualização: 1 segundo

## 🛠️ Tecnologias Utilizadas

- Flask: Framework web
- Flask-SocketIO: Comunicação em tempo real
- JavaScript: Frontend interativo
- WebSockets: Atualizações em tempo real
- Windows Netsh: Gerenciamento do Hotspot

## 📝 Notas

- Execute o aplicativo como administrador para ter acesso completo às funcionalidades
- Certifique-se de que seu adaptador WiFi suporta Hosted Network
- Os apelidos dos dispositivos são salvos localmente em `apelidos.json`

## 🤝 Contribuindo

1. Faça um Fork do projeto
2. Crie sua Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a Branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 👥 Autores

* **Seu Nome** - *Trabalho Inicial* - [SeuUsuario](https://github.com/SeuUsuario)

---
⌨️ com ❤️ por [SeuNome](https://github.com/SeuUsuario)
