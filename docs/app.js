/* FASARO Zlecenia — logika aplikacji (vanilla JS, bez zależności) */
(function () {
  "use strict";

  var DATA_URL = "data/leads.json";
  var META_URL = "data/meta.json";
  var KEYS = {
    read: "fasaro_read_v1",
    hidden: "fasaro_hidden_v1",
    filter: "fasaro_filter_v1",
    sort: "fasaro_sort_v1",
    onlyNew: "fasaro_onlynew_v1",
    onlyFree: "fasaro_onlyfree_v1",
    hint: "fasaro_hint_v1",
  };

  var SERVICE_FILTERS = [
    { id: "all", label: "Wszystkie" },
    { id: "elewacje", label: "Elewacje" },
    { id: "ocieplenia", label: "Ocieplenia" },
    { id: "tynki", label: "Tynki i gładzie" },
    { id: "remonty", label: "Remonty" },
    { id: "tender", label: "Przetargi" },
  ];

  var TENDER_SOURCES = { bzp: 1, epropublico: 1, bip_kk: 1 };

  var state = {
    leads: [],
    meta: null,
    filter: localStorage.getItem(KEYS.filter) || "all",
    sort: localStorage.getItem(KEYS.sort) || "score",
    onlyNew: localStorage.getItem(KEYS.onlyNew) === "1",
    onlyFree: localStorage.getItem(KEYS.onlyFree) === "1",
    query: "",
    read: new Set(readList(KEYS.read)),
    hidden: new Set(readList(KEYS.hidden)),
    loading: true,
    error: "",
    tab: "leads",
  };

  var el = {};

  /* ---------- Narzędzia ---------- */

  function readList(key) {
    try {
      var raw = JSON.parse(localStorage.getItem(key) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch (err) {
      return [];
    }
  }

  function saveList(key, set) {
    try {
      var arr = Array.from(set).slice(-600);
      localStorage.setItem(key, JSON.stringify(arr));
    } catch (err) {
      /* brak miejsca — trudno, działamy dalej */
    }
  }

  function fold(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/ł/g, "l")
      .replace(/Ł/g, "l")
      .toLowerCase();
  }

  function icon(name, size) {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", size || 16);
    svg.setAttribute("height", size || 16);
    svg.setAttribute("aria-hidden", "true");
    var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", "#" + name);
    svg.appendChild(use);
    return svg;
  }

  function isTender(lead) {
    return !!TENDER_SOURCES[lead.source];
  }

  function contactFree(lead) {
    return !lead || lead.contact_free !== false;
  }

  function distanceText(lead) {
    if (lead.distance_km === null || lead.distance_km === undefined) {
      return lead.city || "Opolskie";
    }
    var km = Number(lead.distance_km);
    if (lead.city && fold(lead.city).indexOf("kedzierzyn") === 0) {
      return lead.city;
    }
    if (km < 1) {
      return (lead.city || "Kędzierzyn-Koźle") + " · w mieście";
    }
    return (lead.city ? lead.city + " · " : "") + Math.round(km) + " km";
  }

  function parseDate(value) {
    if (!value) return null;
    var dt = new Date(value);
    return isNaN(dt.getTime()) ? null : dt;
  }

  function relativeDate(value) {
    var dt = parseDate(value);
    if (!dt) return "";
    var diff = Date.now() - dt.getTime();
    var days = Math.floor(diff / 86400000);
    if (days <= 0) return "dziś";
    if (days === 1) return "wczoraj";
    if (days < 7) return days + " dni temu";
    return dt.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit" });
  }

  function deadlineInfo(lead) {
    if (lead.deadline) {
      var dt = parseDate(lead.deadline);
      if (dt) {
        var days = Math.ceil((dt.getTime() - Date.now()) / 86400000);
        var text = "Termin: " + dt.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" });
        return { text: text, soon: days <= 3 };
      }
    }
    if (lead.deadline_text) {
      var raw = String(lead.deadline_text).trim();
      var prefix = /^termin\b/i.test(raw) ? "" : "Termin: ";
      return { text: prefix + raw.charAt(0).toUpperCase() + raw.slice(1), soon: false };
    }
    return null;
  }

  function updatedText(iso) {
    var dt = parseDate(iso);
    if (!dt) return "";
    var today = new Date();
    var sameDay = dt.toDateString() === today.toDateString();
    var time = dt.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
    if (sameDay) return "dziś, " + time;
    return dt.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit" }) + ", " + time;
  }

  function countUnread() {
    var n = 0;
    state.leads.forEach(function (lead) {
      if (lead.is_new && !state.read.has(lead.id) && !state.hidden.has(lead.id)) n += 1;
    });
    return n;
  }

  function toast(message) {
    el.toast.textContent = message;
    el.toast.classList.add("toast--show");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(function () {
      el.toast.classList.remove("toast--show");
    }, 2400);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      try {
        var area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        document.body.removeChild(area);
        resolve();
      } catch (err) {
        reject(err);
      }
    });
  }

  /* ---------- Dane ---------- */

  function fetchJson(url, bust) {
    var target = bust ? url + "?t=" + Date.now() : url;
    return fetch(target, { cache: bust ? "no-store" : "default" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }

  function loadData(options) {
    var bust = options && options.bust;
    state.loading = true;
    state.error = "";
    renderStatus();
    if (!state.leads.length) renderList();

    return Promise.all([fetchJson(DATA_URL, bust), fetchJson(META_URL, bust)])
      .then(function (results) {
        var data = results[0] || {};
        state.leads = Array.isArray(data.leads) ? data.leads : [];
        state.meta = results[1] || {};
        state.loading = false;
        state.error = "";
        renderAll();
        if (bust) toast("Zaktualizowano");
      })
      .catch(function (err) {
        state.loading = false;
        if (!state.leads.length) {
          state.error = "Nie udało się pobrać listy zleceń. Sprawdź internet i spróbuj ponownie.";
        } else {
          toast("Brak internetu — pokazuję ostatnie dane");
        }
        renderAll();
      });
  }

  /* ---------- Filtry i sortowanie ---------- */

  function matches(lead) {
    if (state.hidden.has(lead.id)) return false;
    if (state.onlyNew && !(lead.is_new && !state.read.has(lead.id))) return false;
    if (state.onlyFree && !contactFree(lead)) return false;

    if (state.filter === "tender") {
      if (!isTender(lead)) return false;
    } else if (state.filter !== "all") {
      if (lead.service !== state.filter) return false;
    }

    if (state.query) {
      var needle = fold(state.query);
      var hay = fold(
        [lead.title, lead.description, lead.city, lead.organization, lead.cpv, lead.service_label]
          .filter(Boolean)
          .join(" ")
      );
      if (hay.indexOf(needle) === -1) return false;
    }
    return true;
  }

  function visibleLeads() {
    var list = state.leads.filter(matches);
    if (state.sort === "newest") {
      list.sort(function (a, b) {
        return (parseDate(b.published_at || b.first_seen) || 0) - (parseDate(a.published_at || a.first_seen) || 0);
      });
    } else if (state.sort === "nearest") {
      list.sort(function (a, b) {
        var da = a.distance_km === null || a.distance_km === undefined ? 999 : Number(a.distance_km);
        var db = b.distance_km === null || b.distance_km === undefined ? 999 : Number(b.distance_km);
        if (da !== db) return da - db;
        return (b.score || 0) - (a.score || 0);
      });
    } else {
      list.sort(function (a, b) {
        var af = contactFree(a) ? 1 : 0;
        var bf = contactFree(b) ? 1 : 0;
        if (bf !== af) return bf - af;
        return (b.score || 0) - (a.score || 0);
      });
    }
    return list;
  }

  function filterCount(id) {
    return state.leads.filter(function (lead) {
      if (state.hidden.has(lead.id)) return false;
      if (id === "tender") return isTender(lead);
      if (id === "all") return true;
      return lead.service === id;
    }).length;
  }

  /* ---------- Render ---------- */

  function renderStatus() {
    var meta = state.meta || {};
    var unread = countUnread();
    if (state.loading && !state.leads.length) {
      el.statusText.textContent = "Ładowanie zleceń…";
      el.statusDot.classList.remove("statusline__dot--warn");
      return;
    }
    if (state.error) {
      el.statusText.textContent = "Brak połączenia z listą";
      el.statusDot.classList.add("statusline__dot--warn");
      return;
    }
    var parts = [];
    parts.push(state.leads.length + " zleceń");
    if (unread > 0) parts.push(unread + " nowych");
    if (meta.updated) parts.push("aktualizacja " + updatedText(meta.updated));
    el.statusText.textContent = parts.join(" · ");
    el.statusDot.classList.toggle("statusline__dot--warn", !navigator.onLine);
  }

  function renderChips() {
    el.chips.textContent = "";
    SERVICE_FILTERS.forEach(function (item) {
      var count = filterCount(item.id);
      var button = document.createElement("button");
      button.type = "button";
      button.className = "chip" + (state.filter === item.id ? " chip--active" : "");
      button.setAttribute("aria-pressed", state.filter === item.id ? "true" : "false");
      button.appendChild(document.createTextNode(item.label));
      var badge = document.createElement("span");
      badge.className = "chip__count";
      badge.textContent = count;
      button.appendChild(badge);
      button.addEventListener("click", function () {
        state.filter = item.id;
        localStorage.setItem(KEYS.filter, item.id);
        renderChips();
        renderList();
      });
      el.chips.appendChild(button);
    });
  }

  function renderList() {
    el.list.textContent = "";

    if (state.loading && !state.leads.length) {
      for (var i = 0; i < 5; i += 1) {
        var skeleton = document.createElement("div");
        skeleton.className = "skeleton";
        el.list.appendChild(skeleton);
      }
      el.listTitle.textContent = "Zlecenia";
      el.listFootnote.textContent = "";
      updateNewLabel();
    updateFreeLabel();
      return;
    }

    if (state.error) {
      el.list.appendChild(emptyState("Brak danych", state.error, "Spróbuj ponownie", function () {
        loadData({ bust: true });
      }));
      el.listTitle.textContent = "Zlecenia";
      el.listFootnote.textContent = "";
      updateNewLabel();
    updateFreeLabel();
      return;
    }

    var list = visibleLeads();
    var label = "Zlecenia";
    SERVICE_FILTERS.forEach(function (item) {
      if (item.id === state.filter) label = item.id === "all" ? "Wszystkie zlecenia" : item.label;
    });
    el.listTitle.textContent = label + " · " + list.length;

    if (!list.length) {
      var hasFilters = state.filter !== "all" || state.query || state.onlyNew;
      el.list.appendChild(
        emptyState(
          "Nic nie znaleziono",
          hasFilters ? "Zmień filtr albo wyczyść wyszukiwanie." : "Poczekaj — nowe zlecenia pojawiają się co 30 minut.",
          hasFilters ? "Wyczyść filtry" : "",
          hasFilters
            ? function () {
                state.filter = "all";
                state.query = "";
                state.onlyNew = false;
                el.searchInput.value = "";
                el.searchWrap.classList.remove("search--filled");
                localStorage.setItem(KEYS.filter, "all");
                localStorage.setItem(KEYS.onlyNew, "0");
                renderChips();
                renderList();
              }
            : null
        )
      );
    } else {
      var fragment = document.createDocumentFragment();
      list.forEach(function (lead) {
        fragment.appendChild(leadCard(lead));
      });
      el.list.appendChild(fragment);
    }

    updateNewLabel();
    updateFreeLabel();
    renderFootnote(list.length);
    renderStatus();
  }

  function emptyState(title, text, actionLabel, action) {
    var box = document.createElement("div");
    box.className = "empty";
    var iconBox = document.createElement("div");
    iconBox.className = "empty__icon";
    iconBox.appendChild(icon(state.error ? "i-info" : "i-search", 24));
    box.appendChild(iconBox);
    var h = document.createElement("h3");
    h.textContent = title;
    box.appendChild(h);
    var p = document.createElement("p");
    p.textContent = text;
    box.appendChild(p);
    if (actionLabel && action) {
      var wrap = document.createElement("div");
      wrap.style.marginTop = "16px";
      var button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn--gold";
      button.textContent = actionLabel;
      button.addEventListener("click", action);
      wrap.appendChild(button);
      box.appendChild(wrap);
    }
    return box;
  }

  function leadCard(lead) {
    var card = document.createElement("article");
    var isNew = lead.is_new && !state.read.has(lead.id);
    card.className = "card" + (isNew ? " card--new" : "");
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", lead.title);

    var top = document.createElement("div");
    top.className = "card__top";

    var score = document.createElement("span");
    score.className = "badge badge--score";
    score.textContent = (lead.score || 0) + "/100";
    top.appendChild(score);

    if (isNew) {
      var newBadge = document.createElement("span");
      newBadge.className = "badge badge--new";
      newBadge.textContent = "Nowe";
      top.appendChild(newBadge);
    }

    if (isTender(lead)) {
      var tender = document.createElement("span");
      tender.className = "badge badge--tender";
      tender.textContent = "Przetarg";
      top.appendChild(tender);
    }

    var service = document.createElement("span");
    service.className = "badge badge--service";
    service.textContent = lead.service_label || "Budowlane";
    top.appendChild(service);

    var contactBadge = document.createElement("span");
    contactBadge.className = "badge " + (contactFree(lead) ? "badge--contact-free" : "badge--contact-paid");
    contactBadge.textContent = contactFree(lead) ? "Kontakt darmowy" : "Kontakt płatny";
    top.appendChild(contactBadge);

    card.appendChild(top);

    var title = document.createElement("h3");
    title.className = "card__title";
    title.textContent = lead.title || "Ogłoszenie budowlane";
    card.appendChild(title);

    var meta = document.createElement("div");
    meta.className = "card__meta";

    var place = document.createElement("span");
    place.appendChild(icon("i-pin", 14));
    place.appendChild(document.createTextNode(distanceText(lead)));
    meta.appendChild(place);

    var when = relativeDate(lead.published_at || lead.first_seen);
    if (when) {
      var time = document.createElement("span");
      time.appendChild(icon("i-clock", 14));
      time.appendChild(document.createTextNode(when));
      meta.appendChild(time);
    }

    card.appendChild(meta);

    var foot = document.createElement("div");
    foot.className = "card__foot";

    var source = document.createElement("span");
    source.textContent = lead.source_label || "Ogłoszenie";
    foot.appendChild(source);

    var deadline = deadlineInfo(lead);
    if (deadline) {
      var dl = document.createElement("span");
      dl.className = "deadline" + (deadline.soon ? " deadline--soon" : "");
      dl.textContent = deadline.text;
      foot.appendChild(dl);
    } else if (lead.organization) {
      var org = document.createElement("span");
      org.textContent = lead.organization;
      foot.appendChild(org);
    }

    card.appendChild(foot);

    function open() {
      openSheet(lead);
    }

    card.addEventListener("click", open);
    card.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });

    return card;
  }

  function updateNewLabel() {
    var unread = countUnread();
    el.onlyNewLabel.textContent = unread > 0 ? "Tylko nowe (" + unread + ")" : "Tylko nowe";
    el.onlyNew.classList.toggle("toggle--on", state.onlyNew);
    el.onlyNew.setAttribute("aria-pressed", state.onlyNew ? "true" : "false");
  }

  function updateFreeLabel() {
    var freeCount = state.leads.filter(function (lead) {
      return !state.hidden.has(lead.id) && contactFree(lead);
    }).length;
    el.onlyFreeLabel.textContent = "Darmowy kontakt (" + freeCount + ")";
    el.onlyFree.classList.toggle("toggle--on", state.onlyFree);
    el.onlyFree.setAttribute("aria-pressed", state.onlyFree ? "true" : "false");
  }

  function renderFootnote(shown) {
    var meta = state.meta || {};
    var parts = [];
    if (meta.updated) parts.push("Ostatnia aktualizacja: " + updatedText(meta.updated));
    if (typeof shown === "number") parts.push("pokazano " + shown + " z " + state.leads.length);
    if (meta.radius_km) parts.push("zasięg ok. " + meta.radius_km + " km");
    el.listFootnote.textContent = parts.join(" · ");
  }

  function renderSources() {
    var meta = state.meta || {};
    var sources = Array.isArray(meta.sources) ? meta.sources : [];
    el.sourcesPanel.textContent = "";
    if (!sources.length) {
      var row = document.createElement("div");
      row.className = "src-row";
      row.textContent = "Brak danych o źródłach.";
      el.sourcesPanel.appendChild(row);
      return;
    }
    sources.forEach(function (source) {
      var row = document.createElement("div");
      row.className = "src-row";

      var dot = document.createElement("span");
      dot.className = "src-row__dot" + (source.status === "error" ? " src-row__dot--err" : "");
      row.appendChild(dot);

      var name = document.createElement("span");
      name.className = "src-row__name";
      name.textContent = source.label || source.id;
      row.appendChild(name);

      var note = document.createElement("span");
      note.className = "src-row__note";
      if (source.status === "error") {
        note.textContent = "chwilowy błąd";
      } else if (source.status === "off") {
        note.textContent = "wyłączone";
      } else {
        note.textContent = source.count + " ogł.";
      }
      row.appendChild(note);

      el.sourcesPanel.appendChild(row);
    });
  }

  function renderNotificationPanel() {
    var meta = state.meta || {};
    var topic = meta.ntfy_topic || "";
    el.topicText.textContent = topic || "temat nieustawiony";
    el.ntfyLink.href = topic ? "ntfy://ntfy.sh/" + topic : "https://ntfy.sh";
    el.ntfyLink.style.opacity = topic ? "1" : "0.5";
    el.ntfyLink.style.pointerEvents = topic ? "auto" : "none";
  }

  function renderTab() {
    ["leads", "search", "info"].forEach(function (name) {
      var page = document.getElementById("page-" + name);
      if (page) page.classList.toggle("page--active", state.tab === name);
    });
    Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (button) {
      var active = button.getAttribute("data-tab") === state.tab;
      button.classList.toggle("tab--active", active);
      if (active) {
        button.setAttribute("aria-current", "page");
      } else {
        button.removeAttribute("aria-current");
      }
    });
    window.scrollTo(0, 0);
  }

  function renderAll() {
    renderStatus();
    renderChips();
    renderList();
    renderSources();
    renderNotificationPanel();
    updateRestoreLabel();
  }

  function updateRestoreLabel() {
    el.restoreLabel.textContent = "Pokaż ukryte (" + state.hidden.size + ")";
    el.restoreHidden.disabled = state.hidden.size === 0;
    el.restoreHidden.style.opacity = state.hidden.size ? "1" : "0.45";
  }

  /* ---------- Szczegóły ---------- */

  function openSheet(lead) {
    if (lead.is_new && !state.read.has(lead.id)) {
      state.read.add(lead.id);
      saveList(KEYS.read, state.read);
      renderList();
    }

    el.sheetBody.textContent = "";

    var top = document.createElement("div");
    top.className = "sheet__meta";

    var score = document.createElement("span");
    score.className = "badge badge--score";
    score.textContent = "Trafność " + (lead.score || 0) + "/100 · " + (lead.score_label || "");
    top.appendChild(score);

    if (isTender(lead)) {
      var tender = document.createElement("span");
      tender.className = "badge badge--tender";
      tender.textContent = "Przetarg publiczny";
      top.appendChild(tender);
    }

    var service = document.createElement("span");
    service.className = "badge badge--service";
    service.textContent = lead.service_label || "Budowlane";
    top.appendChild(service);

    el.sheetBody.appendChild(top);

    var title = document.createElement("h2");
    title.className = "sheet__title";
    title.id = "sheetTitle";
    title.textContent = lead.title || "Ogłoszenie budowlane";
    el.sheetBody.appendChild(title);

    if (lead.description) {
      addSection("Opis", lead.description);
    }

    var details = document.createElement("dl");
    details.className = "kv";
    addRow(details, "Lokalizacja", distanceText(lead));
    if (lead.organization) addRow(details, "Zamawiający", lead.organization);
    var deadline = deadlineInfo(lead);
    if (deadline) addRow(details, "Termin", deadline.text.replace("Termin: ", ""));
    var published = parseDate(lead.published_at);
    if (published) {
      addRow(details, "Opublikowano", published.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" }));
    }
    addRow(details, "Źródło", lead.source_label || "—");
    addRow(details, "Kontakt", contactFree(lead) ? "Darmowy (dane w ogłoszeniu)" : "Płatny — Oferteo pobiera opłatę za kontakt");
    if (Array.isArray(lead.also) && lead.also.length) {
      addRow(details, "Także w", lead.also.join(", "));
    }
    var section = document.createElement("div");
    section.className = "sheet__section";
    section.appendChild(details);
    el.sheetBody.appendChild(section);

    if (Array.isArray(lead.reasons) && lead.reasons.length) {
      addSection("Dlaczego pasuje", lead.reasons.join("\n"));
    }

    if (lead.source === "oferteo") {
      var hint = document.createElement("p");
      hint.className = "footnote";
      hint.style.paddingLeft = "0";
      hint.textContent =
        "Kontakt do zleceniodawcy jest widoczny po zalogowaniu na Oferteo. Możesz też odpowiedzieć na ogłoszenie przez formularz serwisu.";
      el.sheetBody.appendChild(hint);
    }

    var actions = document.createElement("div");
    actions.className = "sheet__actions";

    if (lead.url) {
      var open = document.createElement("a");
      open.className = "btn btn--gold btn--block";
      open.href = lead.url;
      open.target = "_blank";
      open.rel = "noopener";
      open.appendChild(icon("i-external", 17));
      var openLabel = "Otwórz ogłoszenie";
      if (lead.source === "bzp") openLabel = "Otwórz w BZP";
      if (lead.source === "oferteo") openLabel = "Otwórz listę na Oferteo";
      open.appendChild(document.createTextNode(openLabel));
      actions.appendChild(open);
    }

    var copy = document.createElement("button");
    copy.type = "button";
    copy.className = "btn btn--block";
    copy.appendChild(icon("i-copy", 17));
    copy.appendChild(document.createTextNode("Kopiuj notatkę"));
    copy.addEventListener("click", function () {
      copyText(noteText(lead))
        .then(function () {
          toast("Skopiowano notatkę");
        })
        .catch(function () {
          toast("Nie udało się skopiować");
        });
    });
    actions.appendChild(copy);

    var hide = document.createElement("button");
    hide.type = "button";
    hide.className = "btn btn--block";
    hide.appendChild(icon("i-x", 17));
    hide.appendChild(document.createTextNode("Ukryj to zlecenie"));
    hide.addEventListener("click", function () {
      state.hidden.add(lead.id);
      saveList(KEYS.hidden, state.hidden);
      closeSheet();
      renderAll();
      toast("Ukryto — wróć do „Info”, aby przywrócić");
    });
    actions.appendChild(hide);

    el.sheetBody.appendChild(actions);

    el.backdrop.classList.add("sheet-backdrop--open");
    el.sheet.classList.add("sheet--open");
    document.body.style.overflow = "hidden";
    el.sheetBody.scrollTop = 0;

    function addSection(label, text) {
      var wrap = document.createElement("div");
      wrap.className = "sheet__section";
      var heading = document.createElement("div");
      heading.className = "sheet__label";
      heading.textContent = label;
      wrap.appendChild(heading);
      var body = document.createElement("p");
      body.className = "sheet__text";
      body.textContent = text;
      wrap.appendChild(body);
      el.sheetBody.appendChild(wrap);
    }

    function addRow(dl, label, value) {
      var row = document.createElement("div");
      var dt = document.createElement("dt");
      dt.textContent = label;
      var dd = document.createElement("dd");
      dd.textContent = value;
      row.appendChild(dt);
      row.appendChild(dd);
      dl.appendChild(row);
    }
  }

  function closeSheet() {
    el.backdrop.classList.remove("sheet-backdrop--open");
    el.sheet.classList.remove("sheet--open");
    document.body.style.overflow = "";
  }

  function noteText(lead) {
    var lines = [];
    lines.push((lead.service_label || "Zlecenie") + " — " + (lead.score || 0) + "/100");
    lines.push(lead.title || "");
    lines.push("Lokalizacja: " + distanceText(lead));
    var deadline = deadlineInfo(lead);
    if (deadline) lines.push(deadline.text);
    if (lead.organization) lines.push("Zamawiający: " + lead.organization);
    lines.push("Źródło: " + (lead.source_label || ""));
    lines.push("Kontakt: " + (contactFree(lead) ? "darmowy" : "płatny (Oferteo)"));
    if (lead.url) lines.push(lead.url);
    return lines.join("\n");
  }

  /* ---------- Zdarzenia ---------- */

  function bindEvents() {
    el.refreshBtn.addEventListener("click", function () {
      var svg = el.refreshBtn.querySelector("svg");
      svg.classList.add("spin");
      el.refreshBtn.disabled = true;
      loadData({ bust: true }).then(function () {
        svg.classList.remove("spin");
        el.refreshBtn.disabled = false;
      });
    });

    el.searchInput.addEventListener("input", function () {
      state.query = el.searchInput.value.trim();
      el.searchWrap.classList.toggle("search--filled", !!state.query);
      renderList();
    });

    el.searchClear.addEventListener("click", function () {
      el.searchInput.value = "";
      state.query = "";
      el.searchWrap.classList.remove("search--filled");
      renderList();
      el.searchInput.focus();
    });

    el.onlyNew.addEventListener("click", function () {
      state.onlyNew = !state.onlyNew;
      localStorage.setItem(KEYS.onlyNew, state.onlyNew ? "1" : "0");
      renderList();
    });

    el.onlyFree.addEventListener("click", function () {
      state.onlyFree = !state.onlyFree;
      localStorage.setItem(KEYS.onlyFree, state.onlyFree ? "1" : "0");
      renderList();
    });

    el.sortSelect.addEventListener("change", function () {
      state.sort = el.sortSelect.value;
      localStorage.setItem(KEYS.sort, state.sort);
      renderList();
    });

    Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (button) {
      button.addEventListener("click", function () {
        state.tab = button.getAttribute("data-tab") || "leads";
        renderTab();
      });
    });

    el.backdrop.addEventListener("click", closeSheet);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && el.sheet.classList.contains("sheet--open")) closeSheet();
    });

    el.copyTopic.addEventListener("click", function () {
      copyText(el.topicText.textContent).then(function () {
        toast("Skopiowano temat");
      });
    });
    el.copyTopic2.addEventListener("click", function () {
      copyText(el.topicText.textContent).then(function () {
        toast("Skopiowano temat");
      });
    });

    el.restoreHidden.addEventListener("click", function () {
      if (!state.hidden.size) return;
      state.hidden.clear();
      saveList(KEYS.hidden, state.hidden);
      renderAll();
      toast("Przywrócono ukryte zlecenia");
    });

    window.addEventListener("online", renderStatus);
    window.addEventListener("offline", renderStatus);

    window.addEventListener("pageshow", function (event) {
      if (event.persisted) renderList();
    });
  }

  function maybeShowInstallHint() {
    try {
      var dismissed = localStorage.getItem(KEYS.hint) === "1";
      var standalone =
        window.navigator.standalone === true ||
        (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches);
      var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
      if (!dismissed && isIOS && !standalone) {
        el.installHint.classList.add("install-hint--show");
        el.installHint.addEventListener("click", function () {
          el.installHint.classList.remove("install-hint--show");
          localStorage.setItem(KEYS.hint, "1");
        });
      }
    } catch (err) {
      /* tryb prywatny — pomijamy podpowiedź */
    }
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    if (location.protocol !== "https:" && location.hostname !== "localhost") return;
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () {
        /* brak SW nie blokuje aplikacji */
      });
    });
  }

  function init() {
    el = {
      statusText: document.getElementById("statusText"),
      statusDot: document.getElementById("statusDot"),
      searchWrap: document.getElementById("searchWrap"),
      searchInput: document.getElementById("searchInput"),
      searchClear: document.getElementById("searchClear"),
      chips: document.getElementById("chips"),
      onlyNew: document.getElementById("onlyNew"),
      onlyNewLabel: document.getElementById("onlyNewLabel"),
      onlyFree: document.getElementById("onlyFree"),
      onlyFreeLabel: document.getElementById("onlyFreeLabel"),
      sortSelect: document.getElementById("sortSelect"),
      installHint: document.getElementById("installHint"),
      list: document.getElementById("list"),
      listTitle: document.getElementById("listTitle"),
      listFootnote: document.getElementById("listFootnote"),
      sourcesPanel: document.getElementById("sourcesPanel"),
      topicText: document.getElementById("topicText"),
      ntfyLink: document.getElementById("ntfyLink"),
      copyTopic: document.getElementById("copyTopic"),
      copyTopic2: document.getElementById("copyTopic2"),
      restoreHidden: document.getElementById("restoreHidden"),
      restoreLabel: document.getElementById("restoreLabel"),
      refreshBtn: document.getElementById("refreshBtn"),
      sheet: document.getElementById("sheet"),
      sheetBody: document.getElementById("sheetBody"),
      backdrop: document.getElementById("backdrop"),
      toast: document.getElementById("toast"),
    };

    el.sortSelect.value = state.sort;
    el.searchInput.value = "";
    bindEvents();
    maybeShowInstallHint();
    renderAll();
    loadData({});
    registerServiceWorker();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
