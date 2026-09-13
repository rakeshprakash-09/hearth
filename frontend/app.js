let me = JSON.parse(localStorage.getItem("hearth_device") || "null");
let devices = [];
let onlineIds = new Set();
let currentPeerId = null;
let socket = null;
let lastDividerDate = null;

const AVATAR_COLORS = ["#3358e0", "#7451c9", "#c9548b", "#3f9563", "#b8860b", "#2f8f9d"];

function initials(name) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function avatarColor(id) {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

function makeAvatar(device, online) {
  const avatar = document.createElement("span");
  avatar.className = "avatar";
  avatar.style.setProperty("--avatar-bg", avatarColor(device.id));
  avatar.textContent = initials(device.name);
  const dot = document.createElement("span");
  dot.className = "dot" + (online ? " online" : "");
  avatar.appendChild(dot);
  return avatar;
}

function dayLabel(iso) {
  const d = new Date(iso);
  const now = new Date();
  const startOf = (dt) => new Date(dt.getFullYear(), dt.getMonth(), dt.getDate());
  const diffDays = Math.round((startOf(now) - startOf(d)) / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: d.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
}

function timeLabel(iso) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function extLabel(filename) {
  const ext = (filename || "").split(".").pop();
  return ext && ext !== filename ? ext.slice(0, 4).toUpperCase() : "FILE";
}

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
    const meta = document.createElement("span");
    meta.className = "meta";
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = d.name;
    const lastSeen = document.createElement("div");
    lastSeen.className = "last-seen";
    lastSeen.textContent = online ? "online" : lastSeenLabel(d.last_seen_at);
    meta.append(name, lastSeen);
    li.append(makeAvatar(d, online), meta);
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

function renderChatHeader() {
  const peer = devices.find((d) => d.id === currentPeerId);
  if (!peer) return;
  const header = document.getElementById("chat-header");
  header.innerHTML = "";
  const online = onlineIds.has(peer.id);
  const titleWrap = document.createElement("div");
  const title = document.createElement("div");
  title.className = "title";
  title.textContent = peer.name;
  const sub = document.createElement("div");
  sub.className = "sub";
  sub.textContent = online ? "online" : lastSeenLabel(peer.last_seen_at);
  titleWrap.append(title, sub);
  header.append(makeAvatar(peer, online), titleWrap);
}

async function openThread(deviceId) {
  currentPeerId = deviceId;
  lastDividerDate = null;
  renderDeviceList();
  renderChatHeader();
  document.getElementById("message-input").disabled = false;
  document.querySelector("#send-form button").disabled = false;

  const res = await fetch(`/messages/${deviceId}`, { headers: authHeaders() });
  const messages = await res.json();
  const thread = document.getElementById("thread");
  thread.classList.remove("empty");
  thread.innerHTML = "";
  if (messages.length === 0) showEmptyThread();
  else for (const m of messages) appendMessage(m);
}

function showEmptyThread() {
  const thread = document.getElementById("thread");
  thread.classList.add("empty");
  thread.innerHTML =
    '<svg width="40" height="40" viewBox="0 0 32 32" fill="none" aria-hidden="true">' +
    '<rect width="32" height="32" rx="8.5" fill="var(--bubble-received)"/>' +
    '<path d="M16 8.2L23.5 15v9.1a.9.9 0 0 1-.9.9h-4.1v-6.4a.9.9 0 0 0-.9-.9h-3.2a.9.9 0 0 0-.9.9V25H9.4a.9.9 0 0 1-.9-.9V15L16 8.2z" fill="var(--muted-2)"/>' +
    "</svg><div>No messages yet</div>";
}

function appendMessage(m) {
  const thread = document.getElementById("thread");
  if (thread.classList.contains("empty")) {
    thread.classList.remove("empty");
    thread.innerHTML = "";
    lastDividerDate = null;
  }

  const date = new Date(m.created_at).toDateString();
  if (date !== lastDividerDate) {
    const divider = document.createElement("div");
    divider.className = "day-divider";
    divider.textContent = dayLabel(m.created_at);
    thread.appendChild(divider);
    lastDividerDate = date;
  }

  const sentByMe = m.sender_device_id === me.id;
  const row = document.createElement("div");
  row.className = "msg-row " + (sentByMe ? "sent" : "received");

  const bubble = document.createElement("div");
  bubble.className = "message " + (sentByMe ? "sent" : "received");
  if (m.kind === "text") {
    bubble.textContent = m.body;
  } else {
    const chip = document.createElement("span");
    chip.className = "file-chip";
    const ext = document.createElement("span");
    ext.className = "ext";
    ext.textContent = extLabel(m.filename);
    const link = document.createElement("a");
    link.href = "#";
    link.textContent = m.filename || "file";
    link.addEventListener("click", (e) => {
      e.preventDefault();
      downloadFile(m.file_id, m.filename);
    });
    chip.append(ext, link);
    bubble.appendChild(chip);
  }

  const time = document.createElement("div");
  time.className = "msg-time";
  time.textContent = timeLabel(m.created_at);

  row.append(bubble, time);
  thread.appendChild(row);
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
      renderChatHeader();
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
