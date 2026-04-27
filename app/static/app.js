const TOKEN_KEY = "netflix_catalog_token";
const USER_KEY = "netflix_catalog_user";
const PAGE_SIZE = 24;

let state = {
  page: 0,
  total: 0,
  filters: {},
};

const $ = (sel) => document.querySelector(sel);

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t, username) {
  localStorage.setItem(TOKEN_KEY, t);
  if (username) localStorage.setItem(USER_KEY, username);
}
function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function api(path, opts = {}) {
  const headers = opts.headers || {};
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401) {
    clearToken();
    showAuth();
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || ("HTTP " + res.status));
  }
  return res.json();
}

/* ---------- Auth UI ---------- */

function showAuth() {
  $("#auth").classList.remove("hidden");
  $("#app").classList.add("hidden");
  $("#user-label").classList.add("hidden");
  $("#logout-btn").classList.add("hidden");
}

function showApp() {
  $("#auth").classList.add("hidden");
  $("#app").classList.remove("hidden");
  const username = localStorage.getItem(USER_KEY);
  if (username) {
    $("#user-label").textContent = username;
    $("#user-label").classList.remove("hidden");
  }
  $("#logout-btn").classList.remove("hidden");
  loadCategories().then(() => search());
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const which = tab.dataset.tab;
    $("#login-form").classList.toggle("hidden", which !== "login");
    $("#register-form").classList.toggle("hidden", which !== "register");
    $("#login-err").textContent = "";
    $("#register-err").textContent = "";
  });
});

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = new URLSearchParams();
  body.set("username", fd.get("username"));
  body.set("password", fd.get("password"));
  try {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.detail || "Login failed");
    }
    const data = await res.json();
    setToken(data.access_token, fd.get("username"));
    showApp();
  } catch (err) {
    $("#login-err").textContent = err.message;
  }
});

$("#register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const res = await fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: fd.get("username"),
        password: fd.get("password"),
      }),
    });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.detail || "Registration failed");
    }
    const data = await res.json();
    setToken(data.access_token, fd.get("username"));
    showApp();
  } catch (err) {
    $("#register-err").textContent = err.message;
  }
});

$("#logout-btn").addEventListener("click", () => {
  clearToken();
  showAuth();
});

/* ---------- Filters / Search ---------- */

async function loadCategories() {
  try {
    const cats = await api("/categories");
    fillSelect($("#f-type"), cats.types);
    fillSelect($("#f-genre"), cats.genres);
    fillSelect($("#f-rating"), cats.ratings);
  } catch (err) {
    console.error(err);
  }
}

function fillSelect(el, values) {
  const current = el.value;
  el.innerHTML = '<option value="">Any</option>';
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    el.appendChild(opt);
  }
  if (current) el.value = current;
}

function readFilters() {
  return {
    q: $("#f-q").value.trim(),
    type: $("#f-type").value,
    genre: $("#f-genre").value,
    rating: $("#f-rating").value,
    country: $("#f-country").value.trim(),
    year_from: $("#f-year-from").value,
    year_to: $("#f-year-to").value,
  };
}

async function search() {
  const f = readFilters();
  state.filters = f;

  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (v !== "" && v != null) params.set(k, v);
  }
  params.set("limit", PAGE_SIZE);
  params.set("offset", state.page * PAGE_SIZE);

  $("#status").textContent = "Searching...";
  $("#grid").innerHTML = "";

  try {
    const data = await api("/shows?" + params.toString());
    state.total = data.total;
    renderResults(data.items);
    updatePager();
  } catch (err) {
    $("#status").textContent = "Error: " + err.message;
  }
}

function renderResults(items) {
  const grid = $("#grid");
  if (!items.length) {
    grid.innerHTML = '<div class="empty">No titles match your filters.</div>';
    $("#status").textContent = "0 results";
    return;
  }

  $("#status").textContent =
    state.total + " result" + (state.total === 1 ? "" : "s");

  const frag = document.createDocumentFragment();
  for (const s of items) {
    const card = document.createElement("article");
    card.className = "card";
    const isTV = s.type === "TV Show";
    card.innerHTML = `
      <span class="badge ${isTV ? "tv" : ""}">${escapeHtml(s.type || "—")}</span>
      <h3>${escapeHtml(s.title || "Untitled")}</h3>
      <div class="meta">${escapeHtml(s.release_year || "")} · ${escapeHtml(s.rating || "—")} · ${escapeHtml(s.duration || "")}</div>
      <div class="desc">${escapeHtml(s.description || "")}</div>
    `;
    card.addEventListener("click", () => openModal(s));
    frag.appendChild(card);
  }
  grid.appendChild(frag);
}

function updatePager() {
  const totalPages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
  $("#page-label").textContent = (state.page + 1) + " / " + totalPages;
  $("#prev-btn").disabled = state.page === 0;
  $("#next-btn").disabled = state.page >= totalPages - 1;
}

function openModal(s) {
  const body = $("#modal-body");
  body.innerHTML = `
    <h2>${escapeHtml(s.title || "Untitled")}</h2>
    <dl>
      <dt>Type</dt><dd>${escapeHtml(s.type || "—")}</dd>
      <dt>Year</dt><dd>${escapeHtml(s.release_year || "—")}</dd>
      <dt>Rating</dt><dd>${escapeHtml(s.rating || "—")}</dd>
      <dt>Duration</dt><dd>${escapeHtml(s.duration || "—")}</dd>
      <dt>Genres</dt><dd>${escapeHtml(s.listed_in || "—")}</dd>
      <dt>Country</dt><dd>${escapeHtml(s.country || "—")}</dd>
      <dt>Director</dt><dd>${escapeHtml(s.director || "—")}</dd>
      <dt>Cast</dt><dd>${escapeHtml(s.cast || "—")}</dd>
      <dt>Added</dt><dd>${escapeHtml(s.date_added || "—")}</dd>
    </dl>
    <p style="margin-top:18px">${escapeHtml(s.description || "")}</p>
  `;
  $("#modal").classList.remove("hidden");
}

$("#modal-close").addEventListener("click", () => $("#modal").classList.add("hidden"));
$("#modal").addEventListener("click", (e) => {
  if (e.target.id === "modal") $("#modal").classList.add("hidden");
});

$("#apply-btn").addEventListener("click", () => {
  state.page = 0;
  search();
});
$("#reset-btn").addEventListener("click", () => {
  ["f-q", "f-type", "f-genre", "f-rating", "f-country", "f-year-from", "f-year-to"]
    .forEach((id) => { $("#" + id).value = ""; });
  state.page = 0;
  search();
});
$("#prev-btn").addEventListener("click", () => {
  if (state.page > 0) { state.page--; search(); }
});
$("#next-btn").addEventListener("click", () => {
  state.page++; search();
});
$("#f-q").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { state.page = 0; search(); }
});

function escapeHtml(v) {
  if (v == null) return "";
  return String(v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/* ---------- Boot ---------- */

if (getToken()) {
  showApp();
} else {
  showAuth();
}
