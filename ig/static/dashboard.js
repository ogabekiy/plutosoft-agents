(() => {
  const list = document.getElementById("conversation-list");
  const messageList = document.getElementById("message-list");
  const emptyChat = document.getElementById("empty-chat");
  const chatView = document.getElementById("chat-view");
  const searchInput = document.getElementById("search");
  const leadSearchInput = document.getElementById("lead-search");
  const leadsPanel = document.getElementById("leads-panel");
  const inboxPanel = document.querySelector(".inbox-panel");
  const leadsList = document.getElementById("leads-list");
  const leadsEmpty = document.getElementById("leads-empty");
  const replyForm = document.getElementById("reply-form");
  const replyInput = document.getElementById("reply-input");
  const sendButton = document.getElementById("send-button");
  const sendError = document.getElementById("send-error");
  const modelSelect = document.getElementById("model-select");
  const modelStatus = document.getElementById("model-status");
  const themeToggle = document.getElementById("theme-toggle");
  const state = { platform: "all", search: "", leadSearch: "", view: "inbox", selected: null, conversations: [] };
  let searchTimer;
  let leadSearchTimer;
  let scrollOnNextRender = false;
  let savedModel = "";

  function setTheme(theme) {
    const isLight = theme === "light";
    document.documentElement.dataset.theme = isLight ? "light" : "dark";
    document.documentElement.style.colorScheme = isLight ? "light" : "dark";
    themeToggle.textContent = isLight ? "☾" : "☼";
    themeToggle.setAttribute("aria-label", isLight ? "Qorong'i rejimga o'tish" : "Yorug' rejimga o'tish");
    themeToggle.title = isLight ? "Qorong'i rejim" : "Yorug' rejim";
    try {
      window.localStorage.setItem("plutosoft-dashboard-theme", isLight ? "light" : "dark");
    } catch (error) {
      console.warn("Mavzu tanlovini saqlab bo'lmadi.", error);
    }
  }

  try {
    setTheme(window.localStorage.getItem("plutosoft-dashboard-theme") || "dark");
  } catch (error) {
    document.documentElement.dataset.theme = "dark";
  }

  themeToggle.addEventListener("click", () => {
    setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
  });

  async function loadModelSetting() {
    try {
      const response = await fetch("/dashboard/api/settings/model", {
        headers: { Accept: "application/json" },
      });
      if (response.status === 401) {
        window.location.assign("/dashboard/login");
        return;
      }
      if (!response.ok) throw new Error("Model sozlamasini yuklab bo'lmadi.");
      const result = await response.json();
      if (result.models.includes(result.model)) {
        modelSelect.value = result.model;
      } else {
        const current = document.createElement("option");
        current.value = result.model;
        current.textContent = `${result.model} (ro'yxatda yo'q)`;
        current.disabled = true;
        modelSelect.prepend(current);
        modelSelect.value = result.model;
      }
      savedModel = result.model;
      modelSelect.disabled = false;
    } catch (error) {
      modelStatus.textContent = error.message;
      modelStatus.classList.add("is-error");
    }
  }

  modelSelect.addEventListener("change", async () => {
    modelSelect.disabled = true;
    modelStatus.textContent = "Saqlanmoqda...";
    modelStatus.classList.remove("is-error");
    try {
      const response = await fetch("/dashboard/api/settings/model", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": document.querySelector('meta[name="dashboard-csrf"]').content,
        },
        body: JSON.stringify({ model: modelSelect.value }),
      });
      const result = await response.json();
      if (response.status === 401) {
        window.location.assign("/dashboard/login");
        return;
      }
      if (!response.ok) throw new Error(result.error || "Model sozlamasi saqlanmadi.");
      savedModel = result.model;
      modelStatus.textContent = "Model saqlandi";
      window.setTimeout(() => { modelStatus.textContent = ""; }, 2500);
    } catch (error) {
      if (savedModel) modelSelect.value = savedModel;
      modelStatus.textContent = error.message;
      modelStatus.classList.add("is-error");
    } finally {
      modelSelect.disabled = false;
    }
  });

  const escapeInitial = (name) => {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    return (parts.length > 1 ? parts[0][0] + parts[1][0] : (parts[0] || "?").slice(0, 2)).toUpperCase();
  };

  const formatTime = (value) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const now = new Date();
    if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  };

  const formatDateTime = (value) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString([], {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  };

  const channelClass = (platform) => platform === "Telegram" ? "telegram" : "";
  const setAvatar = (element, conversation) => {
    element.replaceChildren();
    const fallback = escapeInitial(conversation.display_name || conversation.external_id);
    element.textContent = fallback;
    if (!conversation.avatar_url) return;
    const image = document.createElement("img");
    image.src = conversation.avatar_url;
    image.alt = "";
    image.loading = "lazy";
    image.addEventListener("error", () => {
      element.replaceChildren();
      element.textContent = fallback;
    }, { once: true });
    element.textContent = "";
    element.append(image);
  };
  const selectedConversation = () => state.conversations.find(
    (item) => item.platform === state.selected?.platform
      && item.external_id === state.selected?.external_id,
  );

  const formatLeadStatus = (status) => ({
    sent: "Telegram'ga yuborildi",
    failed: "Telegram yuborilmadi",
    pending: "Yuborilmoqda",
    not_configured: "Faqat bazada",
  })[status] || status;

  async function fetchLeads() {
    const params = new URLSearchParams({ q: state.leadSearch });
    const response = await fetch(`/dashboard/api/leads?${params}`, {
      headers: { Accept: "application/json" },
    });
    if (response.status === 401) {
      window.location.assign("/dashboard/login");
      return;
    }
    if (!response.ok) throw new Error("Leadlarni yuklab bo'lmadi.");
    const result = await response.json();
    leadsList.replaceChildren();
    document.getElementById("leads-count").textContent = result.total;
    leadsEmpty.classList.toggle("hidden", result.leads.length > 0);
    for (const lead of result.leads) {
      const row = document.createElement("tr");
      const customerCell = document.createElement("td");
      const customerName = document.createElement("strong");
      customerName.textContent = lead.name;
      const customerId = document.createElement("small");
      customerId.textContent = `ID · ${lead.source_user_id}`;
      customerCell.append(customerName, customerId);

      const phoneCell = document.createElement("td");
      const phoneLink = document.createElement("a");
      phoneLink.href = `tel:${lead.phone.replace(/[^\d+]/g, "")}`;
      phoneLink.textContent = lead.phone;
      phoneCell.append(phoneLink);

      const platformCell = document.createElement("td");
      const platformTag = document.createElement("span");
      platformTag.className = `mini-channel ${channelClass(lead.platform)}`;
      platformTag.textContent = lead.platform;
      platformCell.append(platformTag);

      const noteCell = document.createElement("td");
      noteCell.className = "lead-note-cell";
      noteCell.textContent = lead.note || "—";

      const summaryCell = document.createElement("td");
      summaryCell.className = "lead-summary-cell";
      if (lead.summary) {
        const details = document.createElement("details");
        const summaryLabel = document.createElement("summary");
        summaryLabel.textContent = "Xulosani ko'rish";
        const summaryText = document.createElement("p");
        summaryText.textContent = lead.summary;
        details.append(summaryLabel, summaryText);
        summaryCell.append(details);
      } else {
        summaryCell.textContent = "AI xulosasi tayyorlanmadi";
      }

      const timeCell = document.createElement("td");
      timeCell.className = "lead-time-cell";
      timeCell.textContent = formatDateTime(lead.created_at);

      const statusCell = document.createElement("td");
      const status = document.createElement("span");
      status.className = `lead-status ${lead.notification_status}`;
      status.textContent = formatLeadStatus(lead.notification_status);
      statusCell.append(status);

      row.append(customerCell, phoneCell, platformCell, noteCell, summaryCell, timeCell, statusCell);
      leadsList.append(row);
    }
  }

  function renderConversations() {
    list.replaceChildren();
    if (!state.conversations.length) {
      const message = document.createElement("div");
      message.className = "list-empty";
      message.textContent = state.search
        ? "Qidiruv bo'yicha suhbat topilmadi."
        : "Hozircha suhbat yo'q. Xabar kelganda shu yerda ko'rinadi.";
      list.append(message);
      return;
    }

    for (const conversation of state.conversations) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "conversation-item";
      if (state.selected?.platform === conversation.platform
        && state.selected?.external_id === conversation.external_id) {
        item.classList.add("selected");
      }

      const avatar = document.createElement("span");
      avatar.className = `conversation-avatar ${channelClass(conversation.platform)}`;
      setAvatar(avatar, conversation);

      const copy = document.createElement("span");
      copy.className = "conversation-copy";
      const line = document.createElement("span");
      line.className = "conversation-line";
      const name = document.createElement("span");
      name.className = "conversation-name";
      name.textContent = conversation.display_name || conversation.external_id;
      const time = document.createElement("span");
      time.className = "conversation-time";
      time.textContent = formatTime(conversation.last_activity);
      line.append(name, time);

      const preview = document.createElement("span");
      preview.className = "conversation-preview";
      preview.textContent = conversation.last_message || "—";
      const tags = document.createElement("span");
      tags.className = "conversation-tags";
      const channel = document.createElement("span");
      channel.className = `mini-channel ${channelClass(conversation.platform)}`;
      channel.textContent = conversation.platform;
      const count = document.createElement("span");
      count.className = "message-count";
      count.textContent = `${conversation.message_count} xabar`;
      tags.append(channel, count);
      copy.append(line, preview, tags);
      item.append(avatar, copy);
      item.addEventListener("click", () => selectConversation(conversation));
      list.append(item);
    }
  }

  function renderMessages(messages) {
    const wasNearBottom = scrollOnNextRender
      || messageList.scrollHeight - messageList.scrollTop - messageList.clientHeight < 80;
    scrollOnNextRender = false;
    messageList.replaceChildren();
    if (!messages.length) {
      const empty = document.createElement("div");
      empty.className = "list-empty";
      empty.textContent = "Bu suhbatda hali xabar yo'q.";
      messageList.append(empty);
      return;
    }
    for (const message of messages) {
      const row = document.createElement("div");
      row.className = `message-row ${message.role === "assistant" ? "assistant" : ""}`;
      const sender = document.createElement("span");
      sender.className = "message-sender";
      sender.textContent = message.role === "assistant" ? "PLUTOSOFT AI" : message.display_name;
      const bubble = document.createElement("div");
      bubble.className = "message-bubble";
      bubble.textContent = message.text;
      const time = document.createElement("span");
      time.className = "message-time";
      time.textContent = formatDateTime(message.created_at);
      row.append(sender, bubble, time);
      messageList.append(row);
    }
    if (wasNearBottom) {
      window.requestAnimationFrame(() => {
        messageList.scrollTop = messageList.scrollHeight;
      });
    }
  }

  async function fetchMessages() {
    const selected = state.selected;
    if (!selected) return;
    const url = `/dashboard/api/conversations/${encodeURIComponent(selected.platform)}/${encodeURIComponent(selected.external_id)}`;
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (response.status === 401) {
      window.location.assign("/dashboard/login");
      return;
    }
    if (!response.ok) throw new Error("Suhbat xabarlarini yuklab bo'lmadi.");
    const result = await response.json();
    if (state.selected?.platform === selected.platform
      && state.selected?.external_id === selected.external_id) {
      renderMessages(result.messages);
    }
  }

  async function selectConversation(conversation) {
    state.selected = { platform: conversation.platform, external_id: conversation.external_id };
    scrollOnNextRender = true;
    emptyChat.classList.add("hidden");
    chatView.classList.remove("hidden");
    const chatAvatar = document.getElementById("chat-avatar");
    chatAvatar.className = `conversation-avatar ${channelClass(conversation.platform)}`;
    setAvatar(chatAvatar, conversation);
    document.getElementById("chat-name").textContent = conversation.display_name || conversation.external_id;
    document.getElementById("chat-meta").textContent = conversation.username
      ? `@${conversation.username.replace(/^@/, "")}`
      : `ID · ${conversation.external_id}`;
    document.getElementById("chat-channel").textContent = conversation.platform;
    document.getElementById("chat-channel").className = `channel-badge ${channelClass(conversation.platform)}`;
    document.getElementById("thread-platform").textContent = conversation.platform;
    sendError.classList.add("hidden");
    replyInput.disabled = false;
    sendButton.disabled = false;
    renderConversations();
    messageList.replaceChildren();
    const loading = document.createElement("div");
    loading.className = "loading-state";
    const loader = document.createElement("span");
    loader.className = "loader";
    const loadingText = document.createElement("span");
    loadingText.textContent = "Xabarlar yuklanmoqda...";
    loading.append(loader, loadingText);
    messageList.append(loading);
    try {
      await fetchMessages();
    } catch (error) {
      renderLoadError(messageList, error.message);
    }
  }

  function renderLoadError(target, text) {
    target.replaceChildren();
    const error = document.createElement("div");
    error.className = "list-empty";
    error.textContent = text;
    target.append(error);
  }

  async function fetchConversations() {
    const params = new URLSearchParams({ platform: state.platform, q: state.search });
    const response = await fetch(`/dashboard/api/conversations?${params}`, {
      headers: { Accept: "application/json" },
    });
    if (response.status === 401) {
      window.location.assign("/dashboard/login");
      return;
    }
    if (!response.ok) throw new Error("Suhbatlarni yuklab bo'lmadi.");
    const result = await response.json();
    state.conversations = result.conversations;
    document.getElementById("stat-total").textContent = result.stats.instagram + result.stats.telegram;
    document.getElementById("stat-instagram").textContent = result.stats.instagram;
    document.getElementById("stat-telegram").textContent = result.stats.telegram;
    document.getElementById("stat-messages").textContent = result.stats.messages;
    document.getElementById("total-count").textContent = result.stats.instagram + result.stats.telegram;
    document.getElementById("ig-count").textContent = result.stats.instagram;
    document.getElementById("tg-count").textContent = result.stats.telegram;
    document.getElementById("leads-count").textContent = result.stats.leads || 0;
    renderConversations();
    if (state.selected) {
      const stillAvailable = selectedConversation();
      if (stillAvailable) {
        await fetchMessages();
      } else {
        state.selected = null;
        chatView.classList.add("hidden");
        emptyChat.classList.remove("hidden");
      }
    }
  }

  const switchView = (view) => {
    state.view = view;
    inboxPanel.classList.toggle("hidden", view === "leads");
    leadsPanel.classList.toggle("hidden", view !== "leads");
    document.querySelector(".topbar h1").childNodes[0].textContent =
      view === "leads" ? "Leads " : "Unified inbox ";
    if (view === "leads") fetchLeads().catch((error) => renderLoadError(leadsList, error.message));
    else fetchConversations().catch((error) => renderLoadError(list, error.message));
  };

  document.querySelectorAll(".nav-item[data-platform]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      state.view = "inbox";
      inboxPanel.classList.remove("hidden");
      leadsPanel.classList.add("hidden");
      document.querySelector(".topbar h1").childNodes[0].textContent = "Unified inbox ";
      state.platform = button.dataset.platform;
      document.getElementById("list-label").textContent = state.platform === "all"
        ? "BARCHASI" : state.platform.toUpperCase();
      fetchConversations().catch((error) => renderLoadError(list, error.message));
      loadModelSetting();
    });
  });

  document.querySelector(".leads-nav-item").addEventListener("click", (event) => {
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("is-active"));
    event.currentTarget.classList.add("is-active");
    switchView("leads");
  });

  searchInput.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
      state.search = searchInput.value.trim();
      fetchConversations().catch((error) => renderLoadError(list, error.message));
    }, 250);
  });

  leadSearchInput.addEventListener("input", () => {
    window.clearTimeout(leadSearchTimer);
    leadSearchTimer = window.setTimeout(() => {
      state.leadSearch = leadSearchInput.value.trim();
      fetchLeads().catch((error) => renderLoadError(leadsList, error.message));
    }, 250);
  });

  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      searchInput.focus();
    }
  });

  document.getElementById("refresh-button").addEventListener("click", () => {
    fetchMessages().catch((error) => renderLoadError(messageList, error.message));
  });

  replyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const selected = state.selected;
    const text = replyInput.value.trim();
    if (!selected || !text || sendButton.disabled) return;
    sendButton.disabled = true;
    replyInput.disabled = true;
    sendError.classList.add("hidden");
    sendButton.querySelector("span").textContent = "Yuborilmoqda...";
    try {
      const response = await fetch(
        `/dashboard/api/conversations/${encodeURIComponent(selected.platform)}/${encodeURIComponent(selected.external_id)}/messages`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": document.querySelector('meta[name="dashboard-csrf"]').content,
          },
          body: JSON.stringify({ text }),
        },
      );
      const result = await response.json();
      if (response.status === 401) {
        window.location.assign("/dashboard/login");
        return;
      }
      if (!response.ok) throw new Error(result.error || "Xabar yuborilmadi.");
      replyInput.value = "";
      await Promise.all([fetchMessages(), fetchConversations()]);
    } catch (error) {
      sendError.textContent = error.message || "Xabar yuborilmadi. Qayta urinib ko'ring.";
      sendError.classList.remove("hidden");
    } finally {
      sendButton.disabled = false;
      replyInput.disabled = false;
      sendButton.querySelector("span").textContent = "Yuborish";
      replyInput.focus();
    }
  });

  replyInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      replyForm.requestSubmit();
    }
  });

  fetchConversations().catch((error) => renderLoadError(list, error.message));
  window.setInterval(() => {
    if (state.view === "leads") {
      fetchLeads().catch((error) => console.error(error));
    } else {
      fetchConversations().catch((error) => console.error(error));
    }
  }, 4000);
})();
