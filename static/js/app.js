let debounceTimeout = null;
let dispositivosAnteriores = new Set();
const socket = io();
let internetEnabled = false;
let aulaStartTime = null;
let aulaEndTime = null;
let temposConexao = {};
let tempoAulaInterval = null;
let isDragging = false;
let selectedDevice = null;
let selectedLine = null;
let startPos = { x: 0, y: 0 };
let devicePositions = {};

function setLoading(id, loading) {
  const element = document.getElementById(id);
  const loadingElement = document.getElementById('loading' + id);
  
  if (!element || !loadingElement) {
    console.warn(`Loading elements not found for id: ${id}`);
    return;
  }

  if (loading) {
    element.classList.add('disabled');
    loadingElement.classList.add('visible');
  } else {
    element.classList.remove('disabled');
    loadingElement.classList.remove('visible');
  }
}

function showNotification(message, type = 'disconnect') {
  const notification = document.getElementById('notification');
  notification.textContent = message;
  notification.style.display = 'block';
  notification.dataset.type = type;  // Set notification type
  
  const audioElement = document.getElementById('notificationSound');
  if (audioElement) {
    audioElement.currentTime = 0;
    
    // Try to play with user interaction check
    if (document.hasFocus()) {
      audioElement.play().catch(err => {
        if (err.name === 'NotAllowedError') {
          // Create and show a play button if autoplay is blocked
          const playButton = document.createElement('button');
          playButton.textContent = '🔔';
          playButton.className = 'notification-play';
          playButton.onclick = () => {
            audioElement.play();
            playButton.remove();
          };
          notification.appendChild(playButton);
        }
      });
    }
  }
  
  setTimeout(() => {
    notification.style.display = 'none';
  }, 5000);
}

function salvarApelido(mac) {
  const input = document.getElementById("apelido-" + mac);
  const apelido = input.value;
  input.classList.add('disabled');
  
  if (debounceTimeout) {
    clearTimeout(debounceTimeout);
  }
  
  debounceTimeout = setTimeout(() => {
    fetch("/api/apelido", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mac: mac, apelido: apelido })
    })
    .finally(() => {
      input.classList.remove('disabled');
    });
  }, 2000); // Aumentado para 2 segundos
}

function deletarDispositivo(mac) {
  if (confirm(`Deseja realmente excluir este dispositivo?`)) {
    fetch("/api/apelido/deletar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mac: mac })
    }).then(() => carregarDispositivos());
  }
}

function formatOfflineTime(seconds) {
  if (!seconds) return '';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return `${hours}h ${minutes}m ${secs}s`;
}

function formatTime(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return `${hours}h ${minutes}m ${secs}s`;
}

function criarLinha(dispositivo) {
  const tr = document.createElement("tr");
  tr.className = 'device-row';
  
  const tdStatus = document.createElement("td");
  tdStatus.className = 'cell-icon';
  const statusIndicator = document.createElement("span");
  statusIndicator.className = `status-indicator status-${dispositivo.status || 'offline'}`;
  tdStatus.appendChild(statusIndicator);
  
  const tdMac = document.createElement("td");
  tdMac.textContent = dispositivo.mac;
  
  const tdInput = document.createElement("td");
  const input = document.createElement("input");
  input.type = "text";
  input.value = dispositivo.nome || "";
  input.id = "apelido-" + dispositivo.mac;
  input.placeholder = "Digite um apelido...";
  input.autocomplete = "off";
  input.readOnly = true;
  tdInput.appendChild(input);
  
  tr.onclick = function(e) {
    if (e.target.tagName.toLowerCase() === 'input' && !input.readOnly) return;
    
    // Remove previous active row
    document.querySelectorAll('.device-row').forEach(row => {
      row.classList.remove('active');
    });
    
    // Activate current row
    tr.classList.add('active');
    
    // Show actions menu
    const rect = tr.getBoundingClientRect();
    showActionsMenu(dispositivo.mac, rect);
  };
  
  tr.appendChild(tdStatus);
  
  if (dispositivo.status === 'online') {
    const tdIp = document.createElement("td");
    tdIp.textContent = dispositivo.ip;
    tr.appendChild(tdIp);
    tr.appendChild(tdMac);
    tr.appendChild(tdInput);
  } else {
    const tdOfflineTime = document.createElement("td");
    tdOfflineTime.innerHTML = `
        Atual: ${formatOfflineTime(dispositivo.offline_time)}<br>
        Total: ${dispositivo.total_offline}
    `;
    tdOfflineTime.className = 'offline-time';
    
    tr.appendChild(tdMac);
    tr.appendChild(tdInput);
    tr.appendChild(tdOfflineTime);
  }
  
  return tr;
}

