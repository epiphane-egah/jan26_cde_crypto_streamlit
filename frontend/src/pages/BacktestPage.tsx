import { useEffect, useState } from "react";
import { ArrowDownRight, ArrowUpRight, ChartNoAxesCombined, Clock3, Database, TrendingUp } from "lucide-react";
import { api, BacktestPayload, BacktestRow } from "../api";

const money = (value: number) => new Intl.NumberFormat("fr-FR", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
const fmtDelta = (row: BacktestRow) => (row.arch / row.hold - 1) * 100;

export default function BacktestPage() {
  const [data, setData] = useState<BacktestPayload | null>(null);
  const [period, setPeriod] = useState<"1h" | "1d">("1h");
  const [error, setError] = useState("");
  useEffect(() => { api.backtest().then(setData).catch(e => setError(e.message)); }, []);
  const rows = data?.results[period] ?? [];

  return <div className="page-stack">
    <section className="page-intro"><span className="eyebrow orange">RAPPORT / HISTORIQUE</span><h2>Backtest des stratégies</h2><p>Comparaison des stratégies ARCH, XGBoost et Hold.</p></section>
    <div className="stats-grid">
      <Stat icon={<Database size={18}/>} label="Capital initial" value="1 000 USDT" hint="Base du rapport"/>
      <Stat icon={<TrendingUp size={18}/>} label="Stratégies" value="3" hint="ARCH · XGBoost · Hold"/>
      <Stat icon={<Clock3 size={18}/>} label="Granularités" value="1h / 1j" hint="Deux intervalles"/>
    </div>
    <section className="panel table-panel">
      <div className="table-heading"><div><span className="eyebrow">RÉSULTATS CHIFFRÉS</span><h3>Valeur finale du portefeuille</h3></div><div className="segmented"><button className={period === "1h" ? "selected" : ""} onClick={() => setPeriod("1h")}>1 heure</button><button className={period === "1d" ? "selected" : ""} onClick={() => setPeriod("1d")}>1 jour</button></div></div>
      {error && <div className="notice error">{error}</div>}
      {!data && !error && <p className="muted">Chargement des résultats...</p>}
      {data && <div className="table-wrap"><table><thead><tr><th>Actif</th><th>Hold (référence)</th><th>ARCH</th><th>XGBoost</th><th>ARCH vs Hold</th></tr></thead><tbody>{rows.map(row => <tr key={row.crypto}><td><span className="coin-symbol">{row.crypto.slice(0,1)}</span><strong>{row.crypto}</strong></td><td>{money(row.hold)}</td><td>{money(row.arch)}</td><td>{money(row.xgboost)}</td><td><span className={`delta ${fmtDelta(row) >= 0 ? "positive" : "negative"}`}>{fmtDelta(row) >= 0 ? <ArrowUpRight size={14}/> : <ArrowDownRight size={14}/>} {fmtDelta(row).toLocaleString("fr-FR", { maximumFractionDigits: 1 })}%</span></td></tr>)}</tbody></table></div>}
    </section>
    <section className="panel">
      <div className="panel-title"><div className="icon-tile orange"><ChartNoAxesCombined size={19}/></div><div><h3>Visualisations du rapport</h3></div></div>
      <div className="chart-grid">
        <figure><figcaption>Évolution du portefeuille</figcaption><img src="/assets/evolution_portefeuille.png" alt="Évolution du portefeuille"/></figure>
        <figure><figcaption>Performance finale — 1 heure</figcaption><img src="/assets/comparaison_perf_heure.png" alt="Comparaison des performances sur une heure"/></figure>
        <figure><figcaption>Performance finale — 1 jour</figcaption><img src="/assets/comparaison_perf_jour.png" alt="Comparaison des performances sur un jour"/></figure>
      </div>
    </section>
  </div>;
}

function Stat({ icon, label, value, hint }: { icon: React.ReactNode; label: string; value: string; hint: string }) {
  return <div className="panel stat-card"><div className="stat-icon">{icon}</div><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>;
}
