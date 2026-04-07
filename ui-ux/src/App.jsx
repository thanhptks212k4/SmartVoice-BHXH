import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import VoicePage from "./pages/VoicePage";

function PrivateRoute({ children }) {
  return localStorage.getItem("token") ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"      element={<LoginPage />} />
        <Route path="/voice" element={<PrivateRoute><VoicePage /></PrivateRoute>} />
      </Routes>
    </BrowserRouter>
  );
}
