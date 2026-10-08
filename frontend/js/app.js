// Set window.API_BASE before this script in production (e.g. https://api.yourdomain.com)
const API = window.API_BASE || (location.port === "5500" ? "http://localhost:8000" : "");
const BG = ["A+","A-","B+","B-","AB+","AB-","O+","O-"];
const DONORS_FOR = {"O-":["O-"],"O+":["O+","O-"],"A-":["A-","O-"],"A+":["A+","A-","O+","O-"],"B-":["B-","O-"],"B+":["B+","B-","O+","O-"],"AB-":["AB-","A-","B-","O-"],"AB+":BG}; // display only; backend is authoritative
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function toast(msg, type = "info") {
  const t = document.createElement("div"); t.className = "toast " + type; t.setAttribute("role", "status");
  t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 4500);
}
async function api(path, o = {}) {
  const token = localStorage.getItem("bl_token");
  let r;
  try {
    r = await fetch(API + path, { method: o.method || "GET",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) },
      body: o.body ? JSON.stringify(o.body) : undefined });
  } catch { throw new Error("Cannot reach the server. Please try again."); }
  const j = await r.json().catch(() => ({}));
  if (r.status === 401 && token) { logout(); return; }
  if (!r.ok) {
    const d = j.detail;
    throw new Error(Array.isArray(d) ? d.map(e => e.loc.slice(-1) + ": " + e.msg).join("; ") : d || "Something went wrong");
  }
  return j;
}
const logout = () => { localStorage.removeItem("bl_token"); localStorage.removeItem("bl_role"); location.href = "login.html"; };
function requireAuth(role) {
  if (!localStorage.getItem("bl_token")) { location.href = "login.html?next=" + encodeURIComponent(location.pathname.split("/").pop() + location.search); return false; }
  if (role && localStorage.getItem("bl_role") !== role) { toast("This page is for " + role + " accounts.", "error"); return false; }
  return true;
}
function fillBG(sel) { sel.innerHTML = BG.map(g => `<option>${g}</option>`).join(""); }
function loadMaps() {
  return new Promise(async (res, rej) => {
    if (window.google?.maps) return res();
    try {
      const k = (await api("/api/locations/config")).data.google_maps_api_key;
      if (!k) return rej(new Error("Google Maps key not configured"));
      window.__mapsReady = res;
      const s = document.createElement("script");
      s.src = `https://maps.googleapis.com/maps/api/js?key=${k}&libraries=places&callback=__mapsReady`;
      s.onerror = () => rej(new Error("Maps failed to load")); document.head.appendChild(s);
    } catch (e) { rej(e); }
  });
}
function countUp(el) {
  const to = +el.dataset.count, t0 = performance.now();
  (function f(t) { const p = Math.min((t - t0) / 900, 1); el.textContent = Math.round(to * p); if (p < 1) requestAnimationFrame(f); })(t0);
}
document.addEventListener("DOMContentLoaded", () => {
  const authed = !!localStorage.getItem("bl_token");
  const nav = $("#nav");
  if (nav) nav.outerHTML = `<header class="nav"><a class="logo" href="index.html">🩸 BloodLink</a><nav aria-label="Main">
    <a href="request-blood.html">Request Blood</a><a href="find-donors.html">Find Donors</a>
    ${authed ? `<a href="dashboard.html">Dashboard</a>${localStorage.getItem("bl_role")==="admin"?'<a href="admin.html">Admin</a>':""}<a href="#" id="lo">Logout</a>` : `<a href="login.html">Login</a><a class="btn sm" href="register.html">Join</a>`}</nav></header>`;
  $("#lo")?.addEventListener("click", e => { e.preventDefault(); logout(); });
  const f = $("#foot");
  if (f) f.outerHTML = `<footer><p><b>BloodLink</b> is a matching and communication platform only. It does not replace medical professionals or hospital blood-bank procedures, and does not guarantee blood availability. Always verify blood compatibility and donation eligibility with qualified medical staff.</p></footer>`;
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); e.target.querySelectorAll("[data-count]").forEach(countUp); io.unobserve(e.target); } }), { threshold: .15 });
  document.querySelectorAll(".reveal").forEach(el => io.observe(el));
});

/* ---- premium motion ---- */
document.addEventListener("DOMContentLoaded", () => {
  const sp = document.createElement("div"); sp.id = "sp"; document.body.appendChild(sp);
  addEventListener("scroll", () => { const h = document.documentElement; sp.style.width = (h.scrollTop / ((h.scrollHeight - h.clientHeight) || 1) * 100) + "%"; }, { passive: true });
  document.querySelectorAll(".reveal").forEach((el, i) => el.style.transitionDelay = (i % 4) * 90 + "ms");
  document.addEventListener("pointermove", e => { const c = e.target.closest && e.target.closest(".card,.t"); if (!c) return; const r = c.getBoundingClientRect(); c.style.setProperty("--mx", e.clientX - r.left + "px"); c.style.setProperty("--my", e.clientY - r.top + "px"); });
});
document.addEventListener("click", e => {
  const a = e.target.closest && e.target.closest("a[href]");
  if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || a.target || (a.hash && a.pathname === location.pathname)) return;
  const u = new URL(a.href, location); if (u.origin !== location.origin) return;
  e.preventDefault(); document.body.classList.add("leaving"); setTimeout(() => location.href = a.href, 260);
});
addEventListener("pageshow", e => { if (e.persisted) document.body.classList.remove("leaving"); });
