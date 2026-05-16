import { useEffect, useRef, useCallback } from "react";

/* ─── Badge config ─── */
const BADGE = {
  idle:      { bg: "#f5f5f5", color: "#888",   text: "Chờ..." },
  listening: { bg: "#ede7f6", color: "#5e35b1", text: "Đang lắng nghe..." },
  speaking:  { bg: "#e0f7fa", color: "#00838f", text: "Đang tư vấn..." },
};

function lerp(a, b, t) {
  return a + (b - a) * t;
}

export default function MascotCard({ state = "idle" }) {
  /* ── SVG element refs ── */
  const lidL   = useRef(null);
  const lidR   = useRef(null);
  const irisL  = useRef(null);
  const irisR  = useRef(null);
  const browL  = useRef(null);
  const browR  = useRef(null);
  const mouth  = useRef(null);
  const barsRef = useRef([]);
  const waveRef = useRef(null);
  const glowRef = useRef(null);

  /* ── speaking mouth state (persistent across frames) ── */
  const mh   = useRef(0);    // 0..11
  const mdir = useRef(1);    // +1 or -1

  /* ── blink timer ── */
  useEffect(() => {
    let timer;
    const blink = () => {
      const lL = lidL.current;
      const lR = lidR.current;
      if (!lL || !lR) return;
      lL.setAttribute("ry", "10");
      lR.setAttribute("ry", "10");
      setTimeout(() => {
        if (lL) lL.setAttribute("ry", "0");
        if (lR) lR.setAttribute("ry", "0");
      }, 120);
      timer = setTimeout(blink, 2000 + Math.random() * 2000);
    };
    timer = setTimeout(blink, 1000 + Math.random() * 2000);
    return () => clearTimeout(timer);
  }, []);

  /* ── main animation loop ── */
  useEffect(() => {
    let raf;

    const tick = () => {
      const now = Date.now();

      /* ── iris ── */
      const il = irisL.current;
      const ir = irisR.current;
      if (il && ir) {
        if (state === "listening") {
          il.setAttribute("fill", "#1565C0");
          ir.setAttribute("fill", "#1565C0");
          il.setAttribute("ry", "7");
          ir.setAttribute("ry", "7");
        } else {
          il.setAttribute("fill", "#222");
          ir.setAttribute("fill", "#222");
          il.setAttribute("ry", "6");
          ir.setAttribute("ry", "6");
        }
      }

      /* ── eyebrows ── */
      const bl = browL.current;
      const br = browR.current;
      if (bl && br) {
        if (state === "listening") {
          bl.setAttribute("d", "M33,62 Q42,58 51,62");
          br.setAttribute("d", "M69,62 Q78,58 87,62");
        } else if (state === "speaking") {
          const off = Math.sin(now / 350) * 1.5;
          bl.setAttribute("d", `M33,${65 + off} Q42,${62 + off} 51,${65 + off}`);
          br.setAttribute("d", `M69,${65 + off} Q78,${62 + off} 87,${65 + off}`);
        } else {
          bl.setAttribute("d", "M33,65 Q42,62 51,65");
          br.setAttribute("d", "M69,65 Q78,62 87,65");
        }
      }

      /* ── mouth ── */
      const m = mouth.current;
      if (m) {
        if (state === "speaking") {
          // advance mouth counter
          mh.current += mdir.current;
          if (mh.current >= 11) mdir.current = -1;
          if (mh.current <= 0)  mdir.current = 1;

          if (mh.current > 4) {
            // mouth open
            const cy = lerp(100, 108, (mh.current - 4) / 7);
            m.setAttribute("d", `M49,95 Q60,${cy.toFixed(1)} 71,95`);
            m.setAttribute("fill", "#E53935");
            m.setAttribute("stroke", "#E53935");
          } else {
            // mouth closed
            const cy = lerp(100, 95, (4 - mh.current) / 4);
            m.setAttribute("d", `M49,95 Q60,${cy.toFixed(1)} 71,95`);
            m.setAttribute("fill", "none");
            m.setAttribute("stroke", "#E57373");
          }
        } else if (state === "listening") {
          m.setAttribute("d", "M50,93 Q60,92 70,93");
          m.setAttribute("fill", "none");
          m.setAttribute("stroke", "#E57373");
          mh.current = 0;
          mdir.current = 1;
        } else {
          m.setAttribute("d", "M48,95 Q60,100 72,95");
          m.setAttribute("fill", "none");
          m.setAttribute("stroke", "#E57373");
          mh.current = 0;
          mdir.current = 1;
        }
      }

      /* ── wave bars ── */
      if (state !== "idle") {
        barsRef.current.forEach((bar, i) => {
          if (!bar) return;
          const h = 7 + Math.abs(Math.sin(now / 170 + i * 0.7)) * 26;
          bar.style.height = `${h}px`;
          bar.style.backgroundColor = state === "listening" ? "#7c4dff" : "#26c6da";
        });
      }

      /* ── glow ring ── */
      if (glowRef.current) {
        glowRef.current.style.display = state === "listening" ? "block" : "none";
      }

      /* ── wave container ── */
      if (waveRef.current) {
        waveRef.current.style.opacity = state === "idle" ? "0" : "1";
      }

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [state]);

  const badge = BADGE[state] || BADGE.idle;

  return (
    <div style={S.outer}>
      <div style={S.card}>
        {/* ── Mascot ── */}
        <div style={S.mascotWrap}>
          {/* glow ring — listening only */}
          <div ref={glowRef} style={S.glow} />

          <svg
            viewBox="0 0 120 140"
            width={200}
            height={220}
            style={{ position: "relative", zIndex: 1 }}
          >
            {/* body shadow */}
            <ellipse cx="60" cy="108" rx="22" ry="10" fill="#FFD54F" opacity="0.4" />

            {/* ears */}
            <path d="M28,65 Q20,55 22,44 Q24,36 32,40 L32,55Z" fill="#FFF176" stroke="#F9A825" strokeWidth="2" />
            <path d="M92,65 Q100,55 98,44 Q96,36 88,40 L88,55Z" fill="#FFF176" stroke="#F9A825" strokeWidth="2" />

            {/* body */}
            <rect x="28" y="48" width="64" height="60" rx="20" fill="#FFF176" stroke="#F9A825" strokeWidth="2.5" />

            {/* ear dots */}
            <circle cx="42" cy="62" r="3" fill="#F9A825" />
            <circle cx="78" cy="62" r="3" fill="#F9A825" />

            {/* blush */}
            <ellipse cx="36" cy="80" rx="7" ry="4" fill="#FFCCBC" opacity="0.6" />
            <ellipse cx="84" cy="80" rx="7" ry="4" fill="#FFCCBC" opacity="0.6" />

            {/* paws */}
            <circle cx="14" cy="78" r="8" fill="#FFF176" stroke="#F9A825" strokeWidth="2" />
            <circle cx="106" cy="78" r="8" fill="#FFF176" stroke="#F9A825" strokeWidth="2" />

            {/* collar */}
            <rect x="46" y="108" width="28" height="18" rx="6" fill="#26C6DA" stroke="#00ACC1" strokeWidth="1.5" />
            {/* bell */}
            <circle cx="60" cy="117" r="4" fill="#FFD700" stroke="#F9A825" strokeWidth="1" />

            {/* eyebrows */}
            <path ref={browL} d="M33,65 Q42,62 51,65" stroke="#888" strokeWidth="1.8" fill="none" strokeLinecap="round" />
            <path ref={browR} d="M69,65 Q78,62 87,65" stroke="#888" strokeWidth="1.8" fill="none" strokeLinecap="round" />

            {/* eyes — white */}
            <ellipse cx="42" cy="75" rx="10" ry="10" fill="white" stroke="#ddd" strokeWidth="0.5" />
            <ellipse cx="78" cy="75" rx="10" ry="10" fill="white" stroke="#ddd" strokeWidth="0.5" />

            {/* eyes — iris */}
            <ellipse ref={irisL} cx="42" cy="76" rx="6" ry="6" fill="#222" />
            <ellipse ref={irisR} cx="78" cy="76" rx="6" ry="6" fill="#222" />

            {/* eyes — shine */}
            <circle cx="44" cy="74" r="2" fill="white" />
            <circle cx="80" cy="74" r="2" fill="white" />

            {/* eyes — lids (blink) */}
            <ellipse ref={lidL} cx="42" cy="75" rx="10" ry="0" fill="#FFF176" />
            <ellipse ref={lidR} cx="78" cy="75" rx="10" ry="0" fill="#FFF176" />

            {/* mouth */}
            <path
              ref={mouth}
              d="M48,95 Q60,100 72,95"
              stroke="#E57373"
              strokeWidth="2"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
        </div>

        {/* ── Badge ── */}
        <div
          style={{
            ...S.badge,
            background: badge.bg,
            color: badge.color,
          }}
        >
          {badge.text}
        </div>

        {/* ── Wave bars ── */}
        <div
          ref={waveRef}
          style={{
            ...S.waveWrap,
            opacity: state === "idle" ? 0 : 1,
          }}
        >
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              ref={(el) => (barsRef.current[i] = el)}
              style={{ ...S.bar, height: 7 }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── Styles ─── */
const S = {
  outer: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    width: "100%",
  },
  card: {
    background: "#1a1a2e",
    borderRadius: 24,
    padding: "2rem 2.5rem",
    border: "1px solid #2a2a4a",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 12,
    boxShadow: "0 8px 40px rgba(0,0,0,0.45)",
  },
  mascotWrap: {
    position: "relative",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },
  glow: {
    position: "absolute",
    inset: -20,
    borderRadius: "50%",
    border: "3px solid #7c4dff",
    display: "none",
    animation: "pulse 1.8s ease-in-out infinite",
    pointerEvents: "none",
    zIndex: 0,
  },
  badge: {
    padding: "5px 16px",
    borderRadius: 20,
    fontSize: 13,
    fontWeight: 600,
    letterSpacing: 0.3,
    marginTop: 12,
    transition: "all 0.3s",
  },
  waveWrap: {
    display: "flex",
    justifyContent: "center",
    alignItems: "flex-end",
    gap: 4,
    height: 40,
    transition: "opacity 0.4s",
  },
  bar: {
    width: 5,
    borderRadius: 3,
    transition: "height 0.08s linear",
  },
};
