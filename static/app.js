const history = [];
let locationContext = null;

const elements = {
  form: document.getElementById("chat-form"),
  input: document.getElementById("message-input"),
  list: document.getElementById("message-list"),
  send: document.getElementById("send-button"),
  status: document.getElementById("status-pill"),
  source: document.getElementById("status-source"),
  locationStatus: document.getElementById("location-status"),
  locationButton: document.getElementById("location-button"),
  habitForm: document.getElementById("habit-form"),
  studyForm: document.getElementById("study-form"),
  financeForm: document.getElementById("finance-form"),
  refreshDashboard: document.getElementById("refresh-dashboard"),
  statHabits: document.getElementById("stat-habits"),
  statStudyToday: document.getElementById("stat-study-today"),
  statMonthBalance: document.getElementById("stat-month-balance"),
  habitList: document.getElementById("habit-list"),
  studyList: document.getElementById("study-list"),
  financeList: document.getElementById("finance-list"),
  prompts: Array.from(document.querySelectorAll("[data-prompt]")),
};

function setStatus(text) {
  elements.status.textContent = text;
}

function setLocationStatus(text) {
  elements.locationStatus.textContent = text;
}

function formatBRL(value) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value || 0));
}

function renderDataList(container, items, renderItem) {
  if (!items.length) {
    container.innerHTML = '<div class="data-item"><strong>Sem dados ainda</strong><span>Cadastre o primeiro item para começar.</span></div>';
    return;
  }
  container.innerHTML = items.map(renderItem).join("");
}

function appendMessage(role, text, meta = "") {
  const wrapper = document.createElement("article");
  wrapper.className = `message ${role}`;

  const roleLabel = document.createElement("div");
  roleLabel.className = "message-role";
  roleLabel.textContent = role === "user" ? "Você" : "Dock";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;

  wrapper.append(roleLabel, bubble);

  if (meta) {
    const metaEl = document.createElement("div");
    metaEl.className = "message-meta";
    metaEl.textContent = meta;
    wrapper.appendChild(metaEl);
  }

  elements.list.appendChild(wrapper);
  elements.list.scrollTop = elements.list.scrollHeight;
}

async function sendMessage(message) {
  const cleanMessage = message.trim();
  if (!cleanMessage) return;

  appendMessage("user", cleanMessage);
  history.push({ role: "user", content: cleanMessage });

  elements.input.value = "";
  elements.send.disabled = true;
  setStatus("Pensando");

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: cleanMessage,
        history,
        location: locationContext,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    appendMessage("dock", data.reply, `${data.source || "sem-source"}${data.model ? ` / ${data.model}` : ""}`);
    history.push({ role: "assistant", content: data.reply });
    elements.source.textContent = data.source || "Backend local";
    setStatus("Pronto");
  } catch (err) {
    appendMessage("dock", "Não consegui completar essa resposta agora. Verifica o backend e tenta de novo.", "erro de conexão");
    setStatus("Falha");
  } finally {
    elements.send.disabled = false;
    elements.input.focus();
  }
}

async function loadDashboard() {
  const response = await fetch("/dashboard");
  if (!response.ok) {
    throw new Error(`dashboard failed: ${response.status}`);
  }
  const data = await response.json();

  elements.statHabits.textContent = String(data.highlights.habit_count || 0);
  elements.statStudyToday.textContent = `${data.highlights.study_today_minutes || 0} min`;
  elements.statMonthBalance.textContent = formatBRL(data.highlights.finance_month_balance || 0);

  renderDataList(elements.habitList, data.habits || [], (item) => `
    <div class="data-item">
      <strong>${item.name}</strong>
      <span>${item.weekly_progress}/${item.target_frequency} ${item.unit} • ${item.completion_rate}%</span>
      <button type="button" class="context-button" data-habit-checkin="${item.id}">Check-in hoje</button>
    </div>
  `);

  renderDataList(elements.studyList, data.study.subjects || [], (item) => `
    <div class="data-item">
      <strong>${item.subject}</strong>
      <span>${item.total_minutes} minutos na semana</span>
    </div>
  `);

  renderDataList(elements.financeList, data.finance.categories || [], (item) => `
    <div class="data-item">
      <strong>${item.category}</strong>
      <span>${formatBRL(item.total_amount)} no mês</span>
    </div>
  `);
}

async function submitJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function reverseGeocode(latitude, longitude) {
  const url = `https://geocode.maps.co/reverse?lat=${latitude}&lon=${longitude}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`reverse geocode failed: ${response.status}`);
  }
  const data = await response.json();
  const address = data.address || {};
  return {
    city: address.city || address.town || address.village || address.suburb || null,
    region: address.state || null,
  };
}

async function enableLocation() {
  if (!navigator.geolocation) {
    setLocationStatus("Geolocalização indisponível neste navegador");
    return;
  }

  elements.locationButton.disabled = true;
  setLocationStatus("Buscando localização");

  navigator.geolocation.getCurrentPosition(
    async (position) => {
      try {
        const { latitude, longitude } = position.coords;
        const place = await reverseGeocode(latitude, longitude).catch(() => ({ city: null, region: null }));
        locationContext = {
          latitude,
          longitude,
          city: place.city,
          region: place.region,
        };
        const label = [place.city, place.region].filter(Boolean).join(", ");
        setLocationStatus(label || `${latitude.toFixed(3)}, ${longitude.toFixed(3)}`);
      } finally {
        elements.locationButton.disabled = false;
      }
    },
    () => {
      setLocationStatus("Permissão de localização negada");
      elements.locationButton.disabled = false;
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 300000,
    },
  );
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await sendMessage(elements.input.value);
});

elements.habitForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(elements.habitForm);
  await submitJson("/habits", {
    name: String(formData.get("name") || ""),
    target_frequency: Number(formData.get("target_frequency") || 7),
  });
  elements.habitForm.reset();
  await loadDashboard();
});

elements.studyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(elements.studyForm);
  await submitJson("/study-sessions", {
    subject: String(formData.get("subject") || ""),
    duration_minutes: Number(formData.get("duration_minutes") || 0),
  });
  elements.studyForm.reset();
  await loadDashboard();
});

elements.financeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(elements.financeForm);
  await submitJson("/finance-entries", {
    kind: String(formData.get("kind") || "expense"),
    category: String(formData.get("category") || ""),
    amount: Number(formData.get("amount") || 0),
  });
  elements.financeForm.reset();
  await loadDashboard();
});

elements.input.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    await sendMessage(elements.input.value);
  }
});

for (const button of elements.prompts) {
  button.addEventListener("click", async () => {
    await sendMessage(button.dataset.prompt || "");
  });
}

elements.locationButton.addEventListener("click", enableLocation);
elements.refreshDashboard.addEventListener("click", loadDashboard);
elements.habitList.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const habitId = target.dataset.habitCheckin;
  if (!habitId) return;
  await submitJson(`/habits/${habitId}/checkins`, { value: 1 });
  await loadDashboard();
});

loadDashboard().catch(() => {
  setStatus("Falha");
});
