import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import MascotCard from "./MascotCard";

const BASE_URL   = import.meta.env.VITE_API_URL  || "http://localhost:3000";
const WS_URL     = import.meta.env.VITE_WS_URL   || "ws://localhost:3000";
const STT_WS_URL = import.meta.env.VITE_STT_WS_URL || "ws://localhost:8003";
const VOICE      = import.meta.env.VITE_VOICE || "nuhanoi";
const STT_ENGINE = import.meta.env.VITE_STT_ENGINE || "google";

// Browser gửi chunk 20ms @ 16kHz = 320 samples
const CHUNK_SAMPLES = 512;

export default function VoicePage() {
  const navigate = useNavigate();
  const [state, setState]       = useState("idle");
  const [botText, setBotText]   = useState("");
  const [error, setError]       = useState("");

  const wsRef      = useRef(null);   // Node WS
  const sttWsRef   = useRef(null);   // STT WS
  const audioCtxRef = useRef(null);
  const processorRef = useRef(null);
  const streamRef  = useRef(null);
  const isPlayingRef = useRef(false);
  const stateRef   = useRef("idle");

  const [micReady, setMicReady] = useState(false);

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
    return new Promise((resolve) => {
      if (sttWsRef.current?.readyState === WebSocket.OPEN) { resolve(); return; }
      const ws = new WebSocket(STT_WS_URL);
      ws.binaryType = "arraybuffer";
      sttWsRef.current = ws;

      ws.onopen = () => { console.log("[STT-WS] connected"); resolve(); };
      ws.onclose = () => console.log("[STT-WS] closed");
      ws.onerror = (e) => { console.error("[STT-WS] error", e); resolve(); };

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.event === "speech_start") {
          setStateBoth("listening");
        } else if (data.event === "speech_end") {
          setStateBoth("idle");
        } else if (data.text) {
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
    });
  }, []);

  // ── Phát TTS audio theo streaming ──
  const playAudio = useCallback(async (url) => {
    isPlayingRef.current = true;
    setStateBoth("speaking");
    sttWsRef.current?.send(JSON.stringify({ cmd: "reset" }));

    try {
      const res = await fetch(url);
      if (!res.ok || !res.body) throw new Error("Stream không khả dụng");

      const ctx = new AudioContext({ sampleRate: 24000 });
      audioCtxRef.current = ctx;

      const reader = res.body.getReader();
      let headerSkipped = false;
      let nextStartTime = ctx.currentTime + 0.05; // buffer nhỏ 50ms
      let receivedBytes = new Uint8Array(0);
      const HEADER_SIZE = 44; // WAV header
      const PCM_CHUNK   = 8192; // bytes mỗi lần decode (~170ms @ 24kHz 16bit mono)

      const appendBytes = (existing, incoming) => {
        const merged = new Uint8Array(existing.length + incoming.length);
        merged.set(existing);
        merged.set(incoming, existing.length);
        return merged;
      };

      const scheduleChunk = (pcmBytes) => {
        // pcmBytes: Int16 PCM raw
        const samples = pcmBytes.length / 2;
        const audioBuffer = ctx.createBuffer(1, samples, 24000);
        const channelData = audioBuffer.getChannelData(0);
        const view = new DataView(pcmBytes.buffer);
        for (let i = 0; i < samples; i++) {
          channelData[i] = view.getInt16(i * 2, true) / 32768;
        }
        const src = ctx.createBufferSource();
        src.buffer = audioBuffer;
        src.connect(ctx.destination);
        const startAt = Math.max(nextStartTime, ctx.currentTime + 0.01);
        src.start(startAt);
        nextStartTime = startAt + audioBuffer.duration;
        return audioBuffer.duration;
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        receivedBytes = appendBytes(receivedBytes, value);

        // Bỏ qua WAV header 44 bytes đầu
        if (!headerSkipped) {
          if (receivedBytes.length < HEADER_SIZE) continue;
          receivedBytes = receivedBytes.slice(HEADER_SIZE);
          headerSkipped = true;
        }

        // Phát từng chunk PCM khi đủ dữ liệu
        while (receivedBytes.length >= PCM_CHUNK) {
          const chunk = receivedBytes.slice(0, PCM_CHUNK);
          receivedBytes = receivedBytes.slice(PCM_CHUNK);
          scheduleChunk(chunk);
        }
      }

      // Phát phần còn lại
      if (receivedBytes.length > 1) {
        // Đảm bảo số bytes chẵn (Int16)
        const aligned = receivedBytes.slice(0, receivedBytes.length - (receivedBytes.length % 2));
        if (aligned.length > 0) scheduleChunk(aligned);
      }

      // Đợi audio phát xong rồi mới reset state
      const remaining = nextStartTime - ctx.currentTime;
      setTimeout(() => {
        isPlayingRef.current = false;
        setStateBoth("idle");
        ctx.close();
      }, Math.max(remaining * 1000 + 200, 0));

    } catch (err) {
      console.error("[Audio] Lỗi phát:", err);
      isPlayingRef.current = false;
      setStateBoth("idle");
    }
  }, []);

  // ── Mic capture → stream PCM lên STT WS ──
  const startMic = useCallback(async () => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setError("Trình duyệt không hỗ trợ microphone. Dùng Chrome/Edge trên localhost.");
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: false, sampleRate: 16000 }
      });
      streamRef.current = stream;
      setMicReady(true);
      setError("");

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
    } catch (err) {
      console.error("[Mic] Error:", err.name, err.message);
      if (err.name === "NotAllowedError") {
        setError("Mic bị từ chối — click icon mic trên address bar để cho phép");
      } else if (err.name === "NotFoundError") {
        setError("Không tìm thấy microphone");
      } else {
        setError(`Lỗi mic: ${err.message}`);
      }
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      await connectSTT();
      await startMic();
    };
    init();
    return () => {
      processorRef.current?.disconnect();
      audioCtxRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      sttWsRef.current?.close();
    };
  }, [connectSTT, startMic]);
  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/");
  };

  return (
    <div style={S.bg}>
      {/* Header */}
      <div style={S.header}>
        <button style={S.logout} onClick={handleLogout}>Đăng xuất</button>
      </div>

      {/* Title */}
      <div style={S.titleContainer}>
        <h1 style={S.mainTitle}>TRỢ LÝ ẢO TIẾNG VIỆT</h1>
        <p style={S.subtitle}>TƯ VẤN BẢO HIỂM XÃ HỘI</p>
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
  titleContainer: {
    position: "absolute", top: 20, left: 20,
    display: "flex", flexDirection: "column", alignItems: "flex-start",
  },
  mainTitle: {
    color: "#7c4dff", margin: 0, fontSize: 20, fontWeight: 700,
    letterSpacing: "0.5px",
  },
  subtitle: {
    color: "#aaa", margin: "4px 0 0 0", fontSize: 13, fontWeight: 500,
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
  micBtn: {
    marginBottom: 16, padding: "12px 28px", borderRadius: 12,
    background: "#7c4dff", color: "#fff", border: "none",
    fontSize: 15, fontWeight: 600, cursor: "pointer",
  },
};
