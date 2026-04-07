import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import MascotCard from "./MascotCard";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:3000";
const WS_URL   = import.meta.env.VITE_WS_URL  || "ws://localhost:3000";
const VOICE    = "nuhanoi";

// VAD config
const SILENCE_THRESHOLD = 0.01;  // RMS dưới mức này = im lặng
const SILENCE_DURATION  = 1800;  // ms im lặng để gửi
const MIN_SPEECH_MS     = 400;   // bỏ qua chunk quá ngắn

export default function VoicePage() {
  const navigate  = useNavigate();
  const [state, setState]     = useState("idle");    // idle | listening | speaking
  const [botText, setBotText] = useState("");
  const [error, setError]     = useState("");

  const wsRef          = useRef(null);
  const audioCtxRef    = useRef(null);
  const processorRef   = useRef(null);
  const streamRef      = useRef(null);
  const pcmBufferRef   = useRef([]);
  const silenceTimerRef = useRef(null);
  const speechStartRef  = useRef(null);
  const isPlayingRef    = useRef(false);
  const stateRef        = useRef("idle");

  const setStateBoth = (s) => { stateRef.current = s; setState(s); };

  // ── WebSocket ──
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { navigate("/"); return; }

    const ws = new WebSocket(`${WS_URL}?token=${token}`);
    wsRef.current = ws;

    ws.onopen  = () => console.log("[WS] connected");
    ws.onclose = () => console.log("[WS] closed");
    ws.onerror = () => setError("Mất kết nối server");

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "AI_VOICE_REPLY") {
        if (data.text) setBotText(data.text);
        if (data.audioUrl) playAudio(data.audioUrl);
      }
    };

    return () => ws.close();
  }, [navigate]);

  // ── Play TTS audio ──
  const playAudio = useCallback(async (url) => {
    isPlayingRef.current = true;
    setStateBoth("speaking");
    try {
      const res = await fetch(url);
      const buf = await res.arrayBuffer();
      const ctx = new AudioContext();
      const decoded = await ctx.decodeAudioData(buf);
      const src = ctx.createBufferSource();
      src.buffer = decoded;
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

  // ── Mic + VAD ──
  const startMic = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const ctx = new AudioContext({ sampleRate: 16000 });
      audioCtxRef.current = ctx;

      const src  = ctx.createMediaStreamSource(stream);
      const proc = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = proc;

      proc.onaudioprocess = (ev) => {
        if (isPlayingRef.current) return;

        const f32 = ev.inputBuffer.getChannelData(0);
        const rms = Math.sqrt(f32.reduce((s, v) => s + v * v, 0) / f32.length);

        if (rms > SILENCE_THRESHOLD) {
          // có tiếng nói
          if (!speechStartRef.current) speechStartRef.current = Date.now();
          setStateBoth("listening");
          pcmBufferRef.current.push(new Float32Array(f32));

          // reset silence timer
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = setTimeout(() => {
            flushBuffer();
          }, SILENCE_DURATION);
        }
      };

      src.connect(proc);
      proc.connect(ctx.destination);
    } catch {
      setError("Không thể truy cập microphone");
    }
  }, []);

  // ── Gửi audio lên Whisper API (hoặc Google STT nếu chưa có) ──
  const flushBuffer = useCallback(async () => {
    const chunks = pcmBufferRef.current.splice(0);
    if (!chunks.length) return;

    const duration = Date.now() - (speechStartRef.current || Date.now());
    speechStartRef.current = null;
    if (duration < MIN_SPEECH_MS) return;

    setStateBoth("idle");

    // Ghép PCM -> WAV
    const totalLen = chunks.reduce((s, c) => s + c.length, 0);
    const pcm = new Float32Array(totalLen);
    let offset = 0;
    for (const c of chunks) { pcm.set(c, offset); offset += c.length; }

    const wav = encodeWav(pcm, 16000);
    const blob = new Blob([wav], { type: "audio/wav" });

    // Gửi lên STT endpoint
    const sttUrl = import.meta.env.VITE_STT_URL || `${BASE_URL}/stt`;
    try {
      const form = new FormData();
      form.append("audio", blob, "audio.wav");
      const res  = await fetch(sttUrl, { method: "POST", body: form });
      const data = await res.json();
      const text = data.text?.trim();
      if (text && wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          text,
          language: "VI",
          voice: VOICE,
          timestamp: Math.floor(Date.now() / 1000),
          duration: Math.round(duration / 1000),
        }));
      }
    } catch (e) {
      console.error("[STT]", e);
    }
  }, []);

  useEffect(() => {
    startMic();
    return () => {
      processorRef.current?.disconnect();
      audioCtxRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      clearTimeout(silenceTimerRef.current);
    };
  }, [startMic]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/");
  };

  return (
    <div style={S.bg}>
      <button style={S.logout} onClick={handleLogout}>Đăng xuất</button>
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

// ── Encode Float32 PCM -> WAV bytes ──
function encodeWav(samples, sampleRate) {
  const buf    = new ArrayBuffer(44 + samples.length * 2);
  const view   = new DataView(buf);
  const write  = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  const i16len = samples.length * 2;

  write(0, "RIFF"); view.setUint32(4, 36 + i16len, true);
  write(8, "WAVE"); write(12, "fmt ");
  view.setUint32(16, 16, true);  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);   view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);  write(36, "data");
  view.setUint32(40, i16len, true);

  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    view.setInt16(off, Math.max(-32768, Math.min(32767, samples[i] * 32768)), true);
  }
  return buf;
}

const S = {
  bg: {
    minHeight: "100vh", display: "flex", flexDirection: "column",
    justifyContent: "center", alignItems: "center",
    background: "#0f0f1a", position: "relative",
  },
  logout: {
    position: "absolute", top: 20, right: 20,
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
