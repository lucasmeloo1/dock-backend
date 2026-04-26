const history = [];
let locationContext = null;

const TAB_CONFIG = {
  conversation: {
    title: "Conversa",
    note: "Converse com o Dock para organizar pensamento, registrar eventos e agir com menos friccao.",
  },
  habits: {
    title: "Habitos",
    note: "Consistencia semanal, check-ins e progresso dos habitos que sustentam sua rotina.",
  },
  study: {
    title: "Estudo",
    note: "Volume recente, ritmo de sete dias e sessoes registradas para manter direcao.",
  },
  finance: {
    title: "Financeiro",
    note: "Saldo do mes, categorias mais pesadas e historico operacional de entradas e saidas.",
  },
};

const elements = {
  pageTitle: document.getElementById("page-title"),
  pageNote: document.getElementById("page-note"),
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
  heroHabits: document.getElementById("hero-habits"),
  heroStudy: document.getElementById("hero-study"),
  heroBalance: document.getElementById("hero-balance"),
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

function getTabFromHash() {
  const hash = window.location.hash.replace("#", "").trim();
  if (hash in TAB_CONFIG) return hash;
  return "conversation";
}

function updatePageContext(tabName) {
  const config = TAB_CONFIG[tabName] || TAB_CONFIG.conversation;
  if (elements.pageTitle) {
    elements.pageTitle.textContent = config.title;
  }
  if (elements.pageNote) {
    elements.pageNote.textContent = config.note;
  }
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

  updatePageContext(tabName);
}

function setStatus(text, state = "ready") {
  if (elements.status) {
    elements.status.textContent = text;
    elements.status.dataset.state = state;
  }
  if (elements.conversationMetricStatus) {
    elements.conversationMetricStatus.textContent = text;
  }
}

function humanizeSource(source) {
  const normalized = String(source || "").trim().toLowerCase();
  if (!normalized) return "Motor Dock";

  const exactLabels = {
    openai: "OpenAI",
    ollama: "Ollama",
    fallback: "Fallback local",
    "dock-identity": "Identidade Dock",
    "dock-founder": "Memoria Dock",
    "live-weather": "Clima ao vivo",
    "live-weather-needs-location": "Clima ao vivo",
    "live-weather-unavailable": "Clima indisponivel",
    "live-usd-brl": "Mercado ao vivo",
    "live-eur-brl": "Mercado ao vivo",
    "live-btc-brl": "Mercado ao vivo",
    "live-data-unavailable": "Dados ao vivo indisponiveis",
  };

  if (exactLabels[normalized]) {
    return exactLabels[normalized];
  }
  if (normalized.startsWith("dock-fast-")) {
    return "Fluxo rapido Dock";
  }
  if (normalized.startsWith("dock-fallback-")) {
    return "Fallback Dock";
  }
  if (normalized.startsWith("dock-data-")) {
    return "Painel Dock";
  }
  if (normalized.startsWith("dock-local-")) {
    return "Motor local Dock";
  }
  if (normalized.startsWith("dock-action-")) {
    return "Automacao Dock";
  }
  if (normalized.startsWith("live-")) {
    return "Consulta ao vivo";
  }

  return normalized
    .split("-")
    .filter(Boolean)
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");
}

function setSource(source) {
  const label = humanizeSource(source);
  if (elements.source) {
    elements.source.textContent = label;
  }
  if (elements.conversationMetricSource) {
    elements.conversationMetricSource.textContent = label;
  }
}

function setLocationStatus(text) {
  if (elements.locationStatus) {
    elements.locationStatus.textContent = text;
  }
}

function setLocationButtonLabel(text) {
  if (elements.locationButton) {
    elements.locationButton.textContent = text;
  }
}

function formatBRL(value) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value || 0));
}

function formatShortDate(value) {
  if (!value) return "Sem data";
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
  }).format(date);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  }[char]));
}

function clampPercent(value) {
  return Math.max(0, Math.min(100, Number(value || 0)));
}

function isoDateLabel(date) {
  return new Intl.DateTimeFormat("pt-BR", { weekday: "short" }).format(date).replace(".", "");
}

function renderEmptyState(container, defaultTitle, defaultCopy) {
  if (!container) return;
  const title = container.dataset.emptyTitle || defaultTitle;
  const copy = container.dataset.emptyCopy || defaultCopy;
  container.innerHTML = `
    <div class="data-item">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(copy)}</span>
    </div>
  `;
}