function showActionsMenu(mac, rect) {
  let menu = document.getElementById('deviceActionsMenu');
  if (!menu) {
    menu = document.createElement('div');
    menu.id = 'deviceActionsMenu';
    menu.className = 'actions-menu';
    document.body.appendChild(menu);
  }
  
  menu.innerHTML = `
    <div class="action-item" onclick="event.stopPropagation(); editDevice('${mac}')">
      <span class="action-icon">✏️</span> Editar
    </div>
    <div class="action-item" onclick="event.stopPropagation(); deletarDispositivo('${mac}')">
      <span class="action-icon">🗑️</span> Deletar
    </div>
  `;
  
  menu.style.display = 'block';
  menu.style.top = `${rect.bottom + window.scrollY}px`;
  menu.style.left = `${rect.left}px`;
  
  // Close menu when clicking outside
  document.addEventListener('click', function closeMenu(e) {
    if (!menu.contains(e.target) && !e.target.closest('.device-row')) {
      menu.style.display = 'none';
      document.removeEventListener('click', closeMenu);
    }
  });
}

function editDevice(mac) {
  const input = document.getElementById('apelido-' + mac);
  if (!input) return;
  
  input.readOnly = false;
  input.focus();
  
  // Remove previous event listener
  const newInput = input.cloneNode(true);
  input.parentNode.replaceChild(newInput, input);
  
  // Add new event listeners
  newInput.addEventListener('blur', function() {
    newInput.readOnly = true;
    if (newInput.value !== newInput.defaultValue) {
      salvarApelido(mac);
    }
  });
  
  newInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
      newInput.blur();
    }
  });
  
  // Close the menu
  const menu = document.getElementById('deviceActionsMenu');
  if (menu) menu.style.display = 'none';
}

function updateDeviceTime(device) {
  if (!aulaStartTime || !temposConexao[device.mac]) return;
  
  const tempo = temposConexao[device.mac];
  const now = Date.now();
  
  if (device.status === 'online') {
    if (!tempo.startTime) {
      tempo.startTime = now;
    }
    // Atualiza tempo total enquanto estiver online
    tempo.totalTime = ((now - tempo.startTime) / 1000) + (tempo.previousTime || 0);
  } else if (tempo.startTime) {
    // Salva o tempo acumulado quando desconecta
    tempo.previousTime = (tempo.previousTime || 0) + ((now - tempo.startTime) / 1000);
    tempo.startTime = null;
    tempo.totalTime = tempo.previousTime;
  }
}

