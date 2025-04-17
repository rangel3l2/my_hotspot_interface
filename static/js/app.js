let debounceTimeout = null;
let dispositivosAnteriores = new Set();
const socket = io();

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

function showNotification(message) {
  const notification = document.getElementById('notification');
  notification.textContent = message;
  notification.style.display = 'block';
  
  const audioElement = document.getElementById('notificationSound');
  if (audioElement) {
    audioElement.currentTime = 0; // Reset audio to start
    audioElement.play().catch(err => console.log('Error playing notification:', err));
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
  }, 1000);
}

function criarLinha(dispositivo) {
  const tr = document.createElement("tr");
  
  const tdStatus = document.createElement("td");
  const statusIndicator = document.createElement("span");
  statusIndicator.className = `status-indicator status-${dispositivo.status || 'offline'}`;
  tdStatus.appendChild(statusIndicator);
  
  const tdMac = document.createElement("td");
  tdMac.textContent = dispositivo.mac;
  
  const tdInput = document.createElement("td");
  const input = document.createElement("input");
  input.type = "text";
  input.value = dispositivo.nome;
  input.id = "apelido-" + dispositivo.mac;
  input.addEventListener('input', () => salvarApelido(dispositivo.mac));
  tdInput.appendChild(input);
  
  tr.appendChild(tdStatus);
  if (dispositivo.status === 'online') {
    const tdIp = document.createElement("td");
    tdIp.textContent = dispositivo.ip;
    tr.appendChild(tdIp);
  }
  tr.appendChild(tdMac);
  tr.appendChild(tdInput);
  
  return tr;
}

function carregarDispositivos() {
  setLoading('tabela', true);
  fetch("/api/dispositivos")
    .then(res => res.json())
    .then(dispositivos => {
      const tabelaConectados = document.getElementById("tabelaConectados");
      const tabelaDesconectados = document.getElementById("tabelaDesconectados");
      const contador = document.getElementById("contador");
      
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
      dispositivosAnteriores = dispositivosAtuais;

      tabelaConectados.innerHTML = "";
      tabelaDesconectados.innerHTML = "";
      
      dispositivos.forEach(dispositivo => {
        if (dispositivo.status === 'online') {
          tabelaConectados.appendChild(criarLinha(dispositivo));
        } else {
          tabelaDesconectados.appendChild(criarLinha(dispositivo));
        }
      });
      
      contador.textContent = dispositivos.filter(d => d.status === 'online').length;
    })
    .finally(() => {
      setLoading('tabela', false);
    });
}

function ativar() {
  setLoading('btnAtivar', true);
  fetch("/api/ativar")
    .then(() => carregarDispositivos())
    .finally(() => {
      setLoading('btnAtivar', false);
    });
}

function desativar() {
  setLoading('btnDesativar', true);
  document.body.classList.add('disabled');
  fetch("/api/desativar")
    .then(() => carregarDispositivos())
    .finally(() => {
      setLoading('btnDesativar', false);
      document.body.classList.remove('disabled');
    });
}

// Modal controls
const modal = document.getElementById("aboutModal");
const btn = document.getElementById("btnSobre");
const span = document.getElementsByClassName("close")[0];

btn.onclick = function() {
  modal.style.display = "block";
}

span.onclick = function() {
  modal.style.display = "none";
}

window.onclick = function(event) {
  if (event.target == modal) {
    modal.style.display = "none";
  }
}

socket.on('devices_update', function(dispositivos) {
  const tabelaConectados = document.getElementById("tabelaConectados");
  const tabelaDesconectados = document.getElementById("tabelaDesconectados");
  const contador = document.getElementById("contador");
  
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
  dispositivosAnteriores = dispositivosAtuais;

  tabelaConectados.innerHTML = "";
  tabelaDesconectados.innerHTML = "";
  
  dispositivos.forEach(dispositivo => {
    if (dispositivo.status === 'online') {
      tabelaConectados.appendChild(criarLinha(dispositivo));
    } else {
      tabelaDesconectados.appendChild(criarLinha(dispositivo));
    }
  });
  
  contador.textContent = dispositivos.filter(d => d.status === 'online').length;
});

// Remove o setInterval pois agora usamos WebSocket
window.onload = carregarDispositivos; // Carrega inicial