function renderDataList(container, items, renderItem) {
  if (!container) return;
  if (!items.length) {
    renderEmptyState(container, "Sem dados ainda", "Cadastre o primeiro item para comecar.");
    return;
  }
  container.innerHTML = items.map(renderItem).join("");
}

function renderBars(container, items, options = {}) {
  if (!container) return;
  if (!items.length) {
    renderEmptyState(container, "Sem dados ainda", "Use o chat e o Dock atualiza sozinho.");
    return;
  }

  const maxValue = Math.max(...items.map((item) => Number(item.value || 0)), 1);
  const suffix = options.suffix || "";
  const fillClass = options.fillClass || "";

  container.innerHTML = items.map((item) => {
    const width = Math.max(8, Math.round((Number(item.value || 0) / maxValue) * 100));
    const displayValue = item.displayValue ?? `${item.value}${suffix}`;
    return `
      <div class="bar-row">
        <div class="bar-row-head">
          <span>${escapeHtml(item.label)}</span>
          <strong>${escapeHtml(displayValue)}</strong>
        </div>
        <div class="bar-track">
          <div class="bar-fill ${fillClass}" style="width:${width}%"></div>
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

function appendMessage(role, text, meta = "", options = {}) {
  const wrapper = document.createElement("article");
  wrapper.className = `message ${role}`;
  if (options.typing) {
    wrapper.classList.add("is-typing");
  }

  const roleLabel = document.createElement("div");
  roleLabel.className = "message-role";
  roleLabel.textContent = role === "user" ? "Voce" : "Dock";

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

  if (elements.list) {
    elements.list.appendChild(wrapper);
    elements.list.scrollTop = elements.list.scrollHeight;
  }

  return wrapper;
}

function removeMessage(node) {
  if (node && node.parentNode) {
    node.parentNode.removeChild(node);
  }
}

function buildMessageMeta(source, model) {
  const label = humanizeSource(source);
  return model ? `${label} / ${model}` : label;
}

function updateHighlights(data) {
  const habitCount = Number(data.highlights?.habit_count || 0);
  const studyTodayMinutes = Number(data.highlights?.study_today_minutes || 0);
  const financeMonthBalance = Number(data.highlights?.finance_month_balance || 0);

  if (elements.statHabits) {
    elements.statHabits.textContent = String(habitCount);
  }
  if (elements.statStudyToday) {
    elements.statStudyToday.textContent = `${studyTodayMinutes} min`;
  }
  if (elements.statMonthBalance) {
    elements.statMonthBalance.textContent = formatBRL(financeMonthBalance);
  }

  if (elements.heroHabits) {
    elements.heroHabits.textContent = String(habitCount);
  }
  if (elements.heroStudy) {
    elements.heroStudy.textContent = `${studyTodayMinutes} min`;
  }
  if (elements.heroBalance) {
    elements.heroBalance.textContent = formatBRL(financeMonthBalance);
  }

  if (elements.habitsMetricCount) {
    elements.habitsMetricCount.textContent = String(habitCount);
  }
  if (elements.studyMetricToday) {
    elements.studyMetricToday.textContent = `${studyTodayMinutes} min`;
  }
  if (elements.studyMetricWeek) {
    elements.studyMetricWeek.textContent = `${data.study?.week_minutes || 0} min`;
  }
  if (elements.financeMetricBalance) {
    elements.financeMetricBalance.textContent = formatBRL(data.finance?.month_balance || 0);
  }
  if (elements.financeMetricExpense) {
    elements.financeMetricExpense.textContent = formatBRL(data.finance?.month_expense || 0);
  }
}

async function loadDashboard(options = {}) {
  const { silent = false } = options;
  if (!silent) {
    setStatus("Atualizando painel", "thinking");
  }

  const response = await fetch("/dashboard");
  if (!response.ok) {
    throw new Error(`dashboard failed: ${response.status}`);
  }

  const data = await response.json();
  updateHighlights(data);
  renderHabitDashboard(data.habits || []);
  renderStudyDashboard(data.study || {}, data.study_sessions || []);
  renderFinanceDashboard(data.finance || {});

  if ((data.habits || []).length) {
    const bestHabit = [...data.habits].sort((a, b) => Number(b.completion_rate || 0) - Number(a.completion_rate || 0))[0];
    if (elements.habitsMetricBest) {
      elements.habitsMetricBest.textContent = `${bestHabit.name} · ${Math.round(Number(bestHabit.completion_rate || 0))}%`;
    }
  } else if (elements.habitsMetricBest) {
    elements.habitsMetricBest.textContent = "Sem dados";
  }

  renderDataList(elements.habitList, data.habits || [], (item) => `
    <div class="data-item">
      <div class="data-item-top">
        <div>
          <strong>${escapeHtml(item.name)}</strong>
          <span>${escapeHtml(`${item.weekly_progress}/${item.target_frequency} ${item.unit} • ${Math.round(Number(item.completion_rate || 0))}%`)}</span>
        </div>
        <div class="item-actions">
          <button type="button" class="secondary-button" data-habit-edit="${escapeHtml(item.id)}" data-habit-name="${escapeHtml(item.name)}">Editar</button>
          <button type="button" class="icon-delete" data-habit-delete="${escapeHtml(item.id)}" aria-label="Excluir habito">X</button>
        </div>
      </div>
      <button type="button" class="secondary-button" data-habit-checkin="${escapeHtml(item.id)}">Check-in hoje</button>
    </div>
  `);

  renderDataList(elements.studyList, data.study_sessions || [], (item) => `
    <div class="data-item">
      <div class="data-item-top">
        <div>
          <strong>${escapeHtml(item.subject)}</strong>
          <span>${escapeHtml(`${item.duration_minutes} minutos • ${formatShortDate(item.studied_on)}`)}</span>
        </div>
        <div class="item-actions">
          <button type="button" class="secondary-button" data-study-edit="${escapeHtml(item.id)}" data-study-subject="${escapeHtml(item.subject)}">Editar</button>
          <button type="button" class="icon-delete" data-study-delete="${escapeHtml(item.id)}" aria-label="Excluir sessao">X</button>
        </div>
      </div>
    </div>
  `);

  renderDataList(elements.financeList, data.finance_entries || [], (item) => `
    <div class="data-item">
      <div class="data-item-top">
        <div>
          <strong>${escapeHtml(item.category)}</strong>
          <span>${escapeHtml(`${item.kind === "income" ? "Receita" : "Despesa"} • ${formatBRL(item.amount)} • ${formatShortDate(item.occurred_on)}`)}</span>
        </div>
        <div class="item-actions">
          <button type="button" class="secondary-button" data-finance-edit="${escapeHtml(item.id)}" data-finance-category="${escapeHtml(item.category)}">Editar</button>
          <button type="button" class="icon-delete" data-finance-delete="${escapeHtml(item.id)}" aria-label="Excluir lancamento">X</button>
        </div>
      </div>
    </div>
  `);

  if (!silent) {
    setStatus("Pronto", "ready");
  }
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
    setLocationStatus("Geolocalizacao indisponivel neste navegador");
    setLocationButtonLabel("Indisponivel");
    return;
  }

  if (elements.locationButton) {
    elements.locationButton.disabled = true;
  }
  setLocationButtonLabel("Conectando...");
  setLocationStatus("Buscando localizacao");

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
        setLocationButtonLabel("Atualizar localizacao");
      } finally {
        if (elements.locationButton) {
          elements.locationButton.disabled = false;
        }
      }
    },
    () => {
      setLocationStatus("Permissao de localizacao negada");
      setLocationButtonLabel("Tentar novamente");
      if (elements.locationButton) {
        elements.locationButton.disabled = false;
      }
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 300000,
    },
  );
}

async function runUiAction(action, errorMessage) {
  try {
    setStatus("Atualizando painel", "thinking");
    await action();
    await loadDashboard({ silent: true });
    setStatus("Pronto", "ready");
  } catch (error) {
    console.error(error);
    setStatus("Falha", "error");
    appendMessage("dock", errorMessage, "acao interrompida");
  }
}

async function sendMessage(message) {
  const cleanMessage = message.trim();
  if (!cleanMessage) return;

  appendMessage("user", cleanMessage);
  history.push({ role: "user", content: cleanMessage });

  elements.input.value = "";
  elements.send.disabled = true;
  setStatus("Respondendo", "thinking");

  const typingMessage = appendMessage("dock", "Pensando...", "processando", { typing: true });

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
    removeMessage(typingMessage);
    appendMessage("dock", data.reply, buildMessageMeta(data.source, data.model));
    history.push({ role: "assistant", content: data.reply });
    setSource(data.source || "dock");
    await loadDashboard({ silent: true });
    setStatus("Pronto", "ready");
  } catch (error) {
    console.error(error);
    removeMessage(typingMessage);
    appendMessage("dock", "Nao consegui completar essa resposta agora. Verifica o backend e tenta de novo.", "erro de conexao");
    setStatus("Falha", "error");
  } finally {
    elements.send.disabled = false;
    elements.input.focus();
  }
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await sendMessage(elements.input.value);
});

elements.input.addEventListener("keydown", async (event) => {
  if (event.isComposing) return;
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    await sendMessage(elements.input.value);
  }
});

for (const button of elements.prompts) {
  button.addEventListener("click", async () => {
    activateTab("conversation");
    window.location.hash = "conversation";
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

if (elements.locationButton) {
  elements.locationButton.addEventListener("click", enableLocation);
}

if (elements.refreshDashboard) {
  elements.refreshDashboard.addEventListener("click", async () => {
    try {
      await loadDashboard();
    } catch (error) {
      console.error(error);
      setStatus("Falha", "error");
    }
  });
}

if (elements.habitList) {
  elements.habitList.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const habitId = target.dataset.habitCheckin;
    if (habitId) {
      await runUiAction(
        () => submitJson(`/habits/${habitId}/checkins`, { value: 1 }),
        "Nao consegui registrar o check-in agora.",
      );
      return;
    }

    const habitEditId = target.dataset.habitEdit;
    if (habitEditId) {
      const currentName = target.dataset.habitName || "";
      const nextName = window.prompt("Novo nome do habito:", currentName);
      if (!nextName || nextName.trim() === currentName) return;
      await runUiAction(
        () => patchJson(`/habits/${habitEditId}`, { name: nextName.trim() }),
        "Nao consegui atualizar esse habito agora.",
      );
      return;
    }

    const habitDeleteId = target.dataset.habitDelete;
    if (habitDeleteId) {
      if (!window.confirm("Excluir este habito?")) return;
      await runUiAction(
        () => deleteJson(`/habits/${habitDeleteId}`),
        "Nao consegui excluir esse habito agora.",
      );
    }
  });
}

if (elements.studyList) {
  elements.studyList.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const studyEditId = target.dataset.studyEdit;
    if (studyEditId) {
      const currentSubject = target.dataset.studySubject || "";
      const nextSubject = window.prompt("Novo nome da sessao de estudo:", currentSubject);
      if (!nextSubject || nextSubject.trim() === currentSubject) return;
      await runUiAction(
        () => patchJson(`/study-sessions/${studyEditId}`, { subject: nextSubject.trim() }),
        "Nao consegui atualizar essa sessao agora.",
      );
      return;
    }

    const studyDeleteId = target.dataset.studyDelete;
    if (studyDeleteId) {
      if (!window.confirm("Excluir esta sessao de estudo?")) return;
      await runUiAction(
        () => deleteJson(`/study-sessions/${studyDeleteId}`),
        "Nao consegui excluir essa sessao agora.",
      );
    }
  });
}

if (elements.financeList) {
  elements.financeList.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const financeEditId = target.dataset.financeEdit;
    if (financeEditId) {
      const currentCategory = target.dataset.financeCategory || "";
      const nextCategory = window.prompt("Novo nome do lancamento:", currentCategory);
      if (!nextCategory || nextCategory.trim() === currentCategory) return;
      await runUiAction(
        () => patchJson(`/finance-entries/${financeEditId}`, { category: nextCategory.trim() }),
        "Nao consegui atualizar esse lancamento agora.",
      );
      return;
    }

    const financeDeleteId = target.dataset.financeDelete;
    if (financeDeleteId) {
      if (!window.confirm("Excluir este lancamento?")) return;
      await runUiAction(
        () => deleteJson(`/finance-entries/${financeDeleteId}`),
        "Nao consegui excluir esse lancamento agora.",
      );
    }
  });
}

activateTab(getTabFromHash());
setSource("dock");
setStatus("Sincronizando", "thinking");
loadDashboard()
  .then(() => {
    setStatus("Pronto", "ready");
  })
  .catch((error) => {
    console.error(error);
    setStatus("Falha", "error");
  });
