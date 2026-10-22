const API_BASE =
  import.meta.env.VITE_API_URL || "http://localhost:5001/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Erreur HTTP ${response.status}`);
  }
  return payload as T;
}

export type TradingConfigPayload = {
  prenom: string;
  nom: string;
  montant: number;
  crypto: "Bitcoin (BTC)" | "Binance Coin (BNB)" | "Ethereum (ETH)";
  intervalle: "1 Heure" | "1 Journée";
};

export type ClientRecord = {
  ClientOrderId: string;
  lastname: string;
  firstname: string;
  interval: string;
  type_crypto: string;
  usdt: number;
  solde_crypto: number;
};

export const api = {
  health: () => request<{ status: string; database: string }>("/health"),
  backtest: () => request<BacktestPayload>("/backtest"),
  createTradingConfig: (body: TradingConfigPayload) =>
    request<{ message: string; client: ClientRecord; existed: boolean }>(
      "/trading-configs",
      { method: "POST", body: JSON.stringify(body) }
    ),
  sendContact: (body: { name: string; email: string; subject: string; message: string }) =>
    request<{ message: string }>("/contact", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export type BacktestRow = {
  crypto: string;
  hold: number;
  arch: number;
  xgboost: number;
};

export type BacktestPayload = {
  initial_balance: number;
  currency: string;
  results: { "1h": BacktestRow[]; "1d": BacktestRow[] };
};
