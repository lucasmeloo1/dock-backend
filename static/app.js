const history = [];
let locationContext = null;

const elements = {
  pageTitle: document.getElementById("page-title"),
  form: document.getElementById("chat-form"),
  input: document.getElementById("message-input"),
  list: document.getElementById("message-list"),
  send: document.getElementById("send-button"),
  status: document.getElementById("status-pill"),
  source: document.getElementById("status-source"),
  conversationMetricSource: document.getElementById("conversation-metric-source"),
  conversationMetricStatus: document.getElementById("conversation-metric-status"),
  locationStatus: document.getElementById("location-status"),
  locationButton: document.getElementById("location-button"),
  refreshDashboard: document.getElementById("refresh-dashboard"),
  statHabits: document.getElementById("stat-habits"),
  statStudyToday: document.getElementById("stat-study-today"),
  statMonthBalance: document.getElementById("stat-month-balance"),
  habitsMetricCount: document.getElementById("habits-metric-count"),
  habitsMetricBest: document.getElementById("habits-metric-best"),
  studyMetricToday: document.getElementById("study-metric-today"),
  studyMetricWeek: document.getElementById("study-metric-week"),
  financeMetricBalance: document.getElementById("finance-metric-balance"),
  financeMetricExpense: document.getElementById("finance-metric-expense"),
  habitsWeeklyScore: document.getElementById("habits-weekly-score"),
  habitsProgressFill: document.getElementById("habits-progress-fill"),
  habitsBars: document.getElementById("habits-bars"),
  studyWeeklyScore: document.getElementById("study-weekly-score"),
  studyProgressFill: document.getElementById("study-progress-fill"),
  studyBars: document.getElementById("study-bars"),
  financePie: document.getElementById("finance-pie"),
  financeIncomeShare: document.getElementById("finance-income-share"),
  financeIncomeTotal: document.getElementById("finance-income-total"),
  financeExpenseTotal: document.getElementById("finance-expense-total"),
  financeBars: document.getElementById("finance-bars"),
  habitList: document.getElementById("habit-list"),
  studyList: document.getElementById("study-list"),
  financeList: document.getElementById("finance-list"),
  prompts: Array.from(document.querySelectorAll("[data-prompt]")),
  sidebarNav: document.querySelector(".sidebar-nav"),
  navTabs: Array.from(document.querySelectorAll("[data-tab]")),
  panels: Array.from(document.querySelectorAll("[data-panel]")),
};

const tabTitles = {
  conversation: "Conversa",
  habits: "Hábitos",
  study: "Estudo",
  finance: "Financeiro",
};

function getTabFromHash() {
  const hash = window.location.hash.replace("#", "").trim();
  if (hash in tabTitles) return hash;
  return "conversation";
}

function activateTab(tabName) {
  for (const button of elements.navTabs) {
    const isActive = button.dataset.tab === tabName;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  }

  for (const panel of elements.panels) {
    const isActive = panel.dataset.panel === tabName;
    panel.classList.remove("is-entering");
    panel.classList.toggle("active", isActive);
    panel.hidden = !isActive;
    if (isActive) {
      panel.classList.add("is-entering");
      window.setTimeout(() => panel.classList.remove("is-entering"), 520);
    }
  }

  if (elements.pageTitle) {
    elements.pageTitle.textContent = tabTitles[tabName] || "Dock";
  }
}

