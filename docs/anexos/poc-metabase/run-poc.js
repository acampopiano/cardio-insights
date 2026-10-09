/* POC Metabase: configura una instancia local por API y captura la evidencia. */
const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const path = require("path");
const puppeteer = require("puppeteer");

const MB = "http://localhost:3001";
const OUT = path.join(__dirname, "capturas");
const WRAP_PORT = 5599;
const EMBED_SECRET = crypto.randomBytes(32).toString("hex");

const DB = {
  name: "INCC (base de prueba)",
  host: "cardio-insights-mysql",
  port: 3306,
  dbname: "incc",
  user: "cardio",
  password: "cardio",
};

const SQL = `SELECT CAST(YEAR(FechaRealizado) AS CHAR) AS anio,
       CASE CodSeguroCoo
            WHEN 10 THEN 'FNR'
            WHEN 20 THEN 'Particular'
            ELSE 'Otro'
       END AS financiador,
       COUNT(*) AS actos
FROM flow_coordina
GROUP BY anio, financiador
ORDER BY anio, financiador`;

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
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    throw new Error(`${method} ${endpoint} -> ${res.status}\n${text.slice(0, 600)}`);
  }
  return data;
}

function b64url(input) {
  return Buffer.from(input)
    .toString("base64")
    .replace(/=+$/, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function signJwt(payload, secret) {
  const head = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = b64url(JSON.stringify(payload));
  const sig = b64url(
    crypto.createHmac("sha256", secret).update(`${head}.${body}`).digest()
  );
  return `${head}.${body}.${sig}`;
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function login() {
  const props = await api("GET", "/api/session/properties");
  if (props["setup-token"]) {
    try {
      await api("POST", "/api/setup", {
        token: props["setup-token"],
        user: {
          first_name: "Equipo",
          last_name: "Cardio Insights",
          email: "poc@cardioinsights.local",
          password: "CardioPoc.2026",
          site_name: "Cardio Insights",
        },
        prefs: {
          site_name: "Cardio Insights",
          site_locale: "es",
          allow_tracking: false,
        },
      });
      console.log("   instancia configurada");
    } catch {
      console.log("   la instancia ya tenia usuario");
    }
  }
  const session = await api("POST", "/api/session", {
    username: "poc@cardioinsights.local",
    password: "CardioPoc.2026",
  });
  if (!cookie && session && session.id) cookie = `metabase.SESSION=${session.id}`;
  if (!cookie) throw new Error("no se obtuvo cookie de sesion");
}

async function cleanPrevious() {
  const cards = await api("GET", "/api/card");
  for (const c of cards || []) {
    if (!c.archived) {
      await api("PUT", `/api/card/${c.id}`, { archived: true }).catch(() => {});
    }
  }
  const dashes = await api("GET", "/api/dashboard");
  for (const d of dashes || []) {
    if (!d.archived) {
      await api("PUT", `/api/dashboard/${d.id}`, { archived: true }).catch(() => {});
    }
  }
  console.log(`   archivados: ${(cards || []).length} preguntas, ${(dashes || []).length} tableros`);
}

async function clickByText(page, texts) {
  return page.evaluate((labels) => {
    const nodes = Array.from(
      document.querySelectorAll('button, [role="button"], a, [data-testid]')
    );
    for (const label of labels) {
      const hit = nodes.find((n) => {
        const t = (n.innerText || n.textContent || "").trim().toLowerCase();
        return t && t.length < 40 && t.includes(label.toLowerCase());
      });
      if (hit) {
        hit.click();
        return label;
      }
    }
    return null;
  }, texts);
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });

  console.log("1. sesion");
  await login();

  console.log("2. limpieza de objetos previos");
  await cleanPrevious();

  console.log("3. conexion a MySQL");
  const dbs = await api("GET", "/api/database");
  const list = Array.isArray(dbs) ? dbs : dbs.data || [];
  let db = list.find((d) => d.name === DB.name);
  if (!db) {
    db = await api("POST", "/api/database", {
      name: DB.name,
      engine: "mysql",
      details: {
        host: DB.host,
        port: DB.port,
        dbname: DB.dbname,
        user: DB.user,
        password: DB.password,
        ssl: false,
        "tunnel-enabled": false,
        "advanced-options": false,
      },
      is_full_sync: true,
    });
    await wait(12000);
  }
  console.log("   base id =", db.id);

  const datasetQuery = {
    database: db.id,
    type: "native",
    native: { query: SQL, "template-tags": {} },
  };

  console.log("4. preguntas guardadas");
  const cardBar = await api("POST", "/api/card", {
    name: "Actos realizados por año y financiador",
    description: "Consulta de prueba utilizada en la POC de integración con Metabase.",
    dataset_query: datasetQuery,
    display: "bar",
    visualization_settings: {
      "graph.dimensions": ["anio", "financiador"],
      "graph.metrics": ["actos"],
      "stackable.stack_type": "stacked",
      "graph.x_axis.title_text": "Año",
      "graph.y_axis.title_text": "Cantidad de actos",
    },
    collection_id: null,
  });
  const cardTable = await api("POST", "/api/card", {
    name: "Detalle de actos por año y financiador",
    description: "Resultado tabular de la misma consulta.",
    dataset_query: datasetQuery,
    display: "table",
    visualization_settings: {},
    collection_id: null,
  });
  console.log(`   grafico id = ${cardBar.id}, tabla id = ${cardTable.id}`);

  console.log("5. tablero de ejemplo");
  const dash = await api("POST", "/api/dashboard", {
    name: "POC – Actos realizados",
    description: "Tablero de ejemplo creado durante la POC de Metabase.",
  });
  await api("PUT", `/api/dashboard/${dash.id}`, {
    dashcards: [
      {
        id: -1,
        card_id: cardBar.id,
        row: 0,
        col: 0,
        size_x: 14,
        size_y: 9,
        parameter_mappings: [],
        visualization_settings: {},
      },
      {
        id: -2,
        card_id: cardTable.id,
        row: 0,
        col: 14,
        size_x: 10,
        size_y: 9,
        parameter_mappings: [],
        visualization_settings: {},
      },
    ],
  });
  console.log("   tablero id =", dash.id);

  console.log("6. embebido estatico");
  for (const [key, value] of [
    ["enable-embedding", true],
    ["enable-embedding-static", true],
    ["embedding-secret-key", EMBED_SECRET],
  ]) {
    await api("PUT", `/api/setting/${key}`, { value }).catch(() =>
      console.log(`   ${key}: no disponible en esta version`)
    );
  }
  await api("PUT", `/api/dashboard/${dash.id}`, { enable_embedding: true });

  const token = signJwt(
    {
      resource: { dashboard: dash.id },
      params: {},
      exp: Math.floor(Date.now() / 1000) + 60 * 30,
    },
    EMBED_SECRET
  );
  const embedUrl = `${MB}/embed/dashboard/${token}#bordered=false&titled=false&background=false`;

  const wrapperFile = path.join(__dirname, "embed-cardio-insights.html");
  fs.writeFileSync(wrapperFile, wrapperHtml(embedUrl), "utf8");
  const server = http
    .createServer((req, res) => {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(fs.readFileSync(wrapperFile));
    })
    .listen(WRAP_PORT);

  console.log("7. capturas");
  const browser = await puppeteer.launch({
    headless: "shell",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  await browser.setCookie({
    name: "metabase.SESSION",
    value: cookie.split("=")[1],
    domain: "localhost",
    path: "/",
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

  const shot = async (name) => {
    await page.screenshot({ path: path.join(OUT, name) });
    console.log("   ->", name);
  };

  // 7.1 consulta SQL ejecutada, con el editor y el resultado a la vista
  await page.goto(`${MB}/question/${cardTable.id}`, { waitUntil: "networkidle2" });
  await wait(9000);
  const opened = await clickByText(page, ["abrir editor", "open editor"]);
  console.log("   editor:", opened || "no encontrado");
  await wait(6000);
  await shot("poc-01-consulta-sql.png");

  // 7.2 misma consulta como visualizacion guardada
  await page.goto(`${MB}/question/${cardBar.id}`, { waitUntil: "networkidle2" });
  await wait(9000);
  await shot("poc-02-visualizacion.png");

  // 7.3 tablero dentro de Metabase
  await page.goto(`${MB}/dashboard/${dash.id}`, { waitUntil: "networkidle2" });
  await wait(10000);
  await shot("poc-03-dashboard-metabase.png");

  // 7.4 tablero embebido en una pagina de la aplicacion
  await page.goto(`http://localhost:${WRAP_PORT}/`, { waitUntil: "networkidle2" });
  for (let i = 0; i < 30; i++) {
    const ready = await page.evaluate(() => {
      const f = document.querySelector("iframe");
      try {
        return !!(
          f &&
          f.contentDocument &&
          f.contentDocument.body &&
          f.contentDocument.body.innerText.includes("financiador")
        );
      } catch {
        return false;
      }
    });
    if (ready) break;
    await wait(2000);
  }
  await wait(4000);
  await shot("poc-04-embebido-en-la-app.png");

  await browser.close();
  server.close();

  fs.writeFileSync(
    path.join(__dirname, "datos-poc.json"),
    JSON.stringify(
      {
        metabase_version: (await api("GET", "/api/session/properties")).version,
        card_bar_id: cardBar.id,
        card_table_id: cardTable.id,
        dashboard_id: dash.id,
        embed_url: embedUrl,
        sql: SQL,
      },
      null,
      2
    ),
    "utf8"
  );
  console.log("listo");
}

function wrapperHtml(embedUrl) {
  return `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Cardio Insights — KPIs</title>
<style>
  :root { --deep:#0d3b66; --primary:#2e8bce; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:"Segoe UI",system-ui,sans-serif; background:#f6f8fa; color:#111827; }
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
  iframe { width:100%; height:560px; border:0; display:block; }
</style>
</head>
<body>
<header>
  <div class="brand"><div class="logo">CI</div> Cardio Insights</div>
  <div class="user"><span>Equipo</span><div class="avatar">EC</div></div>
</header>
<main>
  <div class="card" id="card">
    <iframe src="${embedUrl}" title="Tablero embebido"></iframe>
  </div>
</main>
</body>
</html>`;
}

main().catch((e) => {
  console.error("ERROR:", e.message || e);
  process.exit(1);
});
