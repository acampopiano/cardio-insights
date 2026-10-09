/* Captura el tablero embebido por separado y lo pega bajo el header. */
const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const path = require("path");
const puppeteer = require("puppeteer");

const MB = "http://localhost:3001";
const OUT = path.join(__dirname, "capturas");
const PORT = 5602;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

let cookie = null;

async function api(method, endpoint, body) {
  const headers = { "Content-Type": "application/json" };
  if (cookie) headers.Cookie = cookie;
  const res = await fetch(MB + endpoint, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const jar = res.headers.getSetCookie ? res.headers.getSetCookie() : [];
  const session = jar.find((c) => c.startsWith("metabase.SESSION="));
  if (session) cookie = session.split(";")[0];
  const text = await res.text();
  if (!res.ok) throw new Error(`${method} ${endpoint} -> ${res.status}\n${text.slice(0, 400)}`);
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return text;
  }
}

function b64url(input) {
  return Buffer.from(input).toString("base64").replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function signJwt(payload, secret) {
  const head = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = b64url(JSON.stringify(payload));
  const sig = b64url(crypto.createHmac("sha256", secret).update(`${head}.${body}`).digest());
  return `${head}.${body}.${sig}`;
}

function wrapperHtml(embedDataUri) {
  return `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Cardio Insights — KPIs</title>
<style>
  :root { --deep:#0d3b66; --primary:#2e8bce; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:"Segoe UI",system-ui,sans-serif; background:#f6f8fa; }
  header { height:56px; background:var(--deep); color:#fff; display:flex; align-items:center;
           justify-content:space-between; padding:0 22px; }
  .brand { display:flex; align-items:center; gap:10px; font-weight:600; font-size:15px; }
  .logo { width:26px; height:26px; border-radius:7px; background:var(--primary);
          display:grid; place-items:center; font-size:12px; font-weight:700; }
  .user { display:flex; align-items:center; gap:9px; font-size:13px; }
  .avatar { width:32px; height:32px; border-radius:50%; background:rgba(255,255,255,.16);
            display:grid; place-items:center; font-size:11px; font-weight:600;
            border:2px solid rgba(46,139,206,.7); }
  main { padding:18px 22px 22px; }
  .card { background:#fff; border:1px solid #e5e7eb; border-radius:12px; overflow:hidden;
          box-shadow:0 1px 2px rgba(16,24,40,.05); }
  .card img { width:100%; display:block; }
</style>
</head>
<body>
<header>
  <div class="brand"><div class="logo">CI</div> Cardio Insights</div>
  <div class="user"><span>Equipo</span><div class="avatar">EC</div></div>
</header>
<main>
  <div class="card" id="card">
    <img src="${embedDataUri}" alt="Tablero embebido de Metabase">
  </div>
</main>
</body>
</html>`;
}

async function main() {
  await api("POST", "/api/session", {
    username: "poc@cardioinsights.local",
    password: "CardioPoc.2026",
  });
  const secret = await api("GET", "/api/setting/embedding-secret-key");
  const dashboards = await api("GET", "/api/dashboard");
  const dash = (dashboards || []).find((d) => !d.archived);
  if (!dash) throw new Error("no hay tablero activo");

  const token = signJwt(
    {
      resource: { dashboard: dash.id },
      params: {},
      exp: Math.floor(Date.now() / 1000) + 60 * 30,
    },
    typeof secret === "string" ? secret.replace(/"/g, "") : secret
  );
  const embedUrl = `${MB}/embed/dashboard/${token}#bordered=false&titled=false&background=false`;

  const browser = await puppeteer.launch({
    headless: "shell",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 2 });
  await page.goto(embedUrl, { waitUntil: "networkidle2" });
  await wait(8000);
  const tmp = path.join(__dirname, "_embed-only.png");
  await page.screenshot({ path: tmp });
  const dataUri = "data:image/png;base64," + fs.readFileSync(tmp).toString("base64");

  const file = path.join(__dirname, "embed-cardio-insights.html");
  fs.writeFileSync(file, wrapperHtml(dataUri), "utf8");
  const server = http
    .createServer((req, res) => {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(fs.readFileSync(file));
    })
    .listen(PORT);

  await page.setViewport({ width: 1280, height: 860, deviceScaleFactor: 2 });
  await page.goto(`http://localhost:${PORT}/`, { waitUntil: "networkidle2" });
  await wait(1500);
  const height = await page.evaluate(() => {
    const card = document.getElementById("card");
    return Math.ceil(card.getBoundingClientRect().bottom + 22);
  });
  await page.screenshot({
    path: path.join(OUT, "poc-04-embebido-en-la-app.png"),
    clip: { x: 0, y: 0, width: 1280, height },
  });
  console.log("captura lista, alto =", height);

  await browser.close();
  server.close();
  fs.unlinkSync(tmp);
}

main().catch((e) => {
  console.error("ERROR:", e.message || e);
  process.exit(1);
});
