const express = require("express");
const multer  = require("multer");
const http    = require("http");
const router  = express.Router();
const upload  = multer({ storage: multer.memoryStorage() });

const STT_HOST = process.env.STT_HOST || "localhost";
const STT_PORT = process.env.STT_PORT || 8002;

// Proxy audio file sang Python Whisper service
router.post("/", upload.single("audio"), (req, res) => {
  if (!req.file) return res.status(400).json({ error: "No audio file" });

  const boundary = `----FormBoundary${Date.now()}`;
  const body = Buffer.concat([
    Buffer.from(
      `--${boundary}\r\nContent-Disposition: form-data; name="audio"; filename="audio.wav"\r\nContent-Type: audio/wav\r\n\r\n`
    ),
    req.file.buffer,
    Buffer.from(`\r\n--${boundary}--\r\n`),
  ]);

  const options = {
    hostname: STT_HOST, port: STT_PORT, path: "/stt", method: "POST",
    headers: {
      "Content-Type": `multipart/form-data; boundary=${boundary}`,
      "Content-Length": body.length,
    },
  };

  const proxyReq = http.request(options, (proxyRes) => {
    let data = "";
    proxyRes.on("data", (chunk) => (data += chunk));
    proxyRes.on("end", () => {
      try { res.json(JSON.parse(data)); }
      catch { res.status(500).json({ error: "STT parse error" }); }
    });
  });

  proxyReq.on("error", () => res.status(503).json({ error: "STT service unavailable" }));
  proxyReq.write(body);
  proxyReq.end();
});

module.exports = router;
