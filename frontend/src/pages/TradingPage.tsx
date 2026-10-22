import { FormEvent, useMemo, useState } from "react";
import { ArrowRight, Check, CircleAlert } from "lucide-react";
import { api, ClientRecord, TradingConfigPayload } from "../api";

const cryptos: TradingConfigPayload["crypto"][] = [
  "Bitcoin (BTC)",
  "Binance Coin (BNB)",
  "Ethereum (ETH)",
];

export default function TradingPage() {
  const [prenom, setPrenom] = useState("");
  const [nom, setNom] = useState("");
  const [montant, setMontant] = useState(100);
  const [crypto, setCrypto] =
    useState<TradingConfigPayload["crypto"]>("Bitcoin (BTC)");
  const [intervalle, setIntervalle] =
    useState<TradingConfigPayload["intervalle"]>("1 Heure");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClientRecord | null>(null);
  const [existed, setExisted] = useState(false);
  const [error, setError] = useState("");

  const symbol = useMemo(() => {
    if (crypto.includes("BTC")) return "BTC";
    if (crypto.includes("BNB")) return "BNB";
    return "ETH";
  }, [crypto]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const response = await api.createTradingConfig({
        prenom,
        nom,
        montant,
        crypto,
        intervalle,
      });
      setResult(response.client);
      setExisted(response.existed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="trading-layout">
      <section className="intro-column">
        <p className="kicker">Configuration du bot</p>
        <h1>Préparer une stratégie de trading.</h1>
       

        <div className="market-note">
          <span className="market-symbol">{symbol}</span>
          <div>
            <small>ACTIF SÉLECTIONNÉ</small>
            <strong>{crypto}</strong>
          </div>
        </div>

        <dl className="compat-list">
          <div><dt>Identifiant</dt><dd>bot_Prénom_Nom</dd></div>
          <div><dt>Intervalle</dt><dd>1 Heure / 1 Journée</dd></div>
          <div><dt>Solde crypto initial</dt><dd>0</dd></div>
        </dl>
      </section>

      <section className="form-sheet">
        <form onSubmit={submit}>
          <div className="form-heading">
            <span>01</span>
            <div>
              <h2>Informations personnelles</h2>
              <p>Ces valeurs servent aussi à construire le ClientOrderId.</p>
            </div>
          </div>

          <div className="two-fields">
            <label>
              <span>Prénom</span>
              <input
                value={prenom}
                onChange={(e) => setPrenom(e.target.value)}
                placeholder="Epiphane"
                required
              />
            </label>
            <label>
              <span>Nom</span>
              <input
                value={nom}
                onChange={(e) => setNom(e.target.value)}
                placeholder="Egah"
                required
              />
            </label>
          </div>

          <div className="rule" />

          <div className="form-heading">
            <span>02</span>
            <div>
              <h2>Paramètres d'investissement</h2>
              <p>Les libellés enregistrés restent ceux de l'application d'origine.</p>
            </div>
          </div>

          <label>
            <span>Montant à investir (USDT)</span>
            <div className="amount-field">
              <input
                type="number"
                min="10"
                step="50"
                value={montant}
                onChange={(e) => setMontant(Number(e.target.value))}
                required
              />
              <b>USDT</b>
            </div>
            <small>Montant minimum requis : 10 USDT</small>
          </label>

          <div className="two-fields">
            <label>
              <span>Crypto-monnaie cible</span>
              <select
                value={crypto}
                onChange={(e) =>
                  setCrypto(e.target.value as TradingConfigPayload["crypto"])
                }
              >
                {cryptos.map((item) => <option key={item}>{item}</option>)}
              </select>
            </label>

            <fieldset>
              <legend>Intervalle de trading</legend>
              <label className="radio-line">
                <input
                  type="radio"
                  name="intervalle"
                  value="1 Heure"
                  checked={intervalle === "1 Heure"}
                  onChange={() => setIntervalle("1 Heure")}
                />
                <span>1 Heure</span>
              </label>
              <label className="radio-line">
                <input
                  type="radio"
                  name="intervalle"
                  value="1 Journée"
                  checked={intervalle === "1 Journée"}
                  onChange={() => setIntervalle("1 Journée")}
                />
                <span>1 Journée</span>
              </label>
            </fieldset>
          </div>

          {error && (
            <div className="message error">
              <CircleAlert size={17} />
              <span>{error}</span>
            </div>
          )}

          {result && (
            <div className="message success">
              <Check size={17} />
              <div>
                <strong>
                  {existed ? "Ce client existe déjà." : "Paramètres enregistrés."}
                </strong>
                <p>
                  {result.firstname} {result.lastname} · {result.type_crypto} ·{" "}
                  {result.interval} · {result.usdt.toLocaleString("fr-FR")} USDT
                </p>
              </div>
            </div>
          )}

          <button className="submit-button" type="submit" disabled={loading}>
            {loading ? "Enregistrement…" : "Lancer l'application de trading"}
            <ArrowRight size={17} />
          </button>
        </form>
      </section>
    </div>
  );
}
