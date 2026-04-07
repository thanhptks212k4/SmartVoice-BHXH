import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import MascotCard from "./MascotCard";

const BASE_URL   = import.meta.env.VITE_API_URL  || "http://localhost:3000";
const WS_URL     = import.meta.env.VITE_WS_URL   || "ws://localhost:3000";
const STT_WS_URL = import.meta.env.VITE_STT_WS_URL || "ws://localhost:8003";
const VOICE      = "nuhanoi";

// Browser gửi chunk 20ms @ 16kHz = 320 samples
const CHUNK_SAMPLES = 320;

export default function VoicePage() {
  const navigate = useNavigate();
  const [state, setState]       = useState("idle");
  const [botText, setBotText]   = useState("");
  const [error, setError]       = useState("");
  const [engine, setEngine]     = useState(
    localStorage.getItem("stt_engine") || "google"
  );

  const wsRef      = useRef(null);   // Node WS
  const sttWsRef   = useRef(null);   // STT WS
  const audioCtxRef = useRef(null);
  const processorRef = useRef(null);
  const streamRef  = useRef(null);
  const isPlayingRef = useRef(false);
  const stateRef   = useRef("idle");

  const setStateBoth = (s) => { stateRef.current = s; setState(s); };

  // ── Kết nối Node WebSocket ──
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { navigate("/"); return; }

    const ws = new WebSocket(`${WS_URL}?token=${token}`);
    wsRef.current = ws;
    ws.onopen  = () => console.log("[WS] connected");
    ws.onclose = () => setError("Mất kết nối server");
    ws.onerror = () => setError("Lỗi kết nối server");
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "AI_VOICE_REPLY") {
        if (data.text) setBotText(data.text);
        if (data.audioUrl) playAudio(data.audioUrl);
      }
    };
    return () => ws.close();
  }, [navigate]);

  // ── Kết nối STT WebSocket ──
  const connectSTT = useCallback(() => {
    if (sttWsRef.current?.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket(STT_WS_URL);
    ws.binaryType = "arraybuffer";
    sttWsRef.current = ws;

    ws.onopen = () => console.log("[STT-WS] connected");
    ws.onclose = () => console.log("[STT-WS] closed");
    ws.onerror = (e) => console.error("[STT-WS] error", e);

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.event === "speech_start") {
        setStateBoth("listening");
      } else if (data.event === "speech_end") {
        setStateBoth("idle");
      } else if (data.text) {
        // Gửi text lên Node server qua WS
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            text: data.text,
            language: "VI",
            voice: VOICE,
            timestamp: Math.floor(Date.now() / 1000),
            duration: 0,
          }));
        }
      }
    };
  }, []);

  // ── Phát TTS audio ──
  const playAudio = useCallback(async (url) => {
    isPlayingRef.current = true;
    setStateBoth("speaking");
    // Reset STT để tránh thu âm lại lúc phát
    sttWsRef.current?.send(JSON.stringify({ cmd: "reset" }));
    try {
      const res     = await fetch(url);
      const buf     = await res.arrayBuffer();
      const ctx     = new AudioContext();
      const decoded = await ctx.decodeAudioData(buf);
      const src     = ctx.createBufferSource();
      src.buffer    = decoded;
      src.connect(ctx.destination);
      src.start();
      src.onended = () => {
        isPlayingRef.current = false;
        setStateBoth("idle");
        ctx.close();
      };
    } catch {
      isPlayingRef.current = false;
      setStateBoth("idle");
    }
  }, []);

  // ── Mic capture → stream PCM lên STT WS ──
  const startMic = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const ctx  = new AudioContext({ sampleRate: 16000 });
      audioCtxRef.current = ctx;

      const src  = ctx.createMediaStreamSource(stream);
      const proc = ctx.createScriptProcessor(CHUNK_SAMPLES, 1, 1);
      processorRef.current = proc;

      proc.onaudioprocess = (ev) => {
        if (isPlayingRef.current) return;
        const stt = sttWsRef.current;
        if (!stt || stt.readyState !== WebSocket.OPEN) return;

        const f32 = ev.inputBuffer.getChannelData(0);
        // Gửi Float32Array binary
        stt.send(f32.buffer.slice(f32.byteOffset, f32.byteOffset + f32.byteLength));
      };

      src.connect(proc);
      proc.connect(ctx.destination);
    } catch {
      setError("Không thể truy cập microphone");
    }
  }, []);

  useEffect(() => {
    connectSTT();
    startMic();
    return () => {
      processorRef.current?.disconnect();
      audioCtxRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      sttWsRef.current?.close();
    };
  }, [connectSTT, startMic]);

  // ── Đổi engine STT ──
  const handleEngineChange = (e) => {
    const val = e.target.value;
    setEngine(val);
    localStorage.setItem("stt_engine", val);
    // Gửi lệnh đổi engine lên server (cần restart server để có hiệu lực)
    alert(`Đổi sang ${val.toUpperCase()}. Restart STT server với STT_ENGINE=${val}`);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/");
  };

  return (
    <div style={S.bg}>
      {/* Header */}
      <div style={S.header}>
        <select style={S.select} value={engine} onChange={handleEngineChange}>
          <option value="google">Google STT</option>
          <option value="whisper">Whisper</option>
        </select>
        <button style={S.logout} onClick={handleLogout}>Đăng xuất</button>
      </div>

      {error && <p style={S.error}>{error}</p>}

      <MascotCard state={state} />

      {botText && (
        <div style={S.bubble}>
          <p style={S.bubbleText}>{botText}</p>
        </div>
      )}
    </div>
  );
}

const S = {
  bg: {
    minHeight: "100vh", display: "flex", flexDirection: "column",
    justifyContent: "center", alignItems: "center",
    background: "#0f0f1a", position: "relative",
  },
  header: {
    position: "absolute", top: 20, right: 20,
    display: "flex", gap: 10, alignItems: "center",
  },
  select: {
    background: "#1a1a2e", border: "1px solid #3a3a5a",
    color: "#aaa", borderRadius: 8, padding: "6px 10px",
    fontSize: 13, cursor: "pointer", outline: "none",
  },
  logout: {
    background: "transparent", border: "1px solid #3a3a5a",
    color: "#888", borderRadius: 8, padding: "6px 14px",
    cursor: "pointer", fontSize: 13,
  },
  error:  { color: "#ff5252", fontSize: 13 },
  bubble: {
    marginTop: 16, background: "#1a1a2e", border: "1px solid #2a2a4a",
    borderRadius: 14, padding: "12px 20px", maxWidth: 360,
  },
  bubbleText: { color: "#ddd", margin: 0, fontSize: 14, lineHeight: 1.6 },
};