function carregarDispositivos() {
  setLoading('tabela', true);
  fetch("/api/dispositivos")
    .then(res => res.json())
    .then(dispositivos => {
      const tabelaConectados = document.getElementById("tabelaConectados");
      const tabelaDesconectados = document.getElementById("tabelaDesconectados");
      const contadorOnline = document.getElementById("contadorOnline");
      const contadorOffline = document.getElementById("contadorOffline");
      
      if (!tabelaConectados || !tabelaDesconectados || !contadorOnline || !contadorOffline) {
        console.error("Elementos necessários não encontrados");
        return;
      }

      // Verifica dispositivos que desconectaram
      const dispositivosAtuais = new Set(
        dispositivos
          .filter(d => d.status === 'online')
          .map(d => d.mac)
      );
      
      dispositivosAnteriores.forEach(mac => {
        if (!dispositivosAtuais.has(mac)) {
          const dispositivo = dispositivos.find(d => d.mac === mac);
          if (dispositivo) {
            showNotification(`${dispositivo.nome} desconectou!`);
          }
        }
      });

      // Verifica dispositivos que conectaram
      dispositivosAtuais.forEach(mac => {
        if (!dispositivosAnteriores.has(mac)) {
          const dispositivo = dispositivos.find(d => d.mac === mac);
          if (dispositivo) {
            showNotification(`${dispositivo.nome} conectou!`, 'connect');
            const connectSound = document.getElementById('connectSound');
            if (connectSound) {
              connectSound.currentTime = 0;
              connectSound.play().catch(() => {/* Ignora erros de autoplay */});
            }
          }
        }
      });

      dispositivosAnteriores = dispositivosAtuais;

      tabelaConectados.innerHTML = "";
      tabelaDesconectados.innerHTML = "";
      
      dispositivos.forEach(dispositivo => {
        if (aulaStartTime) {
          updateDeviceTime(dispositivo);
        }
        if (dispositivo.status === 'online') {
          tabelaConectados.appendChild(criarLinha(dispositivo));
        } else {
          tabelaDesconectados.appendChild(criarLinha(dispositivo));
        }
      });
      
      const onlineDevices = dispositivos.filter(d => d.status === 'online');
      const offlineDevices = dispositivos.filter(d => d.status === 'offline');
      
      contadorOnline.textContent = onlineDevices.length;
      contadorOffline.textContent = offlineDevices.length;
    })
    .then(() => {
      if (document.getElementById('networkView').style.display === 'block') {
        updateNetworkView();
      }
    })
    .finally(() => {
      setLoading('tabela', false);
    });
}

// Move functions to window object
window.ativar = function() {
  setLoading('btnAtivar', true);
  fetch("/api/ativar")
    .then(res => res.json())
    .then(data => {
      console.log("Hotspot activated:", data);
      setTimeout(carregarDispositivos, 2000);
    })
    .catch(err => {
      console.error("Error activating hotspot:", err);
    })
    .finally(() => {
      setLoading('btnAtivar', false);
    });
};

window.desativar = function() {
  setLoading('btnDesativar', true);
  document.body.classList.add('disabled');
  fetch("/api/desativar")
    .then(res => res.json())
    .then(data => {
      console.log("Hotspot deactivated:", data);
      setTimeout(carregarDispositivos, 2000);
    })
    .catch(err => {
      console.error("Error deactivating hotspot:", err);
    })
    .finally(() => {
      setLoading('btnDesativar', false);
      document.body.classList.remove('disabled');
    });
};

function toggleInternet() {
  setLoading('btnInternet', true);
  fetch("/api/internet", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enable: !internetEnabled })
  })
  .then(() => {
    internetEnabled = !internetEnabled;
    const btn = document.getElementById('btnInternet');
    btn.textContent = `Internet: ${internetEnabled ? 'Ativada' : 'Desativada'}`;
    btn.classList.toggle('active', internetEnabled);
  })
  .finally(() => {
    setLoading('btnInternet', false);
  });
}

function loadInternetStatus() {
  fetch("/api/internet/status")
    .then(res => res.json())
    .then(data => {
      internetEnabled = data.enabled;
      const btn = document.getElementById('btnInternet');
      btn.textContent = `Internet: ${internetEnabled ? 'Ativada' : 'Desativada'}`;
      btn.classList.toggle('active', internetEnabled);
    });
}

// Define toggleSection in global scope
function toggleSection(sectionId) {
  const section = document.getElementById(sectionId);
  const icon = section.previousElementSibling.querySelector('.toggle-icon');
  
  if (section && icon) {
    section.classList.toggle('collapsed');
    icon.classList.toggle('collapsed');
  }
}

