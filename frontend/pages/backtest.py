"""
Rapport de backtesting — Bot de trading crypto
Streamlit app générée à partir du document source de l'utilisateur.
"""

import streamlit as st
from pathlib import Path

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Bot de trading — Rapport de backtest",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ASSETS = Path(__file__).parent.parent / "staticfiles"


def html(block: str) -> None:
    """Render a raw HTML block with st.markdown.

    Streamlit's markdown parser treats any line indented 4+ spaces as a
    code block, which breaks multi-line HTML written inside an indented
    triple-quoted string. Stripping each line's leading whitespace avoids
    that, while HTML itself doesn't care about whitespace between tags.
    """
    cleaned = "\n".join(line.strip() for line in block.strip("\n").split("\n"))
    st.markdown(cleaned, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# STYLE — thème "terminal de trading" : fond quasi-noir, accents bleu/orange
# repris directement des courbes xgboost (bleu) et arch (orange) du rapport.
# --------------------------------------------------------------------------


html(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    :root{
        --bg:        #0B0E14;
        --bg-panel:  #11151D;
        --bg-panel2: #161B26;
        --line:      #232A38;
        --ink:       #E7E6E2;
        --ink-dim:   #8B93A6;
        --blue:      #4C8DFF;   /* xgboost */
        --orange:    #E8873A;  /* arch */
        --green:     #4CC38A;
        --red:       #E5566D;
    }

    html, body, [class*="css"]  { color: var(--ink); }
    .stApp { background: var(--bg); }

    /* Kill default streamlit padding weirdness */
    .block-container{ padding-top: 1.4rem; padding-bottom: 4rem; max-width: 1180px; }

    h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.01em; }
    p, li, span, div { font-family: 'Inter', sans-serif; }
    .mono { font-family: 'IBM Plex Mono', monospace; }

    /* ---------- Header / ticker ---------- */
    .eyebrow{
        font-family:'IBM Plex Mono', monospace;
        font-size:0.78rem;
        letter-spacing:0.18em;
        text-transform:uppercase;
        color: var(--ink-dim);
        margin-bottom:0.4rem;
    }
    .hero-title{
        font-size:2.6rem;
        font-weight:700;
        line-height:1.08;
        margin:0 0 0.6rem 0;
        background: linear-gradient(90deg, #F2F1ED 0%, #B9C2D6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-sub{
        color: var(--ink-dim);
        font-size:1.02rem;
        max-width: 640px;
        line-height:1.55;
    }

    .ticker{
        margin-top:1.6rem;
        border-top:1px solid var(--line);
        border-bottom:1px solid var(--line);
        padding: 0.85rem 0;
        display:flex;
        gap: 2.2rem;
        flex-wrap:wrap;
        font-family:'IBM Plex Mono', monospace;
        font-size:0.82rem;
        color: var(--ink-dim);
    }
    .ticker b{ color: var(--ink); font-weight:600; }
    .dot-blue{ color: var(--blue); }
    .dot-orange{ color: var(--orange); }

    /* ---------- Section labels ---------- */
    .sec-label{
        font-family:'IBM Plex Mono', monospace;
        font-size:0.75rem;
        letter-spacing:0.16em;
        text-transform:uppercase;
        color: var(--orange);
        margin: 2.6rem 0 0.3rem 0;
    }
    .sec-title{
        font-size:1.5rem;
        font-weight:600;
        margin: 0 0 1rem 0;
    }

    /* ---------- Strategy cards ---------- */
    .strat-card{
        background: var(--bg-panel);
        border:1px solid var(--line);
        border-radius: 10px;
        padding: 1.3rem 1.4rem;
        height:100%;
    }
    .strat-num{
        font-family:'IBM Plex Mono', monospace;
        font-size:0.78rem;
        color: var(--ink-dim);
        letter-spacing:0.08em;
    }
    .strat-name{
        font-size:1.12rem;
        font-weight:600;
        margin: 0.25rem 0 0.6rem 0;
    }
    .strat-body{ color:#C7CCD9; font-size:0.93rem; line-height:1.6; }
    .strat-formula{
        margin-top:0.7rem;
        background: var(--bg-panel2);
        border:1px solid var(--line);
        border-radius:6px;
        padding:0.55rem 0.75rem;
        font-family:'IBM Plex Mono', monospace;
        font-size:0.85rem;
        color: var(--orange);
        display:inline-block;
    }

    /* ---------- Table ---------- */
    .res-table{ width:100%; border-collapse: collapse; font-family:'IBM Plex Mono', monospace; font-size:0.9rem;}
    .res-table th{
        text-align:right;
        color: var(--ink-dim);
        font-weight:500;
        font-size:0.72rem;
        letter-spacing:0.1em;
        text-transform:uppercase;
        padding: 0.55rem 0.8rem;
        border-bottom:1px solid var(--line);
    }
    .res-table th:first-child, .res-table td:first-child{ text-align:left; }
    .res-table td{
        text-align:right;
        padding: 0.65rem 0.8rem;
        border-bottom:1px solid var(--line);
        color: var(--ink);
    }
    .res-table tr:last-child td{ border-bottom:none; }
    .pos{ color: var(--green); }
    .neg{ color: var(--red); }
    .crypto-name{ font-family:'Space Grotesk',sans-serif; font-weight:600; color:var(--ink); }

    /* ---------- Caption under charts ---------- */
    .chart-caption{
        color: var(--ink-dim);
        font-size:0.85rem;
        margin-top:0.5rem;
        line-height:1.5;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"]{ gap: 6px; border-bottom:1px solid var(--line); }
    .stTabs [data-baseweb="tab"]{
        font-family:'IBM Plex Mono', monospace;
        font-size:0.85rem;
        color: var(--ink-dim);
        background: transparent;
    }
    .stTabs [aria-selected="true"]{ color: var(--orange) !important; }

    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}

    /* Streamlit's own top header bar is fixed above the content and was
       overlapping our custom eyebrow/title regardless of its height — this
       report doesn't need it (no sidebar toggle in use), so remove it from
       layout entirely rather than trying to color/size it. */
    header[data-testid="stHeader"]{
        display: none;
    }
    </style>
    """
)

# --------------------------------------------------------------------------
# HEADER
# --------------------------------------------------------------------------
html('<div class="eyebrow">Backtest · BTC / BNB / ETH · Capital initial 1 000 USDT</div>')
html('<div class="hero-title">Bot de trading algorithmique<br>— rapport de performance</div>')
html(
    '<div class="hero-sub">Deux stratégies de décision d\'achat / vente sont mises en place et comparées '
    'entre elles, ainsi qu\'à une stratégie de référence passive (<i>hold</i>), sur trois cryptomonnaies '
    'et deux granularités temporelles.</div>'
)
html(
    """
    <div class="ticker">
        <span><span class="dot-orange">●</span> ARCH — croisement de moyennes mobiles + gestion du risque par volatilité</span>
        <span><span class="dot-blue">●</span> XGBOOST — prédiction directionnelle par gradient boosting</span>
        <span>◇ HOLD — stratégie de référence passive</span>
    </div>
    """
)

# --------------------------------------------------------------------------
# SECTION — Méthodologie
# --------------------------------------------------------------------------
html('<div class="sec-label">01 — Méthodologie</div>')
html('<div class="sec-title">Les stratégies mises en place</div>')

c1, c2, c3 = st.columns(3, gap="medium")

with c1:
    html(
        """
        <div class="strat-card">
            <div class="strat-num">STRATÉGIE 01</div>
            <div class="strat-name">Croisement de moyennes mobiles + modèle ARCH</div>
            <div class="strat-body">
                On décide d'acheter lorsque la moyenne mobile 200 dépasse la moyenne mobile 600
                (« croix d'or »), et de vendre lorsqu'elle repasse en dessous (« croix de la mort »).
                <br><br>
                Pour limiter le risque, un modèle ARCH est utilisé pour prédire la volatilité future
                à horizon 1. Si cette volatilité prédite dépasse 0,05, seule une fraction du capital
                est investie plutôt que sa totalité, selon la formule suivante :
            </div>
            <div class="strat-formula">min(1, 0.05 / volatilité_prédite)</div>
        </div>
        """
    )

with c2:
    html(
        """
        <div class="strat-card">
            <div class="strat-num">STRATÉGIE 02</div>
            <div class="strat-name">Prédiction par gradient boosting</div>
            <div class="strat-body">
                Un modèle de <i>gradient boosting</i> prédit la valeur de chaque cryptomonnaie à
                horizon 1.
                <br><br>
                Si la valeur prédite est supérieure à la valeur actuelle, le signal est à l'achat
                (tendance haussière) ; si elle est inférieure, le signal est à la vente (tendance
                baissière).
            </div>
        </div>
        """
    )

with c3:
    html(
        """
        <div class="strat-card">
            <div class="strat-num">RÉFÉRENCE</div>
            <div class="strat-name">Stratégie « hold »</div>
            <div class="strat-body">
                Enfin, le gain théorique d'une position passive — acheter au départ et ne plus
                jamais revendre — est calculé pour chaque cryptomonnaie. Cette stratégie sert de
                référence pour juger si les deux modèles actifs créent réellement de la valeur.
            </div>
        </div>
        """
    )

# --------------------------------------------------------------------------
# SECTION — Résultats chiffrés
# --------------------------------------------------------------------------
html('<div class="sec-label">02 — Résultats</div>')
html('<div class="sec-title">Valeur finale du portefeuille</div>')
html(
    '<p style="color:var(--ink-dim); font-size:0.93rem; margin-top:-0.6rem;">'
    'Capital de départ : 1 000 USDT et 0 cryptomonnaie. Valeurs en dollars, à l\'issue du backtest.</p>'
)

results = {
    "1h": [
        {"crypto": "BTC", "hold": 14690.26, "arch": 9655.24, "xgboost": 10},
        {"crypto": "BNB", "hold": 337211.76, "arch": 280188.85, "xgboost": 10},
        {"crypto": "ETH", "hold": 5917.34, "arch": 20449.96, "xgboost": 10},
    ],
    "1d": [
        {"crypto": "BTC", "hold": 14750.36, "arch": 4203.56, "xgboost": 9},
        {"crypto": "BNB", "hold": 364105.67, "arch": 8659.22, "xgboost": 7867},
        {"crypto": "ETH", "hold": 5884.40, "arch": 1536.84, "xgboost": 615},
    ],
}


def fmt_usd(v):
    return f"${v:,.2f}".replace(",", " ").replace(".", ",")


def build_table(rows):
    html = """
    <table class="res-table">
        <thead>
            <tr>
                <th>Crypto</th>
                <th>Hold (référence)</th>
                <th>ARCH</th>
                <th>XGBoost</th>
                <th>ARCH vs Hold</th>
            </tr>
        </thead>
        <tbody>
    """
    for r in rows:
        delta = r["arch"] / r["hold"] - 1
        delta_class = "pos" if delta >= 0 else "neg"
        delta_str = f"{'+' if delta>=0 else ''}{delta*100:,.0f}%".replace(",", " ")
        html += f"""
            <tr>
                <td class="crypto-name">{r['crypto']}</td>
                <td>{fmt_usd(r['hold'])}</td>
                <td>{fmt_usd(r['arch'])}</td>
                <td>{fmt_usd(r['xgboost'])}</td>
                <td class="{delta_class}">{delta_str}</td>
            </tr>
        """
    html += "</tbody></table>"
    return html


tab1h, tab1d = st.tabs(["INTERVALLE — 1 HEURE", "INTERVALLE — 1 JOUR"])

with tab1h:
    html(build_table(results["1h"]))
    html(
        '<div class="chart-caption">Sur l\'intervalle 1h, le modèle XGBoost reste quasiment '
        'inactif (valeur finale proche de 0), tandis que la stratégie ARCH dépasse largement '
        'la stratégie hold sur BTC et ETH — mais reste en retrait sur BNB.</div>'
    )

with tab1d:
    html(build_table(results["1d"]))
    html(
        '<div class="chart-caption">Sur l\'intervalle 1 jour, les écarts sont plus resserrés : '
        'XGBoost redevient compétitif sur BNB et ETH, mais aucune des deux stratégies actives '
        'ne parvient à dépasser le hold sur cet intervalle.</div>'
    )

# --------------------------------------------------------------------------
# SECTION — Graphiques
# --------------------------------------------------------------------------
html('<div class="sec-label">03 — Visualisations</div>')
html('<div class="sec-title">Évolution du portefeuille</div>')
html(
    '<p style="color:var(--ink-dim); font-size:0.93rem; margin-top:-0.6rem;">'
    'Comparaison de la valeur du portefeuille dans le temps, par cryptomonnaie et par intervalle, '
    'pour les stratégies ARCH et XGBoost.</p>'
)

img_path = ASSETS / "evolution_portefeuille.png"
if img_path.exists():
    st.image(str(img_path), use_container_width=True)
else:
    st.warning("Image introuvable : assets/evolution_portefeuille.png")

html('<div class="sec-title" style="margin-top:2.2rem;">Performance finale par crypto et stratégie</div>')

col_a, col_b = st.columns(2, gap="large")
with col_a:
    html('<p class="chart-caption" style="margin-bottom:0.4rem;"><b>Intervalle 1 heure</b> — échelle logarithmique</p>')
    p1 = ASSETS / "comparaison_perf_heure.png"
    if p1.exists():
        st.image(str(p1), use_container_width=True)

with col_b:
    html('<p class="chart-caption" style="margin-bottom:0.4rem;"><b>Intervalle 1 jour</b> — échelle logarithmique</p>')
    p2 = ASSETS / "comparaison_perf_jour.png"
    if p2.exists():
        st.image(str(p2), use_container_width=True)

# --------------------------------------------------------------------------
# FOOTER
# --------------------------------------------------------------------------
html(
    """
    <div style="margin-top:3rem; padding-top:1.2rem; border-top:1px solid var(--line);
                color:var(--ink-dim); font-size:0.8rem; font-family:'IBM Plex Mono',monospace;">
    
    </div>
    """
)