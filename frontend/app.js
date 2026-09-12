let me = JSON.parse(localStorage.getItem("hearth_device") || "null");
let devices = [];
let onlineIds = new Set();
let currentPeerId = null;
let socket = null;

function authHeaders() {
  return { Authorization: `Bearer ${me.token}` };
}

function promptRequired(message) {
  let value = "";
  while (!value) value = (prompt(message) || "").trim();
  return value;
}

async function registerDevice() {
  const name = promptRequired("Your device name (e.g. \"Rakesh's laptop\")");
  const pairingCode = promptRequired("Pairing code (ask whoever runs Hearth for one)");
  const res = await fetch("/devices", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, pairing_code: pairingCode }),
  });
  if (!res.ok) {
    alert("Registration failed: " + (await res.json()).detail);
    throw new Error("registration failed");
  }
  me = await res.json();
  localStorage.setItem("hearth_device", JSON.stringify(me));
}

async function loadDevices() {
  const res = await fetch("/devices", { headers: authHeaders() });
  devices = await res.json();
  renderDeviceList();
}

function renderDeviceList() {
  const list = document.getElementById("device-list");
  list.innerHTML = "";
  for (const d of devices) {
    const online = onlineIds.has(d.id);
    const li = document.createElement("li");
    li.className = "device" + (d.id === currentPeerId ? " active" : "");
    const dot = document.createElement("span");
    dot.className = "dot " + (online ? "online" : "offline");
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = d.name;
    const lastSeen = document.createElement("span");
    lastSeen.className = "last-seen";
    lastSeen.textContent = online ? "online" : lastSeenLabel(d.last_seen_at);
    li.append(dot, name, lastSeen);
    li.addEventListener("click", () => openThread(d.id));
    list.appendChild(li);
  }
}

function lastSeenLabel(iso) {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

async function openThread(deviceId) {
  currentPeerId = deviceId;
  renderDeviceList();
  const peer = devices.find((d) => d.id === deviceId);
  document.getElementById("chat-header").textContent = peer ? peer.name : "";
  document.getElementById("message-input").disabled = false;
  document.querySelector("#send-form button").disabled = false;

  const res = await fetch(`/messages/${deviceId}`, { headers: authHeaders() });
  const messages = await res.json();
  const thread = document.getElementById("thread");
  thread.innerHTML = "";
  for (const m of messages) appendMessage(m);
}

function appendMessage(m) {
  const thread = document.getElementById("thread");
  const div = document.createElement("div");
  div.className = "message " + (m.sender_device_id === me.id ? "sent" : "received");
  if (m.kind === "text") {
    div.textContent = m.body;
  } else {
    const link = document.createElement("a");
    link.href = "#";
    link.textContent = "📎 " + (m.filename || "file");
    link.addEventListener("click", (e) => {
      e.preventDefault();
      downloadFile(m.file_id, m.filename);
    });
    div.appendChild(link);
  }
  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;
}

async function downloadFile(fileId, filename) {
  const res = await fetch(`/files/${fileId}`, { headers: authHeaders() });
  if (!res.ok) {
    alert("Download failed");
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "file";
  a.click();
  URL.revokeObjectURL(url);
}

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${proto}//${location.host}/ws`);
  let authed = false;

  socket.onopen = () => {
    authed = false;
    socket.send(JSON.stringify({ type: "auth", token: me.token }));
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "presence") {
      if (!authed) {
        authed = true;
        if (currentPeerId) openThread(currentPeerId);
      }
      onlineIds = new Set(data.online_device_ids);
      renderDeviceList();
    } else if (data.type === "message") {
      if (data.sender_device_id === currentPeerId || data.recipient_device_id === currentPeerId) {
        appendMessage(data);
      }
      if (data.recipient_device_id === me.id) notify(data);
      loadDevices();
    }
  };
  socket.onclose = () => setTimeout(connectWebSocket, 2000);
}

function notify(message) {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  if (!document.hidden) return;
  const sender = devices.find((d) => d.id === message.sender_device_id);
  new Notification(sender ? sender.name : "Hearth", {
    body: message.kind === "text" ? message.body : `Sent a file: ${message.filename || ""}`,
  });
}

document.getElementById("send-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!currentPeerId) return;
  const input = document.getElementById("message-input");
  const fileInput = document.getElementById("file-input");

  if (fileInput.files.length > 0) {
    const form = new FormData();
    form.append("recipient_device_id", currentPeerId);
    form.append("file", fileInput.files[0]);
    const res = await fetch("/files", { method: "POST", headers: authHeaders(), body: form });
    if (res.ok) appendMessage(await res.json());
    else alert("Upload failed: " + (await res.json()).detail);
    fileInput.value = "";
  } else if (input.value.trim()) {
    const res = await fetch("/messages", {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ recipient_device_id: currentPeerId, body: input.value.trim() }),
    });
    if (res.ok) appendMessage(await res.json());
    input.value = "";
  }
});

document.getElementById("file-input").addEventListener("change", () => {
  document.getElementById("send-form").requestSubmit();
});

document.getElementById("remove-device-btn").addEventListener("click", async () => {
  if (!confirm("Remove this device? You'll need a new pairing code to use Hearth again here.")) return;
  await fetch(`/devices/${me.id}`, { method: "DELETE", headers: authHeaders() });
  localStorage.removeItem("hearth_device");
  location.reload();
});

async function checkStorage() {
  const res = await fetch("/storage", { headers: authHeaders() });
  const status = await res.json();
  const banner = document.getElementById("storage-warning");
  if (status.warn) {
    banner.textContent = `Storage is ${Math.round(status.used_ratio * 100)}% full -- ask whoever runs Hearth to free up space or raise the limit.`;
    banner.hidden = false;
  } else {
    banner.hidden = true;
  }
}

async function main() {
  if (!me) await registerDevice();
  document.getElementById("me").textContent = `You: ${me.name}`;
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
  await loadDevices();
  await checkStorage();
  connectWebSocket();
}

main();