function filterDevices(searchTerm) {
  const rows = document.querySelectorAll('tr');
  searchTerm = searchTerm.toLowerCase();
  
  rows.forEach(row => {
    const apelido = row.querySelector('input')?.value.toLowerCase() || '';
    const mac = row.querySelector('td:nth-child(2)')?.textContent.toLowerCase() || '';
    
    if (apelido.includes(searchTerm) || mac.includes(searchTerm)) {
      row.classList.remove('hidden');
    } else {
      row.classList.add('hidden');
    }
  });
}

function updateTempoAula() {
    if (!aulaStartTime) return;
    
    const now = Date.now();
    const tempoDecorrido = Math.floor((now - aulaStartTime) / 1000);
    const tempoElement = document.getElementById('tempoAula');
    
    if (tempoElement) {
        tempoElement.textContent = `Tempo decorrido: ${formatTime(tempoDecorrido)}`;
        tempoElement.classList.add('visible');
    }
}

function iniciarAula() {
    fetch("/api/aula/iniciar", {
        method: "POST",
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'error') {
            throw new Error(data.mensagem);
        }
        console.log("Aula iniciada:", data);
        aulaStartTime = Date.now();
        document.getElementById('btnIniciarAula').disabled = true;
        document.getElementById('btnFinalizarAula').disabled = false;
        document.getElementById('tempoAula').classList.add('visible');
        temposConexao = {};
        
        // Inicia o contador de tempo
        if (tempoAulaInterval) clearInterval(tempoAulaInterval);
        tempoAulaInterval = setInterval(updateTempoAula, 1000);
        
        carregarDispositivos();
    })
    .catch(error => {
        console.error("Erro ao iniciar aula:", error);
        alert(`Erro ao iniciar aula: ${error.message}`);
    });
}

function finalizarAula() {
    const modal = document.getElementById('reportModal');
    modal.style.display = 'block';
    
    // Stop the timer but keep displaying it
    if (tempoAulaInterval) {
        clearInterval(tempoAulaInterval);
        tempoAulaInterval = null;
    }
}

function closeReportModal() {
  const modal = document.getElementById('reportModal');
  const reportContent = document.getElementById('reportContent');
  modal.style.display = 'none';
  reportContent.style.display = 'none';
}

function cancelReport() {
    // Don't reset the timer if user cancels
    const tempoElement = document.getElementById('tempoAula');
    if (!tempoAulaInterval && aulaStartTime) {
        // Restart the timer if it was stopped
        tempoAulaInterval = setInterval(updateTempoAula, 1000);
    }
    closeReportModal();
}

