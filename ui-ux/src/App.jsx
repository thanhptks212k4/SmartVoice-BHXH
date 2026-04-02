import { useEffect, useState } from "react";
import { io } from "socket.io-client";
import MascotCard from "./pages/MascotCard";

const socket = io("http://localhost:5500", { autoConnect: true });

export default function App() {
  const [voiceState, setVoiceState] = useState("idle");

  useEffect(() => {
    socket.on("state", (data) => setVoiceState(data.s));
    window.setVoiceState = setVoiceState;
    return () => socket.off("state");
  }, []);

  return (
    <div style={{ display:"flex", justifyContent:"center",
                  alignItems:"center", minHeight:"100vh" }}>
      <div style={{ background:"#1a1a2e", borderRadius:24,
                    padding:"2rem", border:"1px solid #2a2a4a" }}>
        <MascotCard state={voiceState} />
      </div>
    </div>
  );
}
