const fs = require("fs");
const http = require("http");
const path = require("path");
const puppeteer = require("puppeteer");

const PORT = 5602;
const file = path.join(__dirname, "embed-cardio-insights.html");
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const server = http
    .createServer((req, res) => {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(fs.readFileSync(file));
    })
    .listen(PORT);

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-features=IsolateOrigins,site-per-process"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 860 });
  await page.goto(`http://localhost:${PORT}/`, { waitUntil: "networkidle2" });
  await wait(20000);

  const frame = page.frames().find((f) => f.url().includes("/embed/dashboard/"));
  if (!frame) {
    console.log("no se encontro el frame");
    process.exit(0);
  }
  const info = await frame.evaluate(() => {
    const out = {
      win: [window.innerWidth, window.innerHeight],
      scroll: [document.body.scrollWidth, document.body.scrollHeight],
      cards: [],
    };
    const nodes = document.querySelectorAll(
      '[data-testid="dashcard"], .DashCard, [class*="DashCard"]'
    );
    out.count = nodes.length;
    nodes.forEach((n, i) => {
      const r = n.getBoundingClientRect();
      const cs = getComputedStyle(n);
      out.cards.push({
        i,
        rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
        vis: cs.visibility,
        op: cs.opacity,
        display: cs.display,
        text: (n.innerText || "").slice(0, 40).replace(/\n/g, " "),
      });
    });
    const grid = document.querySelector('[class*="DashboardGrid"], .DashboardGrid');
    if (grid) {
      const r = grid.getBoundingClientRect();
      out.grid = [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)];
    }
    return out;
  });
  console.log(JSON.stringify(info, null, 2));

  await frame.evaluate(() => {
    const n = document.querySelector('[data-testid="dashcard"]');
    if (n) n.scrollIntoView();
  });
  await wait(3000);
  await page.screenshot({ path: "diag-frame.png" });
  await browser.close();
  server.close();
})();
