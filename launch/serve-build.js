#!/usr/bin/env node
/**
 * Loopback-only static server for the production React build.
 * Usage: node serve-build.js <build-dir> <port>
 */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const BUILD_ROOT = path.resolve(process.argv[2] || ".");
const PORT = Number.parseInt(process.argv[3] || "3000", 10);

if (!Number.isInteger(PORT) || PORT < 1 || PORT > 65535) {
  throw new Error(`Invalid port: ${process.argv[3]}`);
}

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".eot": "application/vnd.ms-fontobject",
  ".map": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
};

const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "SAMEORIGIN",
  "Cross-Origin-Resource-Policy": "same-origin",
};

function resolveRequestPath(rawUrl) {
  let pathname;
  try {
    pathname = decodeURIComponent(String(rawUrl || "/").split("?")[0]);
  } catch {
    return null;
  }
  if (pathname === "/") pathname = "/index.html";
  const relativePath = pathname.replace(/^[/\\]+/, "");
  const resolved = path.resolve(BUILD_ROOT, relativePath);
  const relative = path.relative(BUILD_ROOT, resolved);
  if (relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    return null;
  }
  return resolved;
}

function send(res, status, headers, body) {
  res.writeHead(status, { ...SECURITY_HEADERS, ...headers });
  res.end(body);
}

const server = http.createServer((req, res) => {
  const filePath = resolveRequestPath(req.url);
  if (!filePath) {
    send(res, 403, { "Content-Type": "text/plain; charset=utf-8" }, "Forbidden");
    return;
  }

  fs.stat(filePath, (statError, stat) => {
    const target = !statError && stat.isFile() ? filePath : path.join(BUILD_ROOT, "index.html");
    fs.readFile(target, (readError, data) => {
      if (readError) {
        send(res, 404, { "Content-Type": "text/plain; charset=utf-8" }, "Not found");
        return;
      }
      const ext = path.extname(target).toLowerCase();
      const cacheControl = target === filePath && /\\.(?:js|css|woff2?|ttf)$/.test(ext)
        ? "public, max-age=31536000, immutable"
        : "no-cache";
      send(res, 200, {
        "Content-Type": MIME[ext] || "application/octet-stream",
        "Cache-Control": cacheControl,
      }, data);
    });
  });
});

server.requestTimeout = 30_000;
server.headersTimeout = 10_000;
server.keepAliveTimeout = 5_000;
server.maxHeadersCount = 100;

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[phoenix-frontend] Serving ${BUILD_ROOT} on http://127.0.0.1:${PORT}`);
});

server.on("error", (error) => {
  if (error.code === "EADDRINUSE") {
    console.error(`[phoenix-frontend] Port ${PORT} is already in use.`);
  } else {
    console.error(`[phoenix-frontend] Server error: ${error.message}`);
  }
  process.exitCode = 1;
});

function shutdown() {
  server.close(() => process.exit(0));
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