function setStatus(text) {
  elements.status.textContent = text;
  if (elements.conversationMetricStatus) {
    elements.conversationMetricStatus.textContent = text;
  }
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

function clampPercent(value) {
  return Math.max(0, Math.min(100, Number(value || 0)));
}

function isoDateLabel(date) {
  return new Intl.DateTimeFormat("pt-BR", { weekday: "short" }).format(date).replace(".", "");
}

function renderBars(container, items, options = {}) {
  if (!container) return;
  if (!items.length) {
    container.innerHTML = '<div class="data-item"><strong>Sem dados ainda</strong><span>Use o chat e o Dock atualiza sozinho.</span></div>';
    return;
  }

  const maxValue = Math.max(...items.map((item) => Number(item.value || 0)), 1);
  const suffix = options.suffix || "";
  container.innerHTML = items.map((item) => {
    const width = Math.max(8, Math.round((Number(item.value || 0) / maxValue) * 100));
    return `
      <div class="bar-row">
        <div class="bar-row-head">
          <span>${item.label}</span>
          <strong>${item.displayValue ?? `${item.value}${suffix}`}</strong>
        </div>
        <div class="bar-track">
          <div class="bar-fill ${options.fillClass || ""}" style="width:${width}%"></div>
        </div>
      </div>
    `;
  }).join("");
}

function renderHabitDashboard(habits) {
  const totalTarget = habits.reduce((sum, item) => sum + Number(item.target_frequency || 0), 0);
  const totalProgress = habits.reduce((sum, item) => sum + Number(item.weekly_progress || 0), 0);
  const score = totalTarget ? Math.round((totalProgress / totalTarget) * 100) : 0;

  if (elements.habitsWeeklyScore) {
    elements.habitsWeeklyScore.textContent = `${score}%`;
  }
  if (elements.habitsProgressFill) {
    elements.habitsProgressFill.style.width = `${clampPercent(score)}%`;
  }

  const topHabits = [...habits]
    .sort((a, b) => Number(b.completion_rate || 0) - Number(a.completion_rate || 0))
    .slice(0, 4)
    .map((item) => ({
      label: item.name,
      value: Number(item.completion_rate || 0),
      displayValue: `${Math.round(Number(item.completion_rate || 0))}%`,
    }));

  renderBars(elements.habitsBars, topHabits, { fillClass: "habits-bar-fill" });
}

function renderStudyDashboard(studySummary, studySessions) {
  const weekMinutes = Number(studySummary.week_minutes || 0);
  const progress = clampPercent((weekMinutes / 600) * 100);

  if (elements.studyWeeklyScore) {
    elements.studyWeeklyScore.textContent = `${weekMinutes} min`;
  }
  if (elements.studyProgressFill) {
    elements.studyProgressFill.style.width = `${progress}%`;
  }

  const today = new Date();
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (6 - index));
    const iso = date.toISOString().slice(0, 10);
    return { iso, label: isoDateLabel(date), value: 0 };
  });

  for (const session of studySessions) {
    const bucket = days.find((item) => item.iso === session.studied_on);
    if (bucket) {
      bucket.value += Number(session.duration_minutes || 0);
    }
  }

  renderBars(
    elements.studyBars,
    days.map((item) => ({
      label: item.label,
      value: item.value,
      displayValue: `${item.value} min`,
    })),
    { fillClass: "study-bar-fill" },
  );
}

