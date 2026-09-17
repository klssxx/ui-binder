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

  useEffect(() => {
    api.health().then((h) => {
      setInfo(h.vision_provider);
      setProvider(h.vision_provider.configured);
    }).catch(() => {});
  }, []);

  const handleChange = async (newProvider: string) => {
    // In a real implementation, this would update a setting
    // For now, just visual feedback
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
            title={p === "heuristic" ? "Local (sin red)" : p}
          >
            {p === "heuristic" ? "Local" : p}
          </button>
        ))}
      </div>
      {info.remote_configured && (
        <span className="vision-privacy" title="Proveedor remoto configurado">
          ☁️
        </span>
      )}
    </div>
  );
}
