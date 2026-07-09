import type { HealthInfo } from "../types";

interface Props {
  health: HealthInfo | null;
}

export function Header({ health }: Props) {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          {/* Stylised NEM waveform */}
          <svg width="34" height="34" viewBox="0 0 34 34" role="img" aria-label="AEMO">
            <rect width="34" height="34" rx="8" fill="#1B3A6B" />
            <path
              d="M6 22 L12 12 L17 18 L22 8 L28 20"
              fill="none"
              stroke="#FFC220"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <div className="brand-text">
          <h1>AEMO NEM Operations Agent</h1>
          <p>National Electricity Market · dispatch, prices, notices, settlements</p>
        </div>
      </div>

      <div className="badges">
        <span className="badge badge-region" title="Model runs on an in-region provisioned-throughput endpoint">
          Australia East · in-region (PT endpoint)
        </span>
        {health && (
          <span
            className={`badge badge-status ${health.status === "ok" ? "ok" : "warn"}`}
            title={`Endpoint: ${health.pt_endpoint}`}
          >
            {health.status === "ok" ? "Connected" : "Degraded"}
            {health.genie_enabled ? " · Genie on" : ""}
          </span>
        )}
      </div>
    </header>
  );
}
