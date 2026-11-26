const assert = require("node:assert/strict");
const { after, before, test } = require("node:test");
const fs = require("node:fs/promises");
const http = require("node:http");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

const serverScript = path.join(__dirname, "serve-build.js");
let root;
let port;
let child;

async function freePort() {
  const probe = net.createServer();
  await new Promise((resolve, reject) => {
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", resolve);
  });
  const address = probe.address();
  const chosen = address.port;
  await new Promise((resolve) => probe.close(resolve));
  return chosen;
}

async function rawGet(requestPath) {
  return new Promise((resolve, reject) => {
    const request = http.request({ host: "127.0.0.1", port, path: requestPath, method: "GET" }, (response) => {
      const chunks = [];
      response.on("data", (chunk) => chunks.push(chunk));
      response.on("end", () => resolve({
        status: response.statusCode,
        headers: response.headers,
        body: Buffer.concat(chunks).toString("utf8"),
      }));
    });
    request.once("error", reject);
    request.end();
  });
}

before(async () => {
  root = await fs.mkdtemp(path.join(os.tmpdir(), "phoenix-static-"));
  await fs.writeFile(path.join(root, "index.html"), "<!doctype html><html><head></head><body><main>Phoenix test shell</main></body></html>");
  await fs.writeFile(path.join(root, "app.js"), "globalThis.phoenixReady = true;");
  port = await freePort();
  child = spawn(process.execPath, [serverScript, root, String(port)], {
    stdio: "ignore",
    env: { ...process.env, PHOENIX_BACKEND_URL: "http://127.0.0.1:8001" },
  });
  child.once("error", (error) => { throw error; });
  let ready = false;
  for (let attempt = 0; attempt < 60 && !ready; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/`);
      ready = response.status === 200;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  assert.equal(ready, true, "static server did not become ready");
});

after(async () => {
  if (child && !child.killed) child.kill();
  if (root) await fs.rm(root, { recursive: true, force: true });
});

test("serves the production index and SPA fallback", async () => {
  const rootResponse = await rawGet("/");
  assert.equal(rootResponse.status, 200);
  assert.match(rootResponse.body, /Phoenix test shell/);
  assert.ok(rootResponse.body.includes("window.__PHOENIX_CONFIG__"));
  assert.ok(rootResponse.body.includes('"backendUrl":"http://127.0.0.1:8001"'));
  const routeResponse = await rawGet("/projects/example/settings");
  assert.equal(routeResponse.status, 200);
  assert.match(routeResponse.body, /Phoenix test shell/);
});

test("serves static assets with a content type", async () => {
  const response = await rawGet("/app.js");
  assert.equal(response.status, 200);
  assert.match(response.headers["content-type"], /javascript/);
  assert.match(response.headers["cache-control"], /immutable/);
});

test("rejects encoded path traversal", async () => {
  const response = await rawGet("/%2e%2e/secret.txt");
  assert.equal(response.status, 403);
});

test("sets baseline browser security headers", async () => {
  const response = await rawGet("/");
  assert.equal(response.headers["x-content-type-options"], "nosniff");
  assert.equal(response.headers["x-frame-options"], "SAMEORIGIN");
});