function showReport() {
    if (tempoAulaInterval) {
        clearInterval(tempoAulaInterval);
        tempoAulaInterval = null;
    }
    
    const reportBody = document.getElementById('reportBody');
    const reportContent = document.getElementById('reportContent');
    const modal = document.getElementById('reportModal');

    // Clear previous content
    reportBody.innerHTML = '';
    reportContent.style.display = 'none';

    fetch("/api/aula/finalizar", {
        method: "POST",
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        console.log("Dados do relatório:", data);

        if (!data.resultados || !Array.isArray(data.resultados)) {
            reportBody.innerHTML = '<tr><td colspan="4">Erro ao carregar dados do relatório</td></tr>';
            reportContent.style.display = 'block';
            return;
        }

        if (data.resultados.length === 0) {
            reportBody.innerHTML = '<tr><td colspan="4">Nenhum dado registrado para esta aula</td></tr>';
            reportContent.style.display = 'block';
            return;
        }

        data.resultados.forEach((aluno, index) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${index + 1}º - ${aluno.nome || 'Desconhecido'}</td>
                <td>
                    ${formatTime(Math.round(aluno.tempo_conectado))}<br>
                    <small class="text-muted">Desconectado: ${formatTime(Math.round(aluno.tempo_desconectado))}</small>
                </td>
                <td>${aluno.percentual.toFixed(1)}%</td>
                <td>${aluno.nota.toFixed(1)}</td>
            `;
            reportBody.appendChild(tr);
            console.log(`Linha adicionada para ${aluno.nome}`);
        });

        // Show report content
        reportContent.style.display = 'block';
        modal.style.display = 'block';
        
        console.log("Relatório gerado com sucesso:", {
            rows: reportBody.children.length,
            visible: reportContent.style.display,
            modalVisible: modal.style.display
        });
    })
    .catch(error => {
        console.error("Erro ao gerar relatório:", error);
        alert(`Erro ao gerar relatório: ${error.message}`);
        closeReportModal();
    });
}

function resetAula() {
    document.getElementById('btnIniciarAula').disabled = false;
    document.getElementById('btnFinalizarAula').disabled = true;
    const tempoElement = document.getElementById('tempoAula');
    tempoElement.textContent = 'Tempo decorrido: 0h 0m 0s';
    tempoElement.classList.remove('visible');
    aulaStartTime = null;
    aulaEndTime = null;
    temposConexao = {};
    
    if (tempoAulaInterval) {
        clearInterval(tempoAulaInterval);
        tempoAulaInterval = null;
    }
    
    // Reset offline times in the interface
    const allDevices = document.querySelectorAll('tr');
    allDevices.forEach(tr => {
        const offlineTimeCell = tr.querySelector('.offline-time');
        if (offlineTimeCell) {
            offlineTimeCell.innerHTML = `
                Atual: 0h 0m 0s<br>
                Total: 0h 0m 0s
            `;
        }
    });
}

// Close modal when clicking outside
window.onclick = function(event) {
  const modal = document.getElementById('reportModal');
  if (event.target === modal) {
    closeReportModal();
  }
}

// Event listener para atualizações de status
socket.on('devices_update', function(devices) {
    if (!aulaStartTime) return; // Se a aula terminou, não atualiza mais
  
    devices.forEach(device => {
        if (!temposConexao[device.mac]) {
            temposConexao[device.mac] = { startTime: null, totalTime: 0 };
        }
        
        const tempo = temposConexao[device.mac];
        
        if (device.status === 'online') {
            if (!tempo.startTime) {
                tempo.startTime = Date.now();
            }
        } else if (tempo.startTime) {
            tempo.totalTime += (Date.now() - tempo.startTime) / 1000;
            tempo.startTime = null;
        }
    });
});

function updateConnectionLines() {
  const container = document.getElementById('networkView');
  const serverNode = document.querySelector('.server-node');
  
  container.querySelectorAll('.connection-line').forEach(line => {
    const deviceMac = line.dataset.deviceMac;
    const deviceNode = container.querySelector(`.device-node[data-mac="${deviceMac}"]`);
    
    if (deviceNode) {
      const serverRect = serverNode.getBoundingClientRect();
      const deviceRect = deviceNode.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();
      
      const startX = serverRect.left + serverRect.width/2 - containerRect.left;
      const startY = serverRect.top + serverRect.height/2 - containerRect.top;
      const endX = deviceRect.left + deviceRect.width/2 - containerRect.left;
      const endY = deviceRect.top + deviceRect.height/2 - containerRect.top;
      
      const length = Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2));
      const angle = Math.atan2(endY - startY, endX - startX);
      
      line.style.width = `${length}px`;
      line.style.left = `${startX}px`;
      line.style.top = `${startY}px`;
      line.style.transform = `rotate(${angle}rad)`;
    }
  });
}

function updateNetworkView() {
  const container = document.getElementById('networkView');
  const devicesContainer = document.getElementById('networkDevices');
  const serverNode = document.querySelector('.server-node');
  
  devicesContainer.innerHTML = '';
  container.querySelectorAll('.connection-line').forEach(line => line.remove());
  
  const devices = Array.from(document.querySelectorAll('#tabelaConectados tr, #tabelaDesconectados tr'));
  
  devices.forEach((device, index) => {
    const mac = device.querySelector('td:nth-child(2)').textContent;
    const nome = device.querySelector('input').value || 'Desconhecido';
    const status = device.closest('#tabelaConectados') ? 'online' : 'offline';
    
    const deviceNode = document.createElement('div');
    deviceNode.className = 'device-node';
    deviceNode.dataset.mac = mac;
    deviceNode.innerHTML = `
      <span class="phone-icon">📱</span>
      <span class="device-label">${nome}</span>
      <span class="device-status ${status}"></span>
      <div class="connection-handle start"></div>
      <div class="connection-handle end"></div>
    `;
    
    // Apply saved position or calculate new one
    const position = devicePositions[mac] || {
      x: 100 + (index * 150) % (container.offsetWidth - 200),
      y: 150 + Math.floor(index / 3) * 100
    };
    
    deviceNode.style.left = `${position.x}px`;
    deviceNode.style.top = `${position.y}px`;
    
    devicesContainer.appendChild(deviceNode);
    
    const line = document.createElement('div');
    line.className = `connection-line ${status}`;
    line.dataset.deviceMac = mac;
    container.appendChild(line);
  });
  
  updateConnectionLines();
}

function initDragAndDrop() {
  const networkView = document.getElementById('networkView');
  
  networkView.addEventListener('mousedown', startDragging);
  networkView.addEventListener('mousemove', handleDrag);
  networkView.addEventListener('mouseup', stopDragging);
  networkView.addEventListener('mouseleave', stopDragging);
}

function startDragging(e) {
  const deviceNode = e.target.closest('.device-node');
  const line = e.target.closest('.connection-line');
  
  if (deviceNode) {
    isDragging = true;
    selectedDevice = deviceNode;
    selectedDevice.classList.add('dragging');
    
    const rect = selectedDevice.getBoundingClientRect();
    startPos = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  } else if (line) {
    selectedLine = line;
    line.classList.add('selected');
  }
}

function handleDrag(e) {
  if (!isDragging || !selectedDevice) return;
  
  const networkRect = document.getElementById('networkView').getBoundingClientRect();
  let newX = e.clientX - networkRect.left - startPos.x;
  let newY = e.clientY - networkRect.top - startPos.y;
  
  // Keep device within bounds
  newX = Math.max(0, Math.min(newX, networkRect.width - selectedDevice.offsetWidth));
  newY = Math.max(0, Math.min(newY, networkRect.height - selectedDevice.offsetHeight));
  
  selectedDevice.style.left = `${newX}px`;
  selectedDevice.style.top = `${newY}px`;
  
  // Save position
  const mac = selectedDevice.dataset.mac;
  devicePositions[mac] = { x: newX, y: newY };
  
  // Update connection lines
  updateConnectionLines();
}

function stopDragging() {
  if (selectedDevice) {
    selectedDevice.classList.remove('dragging');
    selectedDevice = null;
  }
  if (selectedLine) {
    selectedLine.classList.remove('selected');
    selectedLine = null;
  }
  isDragging = false;
}

// Initialize on load
window.onload = function() {
  carregarDispositivos();
  setInterval(carregarDispositivos, 3000);
  
  const searchInput = document.getElementById('searchDevices');
  searchInput.addEventListener('input', (e) => {
    filterDevices(e.target.value);
  });
  
  // Initialize sections
  document.querySelectorAll('.section-content').forEach(section => {
    section.classList.remove('collapsed');
  });
  
  // Add button event listeners
  document.getElementById('btnIniciarAula').addEventListener('click', iniciarAula);
  document.getElementById('btnFinalizarAula').addEventListener('click', finalizarAula);
  
  document.querySelectorAll('.view-toggle').forEach(button => {
    button.addEventListener('click', () => {
      const view = button.dataset.view;
      document.querySelectorAll('.view-toggle').forEach(b => b.classList.remove('active'));
      button.classList.add('active');
      
      if (view === 'network') {
        document.getElementById('networkView').style.display = 'block';
        document.getElementById('tableView').style.display = 'none';
        updateNetworkView();
        initDragAndDrop();
      } else {
        document.getElementById('networkView').style.display = 'none';
        document.getElementById('tableView').style.display = 'block';
      }
    });
  });
  
  console.log("App initialized");
};