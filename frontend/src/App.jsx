import { useEffect, useState } from "react";
import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function App() {
  const [apiStatus, setApiStatus] = useState("Checking backend...");
  const [error, setError] = useState("");

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const response = await axios.get(
          `${API_BASE_URL}/health`
        );

        const { project, status, version } = response.data;

        setApiStatus(
          `${project} backend is ${status} — version ${version}`
        );
      } catch (requestError) {
        console.error("Backend health check failed:", requestError);

        setApiStatus("Backend unavailable");
        setError(
          "FastAPI server check karein: http://127.0.0.1:8000"
        );
      }
    };

    checkBackend();
  }, []);

  return (
    <main className="page">
      <section className="status-card">
        <p className="eyebrow">
          AI-Powered E-Commerce Intelligence
        </p>

        <h1>VEXTRO</h1>

        <p className="description">
          Multi-platform market intelligence and decision
          support system for consumers and businesses.
        </p>

        <div className="status-box">
          <span>System Status</span>
          <strong>{apiStatus}</strong>
        </div>

        {error && (
          <p className="error-message">
            {error}
          </p>
        )}
      </section>
    </main>
  );
}

export default App;