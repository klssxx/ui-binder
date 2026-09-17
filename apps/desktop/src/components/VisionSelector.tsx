/** Vision provider selector - shows available vision providers. */
import { useState, useEffect } from "react";
import { api } from "../api/client";

export interface VisionProviderInfo {
  configured: string;
  remote_configured: boolean;
  available: string[];
}

export function VisionProviderSelector() {
  const [provider, setProvider] = useState<string | null>(null);
  const [info, setInfo] = useState<VisionProviderInfo | null>(null);

  // Load saved provider from localStorage
  useEffect(() => {
    const savedProvider = localStorage.getItem("uibinder.visionProvider");
    api.health().then((h) => {
      setInfo(h.vision_provider);
      setProvider(savedProvider || h.vision_provider.configured || "heuristic");
    }).catch(() => {});
  }, []);

  const handleChange = (newProvider: string) => {
    localStorage.setItem("uibinder.visionProvider", newProvider);
    setProvider(newProvider);
  };

  if (!info) return null;

  return (
    <div className="vision-selector">
      <label>Visión:</label>
      <div className="vision-buttons">
        {info.available.map((p) => (
          <button
            key={p}
            className={`vision-btn ${provider === p ? "active" : ""}`}
            onClick={() => handleChange(p)}
            title={p === "heuristic" ? "Local (sin red)" : p === "remote" ? "Remoto (requiere configuración)" : "Automático (local primero)"}
            disabled={p === "remote" && !info.remote_configured}
          >
            {p === "heuristic" ? "Local" : p === "remote" ? "Remoto" : "Auto"}
          </button>
        ))}
      </div>
      {info.remote_configured && (
        <span className="vision-privacy" title="Proveedor remoto configurado">
          ☁️
        </span>
      )}
      {!info.remote_configured && (
        <span className="vision-warning" title="Proveedor remoto no configurado">
          ⚠️ Configura UIBINDER_VISION_* en .env
        </span>
      )}
    </div>
  );
}
