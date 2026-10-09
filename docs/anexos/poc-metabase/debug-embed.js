const puppeteer = require("puppeteer");
const d = require("./datos-poc.json");

(async () => {
  const browser = await puppeteer.launch({
    headless: "shell",
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1200, height: 800 });
  page.on("console", (m) => console.log("[console]", m.type(), m.text().slice(0, 200)));
  page.on("pageerror", (e) => console.log("[pageerror]", String(e).slice(0, 300)));
  page.on("requestfailed", (r) =>
    console.log("[failed]", r.url().slice(0, 120), r.failure()?.errorText)
  );
  await page.goto(d.embed_url, { waitUntil: "networkidle2" });
  await new Promise((r) => setTimeout(r, 12000));
  const text = await page.evaluate(() => document.body.innerText.slice(0, 500));
  console.log("--- texto de la pagina ---");
  console.log(text || "(vacio)");
  await page.screenshot({ path: "debug-embed.png" });
  await browser.close();
})();
