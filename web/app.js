const $ = (id) => document.getElementById(id);

const form = $("form");
const city = $("city");
const statusEl = $("status");
let coords = null;
let currentTicket = null;
let pocketTimer = null;

function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function fmtDate(isoDay) {
  const d = new Date(isoDay + "T12:00:00");
  return d.toLocaleDateString([], {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

async function loadPlaces() {
  const res = await fetch("/api/places");
  const data = await res.json();
  city.innerHTML = "";
  const here = document.createElement("option");
  here.value = "";
  here.textContent = "Pick a city, or use your door";
  city.append(here);
  for (const p of data.places) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name;
    city.append(opt);
  }
  city.value = "delhi";
  const today = new Date().toISOString().slice(0, 10);
  $("when").value = today;
}

$("geo").addEventListener("click", () => {
  if (!navigator.geolocation) {
    $("geo-status").textContent = "This browser will not share a location.";
    return;
  }
  $("geo-status").textContent = "Asking for the door…";
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      coords = {
        lat: pos.coords.latitude,
        lon: pos.coords.longitude,
        offset: -new Date().getTimezoneOffset() / 60,
      };
      city.value = "";
      $("geo-status").textContent = `Door at ${coords.lat.toFixed(3)}°, ${coords.lon.toFixed(3)}°. Issued locally.`;
    },
    () => {
      $("geo-status").textContent = "Location refused. A city still works.";
    },
    { enableHighAccuracy: false, timeout: 8000 }
  );
});

document.querySelectorAll(".seg").forEach((group) => {
  group.addEventListener("change", () => {
    group.querySelectorAll("label").forEach((label) => {
      label.classList.toggle("on", label.querySelector("input").checked);
    });
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusEl.textContent = "Waiting on the light…";
  $("go").disabled = true;
  const duration = Number(form.duration.value);
  const sky = form.sky.value;
  const ground = form.ground.value;
  const body = { duration_min: duration, sky, ground };
  const whenValue = $("when").value;
  if (whenValue) body.when = whenValue;
  const tempValue = $("temp").value;
  if (tempValue !== "") body.temp_c = Number(tempValue);
  if (coords) {
    body.lat = coords.lat;
    body.lon = coords.lon;
    body.offset_hours = coords.offset;
  } else if (city.value) {
    body.city_id = city.value;
  } else {
    statusEl.textContent = "Pick a city or use your door.";
    $("go").disabled = false;
    return;
  }
  try {
    const res = await fetch("/api/ticket", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Could not issue a ticket.");
    }
    const ticket = await res.json();
    render(ticket);
    statusEl.textContent = "";
  } catch (err) {
    statusEl.textContent = err.message;
  } finally {
    $("go").disabled = false;
  }
});

function render(t) {
  currentTicket = t;
  $("result").hidden = false;
  $("serial").textContent = `No. ${t.serial}`;
  $("when-line").textContent = `${fmtDate(t.date)}  ·  ${t.place}`;
  $("title").textContent = t.copy.title;
  $("lede").textContent = t.copy.lede;
  $("leave").textContent = fmtTime(t.leave_by);
  $("sunset").textContent = fmtTime(t.sun.sunset);
  $("heading").textContent = t.sun.heading;
  $("about").textContent = `${t.duration_min} min · ${t.distance_m} m · ${t.temp_c_estimate.toFixed(0)}°C`;
  $("route").textContent = t.copy.route;
  $("cues").innerHTML = "";
  t.copy.cues.forEach((cue) => {
    const li = document.createElement("li");
    li.textContent = cue;
    $("cues").append(li);
  });
  $("rule").textContent = t.copy.rule;
  $("writer").textContent =
    t.copy.writer === "gemma"
      ? `Copy: ${t.copy.model}`
      : "Copy: field recipes · offline";
  $("score-line").textContent = `Score ${t.score.toFixed(0)} · ${t.score_source}`;
  $("verdict").textContent = `${t.verdict} · ${t.temp_c_estimate.toFixed(0)}°C feels right`;
  $("foliage").textContent = t.foliage_note;
  $("meter").style.width = `${Math.min(100, Math.max(0, t.score))}%`;
  const mae = t.engine.tabpfn_mae;
  $("engine").textContent = mae
    ? `TabPFN MAE ${mae.toFixed(2)} vs ridge ${t.engine.ridge_mae.toFixed(2)} on held-out dusk rows.`
    : `Ridge fallback. TabPFN did not load on this machine.`;
  $("pocket-heading").textContent = `Walk ${t.sun.heading}. ${t.copy.rule}`;
  $("result").scrollIntoView({ behavior: "smooth", block: "start" });
}

$("print").addEventListener("click", () => window.print());

$("pocket").addEventListener("click", () => {
  if (!currentTicket) return;
  $("pocket-ui").hidden = false;
  const end = Date.now() + currentTicket.duration_min * 60 * 1000;
  const tick = () => {
    const left = Math.max(0, end - Date.now());
    const m = Math.floor(left / 60000);
    const s = Math.floor((left % 60000) / 1000);
    $("pocket-time").textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    if (left <= 0) {
      $("pocket-sub").textContent = "You can go back in. Or stay out.";
      clearInterval(pocketTimer);
    }
  };
  tick();
  clearInterval(pocketTimer);
  pocketTimer = setInterval(tick, 250);
});

$("pocket-exit").addEventListener("click", () => {
  $("pocket-ui").hidden = true;
  clearInterval(pocketTimer);
});

$("speak").addEventListener("click", async () => {
  if (!currentTicket) return;
  const t = currentTicket;
  const text = [
    t.copy.title + ".",
    `Leave by ${fmtTime(t.leave_by)}. Walk toward ${t.sun.heading}.`,
    t.copy.lede,
    t.copy.cues.join(" "),
    t.copy.rule,
  ].join(" ");
  try {
    const res = await fetch("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
      return;
    }
  } catch {
    /* browser voice is enough */
  }
  if (!window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.92;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
});

$("note-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!currentTicket) return;
  const note = $("note").value.trim();
  const key = "lastlight-notes";
  const all = JSON.parse(localStorage.getItem(key) || "[]");
  all.unshift({
    at: new Date().toISOString(),
    serial: currentTicket.serial,
    place: currentTicket.place,
    note,
  });
  localStorage.setItem(key, JSON.stringify(all.slice(0, 40)));
  $("note-status").textContent = note
    ? "Kept on this device. Not sent anywhere."
    : "Empty note ignored.";
});

loadPlaces().catch(() => {
  statusEl.textContent = "Could not load cities. Is the server up?";
});