function renderFinanceDashboard(financeSummary) {
  const income = Number(financeSummary.month_income || 0);
  const expense = Number(financeSummary.month_expense || 0);
  const total = income + expense;
  const incomeShare = total ? Math.round((income / total) * 100) : 0;

  if (elements.financePie) {
    elements.financePie.style.background = `conic-gradient(from 220deg, #4bf2c2 0 ${incomeShare}%, #5f7cff ${incomeShare}% 100%)`;
  }
  if (elements.financeIncomeShare) {
    elements.financeIncomeShare.textContent = `${incomeShare}% receitas`;
  }
  if (elements.financeIncomeTotal) {
    elements.financeIncomeTotal.textContent = formatBRL(income);
  }
  if (elements.financeExpenseTotal) {
    elements.financeExpenseTotal.textContent = formatBRL(expense);
  }

  const categories = (financeSummary.categories || []).slice(0, 4).map((item) => ({
    label: item.category,
    value: Number(item.total_amount || 0),
    displayValue: formatBRL(item.total_amount || 0),
  }));
  renderBars(elements.financeBars, categories, { fillClass: "finance-bar-fill" });
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
    if (elements.conversationMetricSource) {
      elements.conversationMetricSource.textContent = data.source || "Backend local";
    }
    await loadDashboard();
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
  elements.habitsMetricCount.textContent = String(data.highlights.habit_count || 0);
  elements.studyMetricToday.textContent = `${data.highlights.study_today_minutes || 0} min`;
  elements.studyMetricWeek.textContent = `${data.study.week_minutes || 0} min`;
  elements.financeMetricBalance.textContent = formatBRL(data.finance.month_balance || 0);
  elements.financeMetricExpense.textContent = formatBRL(data.finance.month_expense || 0);
  renderHabitDashboard(data.habits || []);
  renderStudyDashboard(data.study || {}, data.study_sessions || []);
  renderFinanceDashboard(data.finance || {});

  if ((data.habits || []).length) {
    const bestHabit = [...data.habits].sort((a, b) => Number(b.completion_rate || 0) - Number(a.completion_rate || 0))[0];
    elements.habitsMetricBest.textContent = `${bestHabit.name} · ${bestHabit.completion_rate}%`;
  } else {
    elements.habitsMetricBest.textContent = "Sem dados";
  }

  renderDataList(elements.habitList, data.habits || [], (item) => `
    <div class="data-item">
      <div class="data-item-top">
        <div>
          <strong>${item.name}</strong>
          <span>${item.weekly_progress}/${item.target_frequency} ${item.unit} • ${item.completion_rate}%</span>
        </div>
        <div class="item-actions">
          <button type="button" class="secondary-button" data-habit-edit="${item.id}" data-habit-name="${item.name}">Editar</button>
          <button type="button" class="icon-delete" data-habit-delete="${item.id}" aria-label="Excluir hábito">🗑</button>
        </div>
      </div>
      <button type="button" class="secondary-button" data-habit-checkin="${item.id}">Check-in hoje</button>
    </div>
  `);

  renderDataList(elements.studyList, data.study_sessions || [], (item) => `
    <div class="data-item">
      <div class="data-item-top">
        <div>
          <strong>${item.subject}</strong>
          <span>${item.duration_minutes} minutos • ${item.studied_on}</span>
        </div>
        <div class="item-actions">
          <button type="button" class="secondary-button" data-study-edit="${item.id}" data-study-subject="${item.subject}">Editar</button>
          <button type="button" class="icon-delete" data-study-delete="${item.id}" aria-label="Excluir sessão">🗑</button>
        </div>
      </div>
    </div>
  `);

  renderDataList(elements.financeList, data.finance_entries || [], (item) => `
    <div class="data-item">
      <div class="data-item-top">
        <div>
          <strong>${item.category}</strong>
          <span>${item.kind === "income" ? "Receita" : "Despesa"} • ${formatBRL(item.amount)} • ${item.occurred_on}</span>
        </div>
        <div class="item-actions">
          <button type="button" class="secondary-button" data-finance-edit="${item.id}" data-finance-category="${item.category}">Editar</button>
          <button type="button" class="icon-delete" data-finance-delete="${item.id}" aria-label="Excluir lançamento">🗑</button>
        </div>
      </div>
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

async function patchJson(url, payload) {
  const response = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function deleteJson(url) {
  const response = await fetch(url, { method: "DELETE" });
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

elements.input.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    await sendMessage(elements.input.value);
  }
});

for (const button of elements.prompts) {
  button.addEventListener("click", async () => {
    activateTab("conversation");
    await sendMessage(button.dataset.prompt || "");
  });
}

for (const button of elements.navTabs) {
  button.setAttribute("aria-selected", String(button.classList.contains("active")));
}

for (const panel of elements.panels) {
  panel.hidden = !panel.classList.contains("active");
}

if (elements.sidebarNav) {
  elements.sidebarNav.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const button = target.closest("[data-tab]");
    if (!(button instanceof HTMLElement)) return;
    const nextTab = button.dataset.tab || "conversation";
    window.location.hash = nextTab;
  });
}

window.addEventListener("hashchange", () => {
  activateTab(getTabFromHash());
});

elements.locationButton.addEventListener("click", enableLocation);
if (elements.refreshDashboard) {
  elements.refreshDashboard.addEventListener("click", loadDashboard);
}
elements.habitList.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const habitId = target.dataset.habitCheckin;
  if (habitId) {
    await submitJson(`/habits/${habitId}/checkins`, { value: 1 });
    await loadDashboard();
    return;
  }
  const habitEditId = target.dataset.habitEdit;
  if (habitEditId) {
    const currentName = target.dataset.habitName || "";
    const nextName = window.prompt("Novo nome do hábito:", currentName);
    if (!nextName || nextName.trim() === currentName) return;
    await patchJson(`/habits/${habitEditId}`, { name: nextName.trim() });
    await loadDashboard();
    return;
  }
  const habitDeleteId = target.dataset.habitDelete;
  if (habitDeleteId) {
    if (!window.confirm("Excluir este hábito?")) return;
    await deleteJson(`/habits/${habitDeleteId}`);
    await loadDashboard();
  }
});

elements.studyList.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const studyEditId = target.dataset.studyEdit;
  if (studyEditId) {
    const currentSubject = target.dataset.studySubject || "";
    const nextSubject = window.prompt("Novo nome da sessão de estudo:", currentSubject);
    if (!nextSubject || nextSubject.trim() === currentSubject) return;
    await patchJson(`/study-sessions/${studyEditId}`, { subject: nextSubject.trim() });
    await loadDashboard();
    return;
  }
  const studyDeleteId = target.dataset.studyDelete;
  if (studyDeleteId) {
    if (!window.confirm("Excluir esta sessão de estudo?")) return;
    await deleteJson(`/study-sessions/${studyDeleteId}`);
    await loadDashboard();
  }
});

elements.financeList.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const financeEditId = target.dataset.financeEdit;
  if (financeEditId) {
    const currentCategory = target.dataset.financeCategory || "";
    const nextCategory = window.prompt("Novo nome do lançamento:", currentCategory);
    if (!nextCategory || nextCategory.trim() === currentCategory) return;
    await patchJson(`/finance-entries/${financeEditId}`, { category: nextCategory.trim() });
    await loadDashboard();
    return;
  }
  const financeDeleteId = target.dataset.financeDelete;
  if (financeDeleteId) {
    if (!window.confirm("Excluir este lançamento?")) return;
    await deleteJson(`/finance-entries/${financeDeleteId}`);
    await loadDashboard();
  }
});

activateTab(getTabFromHash());
loadDashboard().catch(() => {
  setStatus("Falha");
});
