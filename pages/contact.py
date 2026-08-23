import streamlit as st
from pathlib import Path


# Liens personnels

LINKEDIN_URL = "https://www.linkedin.com/in/egahepiphane/"
GITHUB_URL = "https://github.com/epiphane-egah"

st.set_page_config(page_title="Contact — Bot de trading", page_icon="✉️", layout="centered")


# Style — cohérent avec le thème "terminal de trading" du rapport

st.markdown(
    "\n".join(
        line.strip()
        for line in """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

        :root{
            --bg:        #0B0E14;
            --bg-panel:  #11151D;
            --line:      #232A38;
            --ink:       #E7E6E2;
            --ink-dim:   #8B93A6;
            --orange:    #E8873A;
            --blue:      #4C8DFF;
        }

        .stApp { background: var(--bg); }
        h1, h2, h3, h4, h5 { font-family: 'Space Grotesk', sans-serif; color: var(--ink); }
        p, li, label, span, div { font-family: 'Inter', sans-serif; }

        header[data-testid="stHeader"]{ display: none; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container{ padding-top: 2rem; max-width: 720px; }

        /* Formulaire de contact */
        form{
            background: var(--bg-panel);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 1.4rem;
            display:flex;
            flex-direction:column;
            gap: 0.7rem;
        }
        form input, form textarea{
            background: #161B26;
            border: 1px solid var(--line);
            border-radius: 8px;
            color: var(--ink);
            padding: 0.65rem 0.8rem;
            font-family: 'Inter', sans-serif;
            font-size: 0.92rem;
        }
        form input::placeholder, form textarea::placeholder{ color: var(--ink-dim); }
        form textarea{ min-height: 110px; resize: vertical; }
        form button{
            background: var(--orange);
            color: #0B0E14;
            border: none;
            border-radius: 8px;
            padding: 0.65rem 1.2rem;
            font-weight: 600;
            font-family: 'Space Grotesk', sans-serif;
            cursor: pointer;
            align-self: flex-start;
        }
        form button:hover{ opacity: 0.88; }

        /* Cartes de liens sociaux */
        .social-row{ display:flex; gap: 0.9rem; margin: 1rem 0 1.6rem 0; flex-wrap: wrap; }
        .social-card{
            flex:1;
            min-width: 220px;
            background: var(--bg-panel);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 1rem 1.2rem;
            text-decoration: none !important;
            display:flex;
            align-items:center;
            gap: 0.8rem;
            transition: border-color 0.15s ease;
        }
        .social-card:hover{ border-color: var(--orange); }
        .social-icon{ font-size: 1.5rem; }
        .social-label{ font-family:'IBM Plex Mono', monospace; font-size: 0.72rem; letter-spacing:0.1em; text-transform:uppercase; color: var(--ink-dim); }
        .social-name{ font-family:'Space Grotesk', sans-serif; font-weight:600; color: var(--ink); font-size: 1rem; }

        .footer-credit{
            font-family:'IBM Plex Mono', monospace;
            font-size: 0.82rem;
            color: var(--ink-dim);
        }
        .footer-credit a{ color: var(--orange); text-decoration: none; }
        </style>
        """.strip("\n").split("\n")
    ),
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# En-tête
# --------------------------------------------------------------------------
st.warning("#### Signaler un bug 👾 ou proposer une amélioration ⚡")

st.markdown("#### 📬 Me contacter")

contact_form = f"""
<form action="https://formsubmit.co/egahepiphane@gmail.com" method="POST" enctype="multipart/form-data">
     <input type="hidden" name="_captcha" value="false">
     <input type="text" name="name" placeholder="Votre nom" required>
     <input type="text" name="_subject" placeholder="Sujet">
     <input type="email" name="email" placeholder="Votre email" required>
     <textarea name="message" placeholder="Votre message"></textarea>
     <input type="file" class="img_btn" name="Upload Image" accept="image/png, image/jpeg">
     <input type="hidden" name="_next" value="{GITHUB_URL}">
     <button type="submit">Envoyer</button>
</form>
"""
st.markdown(contact_form, unsafe_allow_html=True)

st.markdown("---")


# Réseaux

st.markdown("#### 🔗 Retrouve-moi en ligne")
st.markdown(
    f"""
    <div class="social-row">
        <a class="social-card" href="{LINKEDIN_URL}" target="_blank">
            <span class="social-icon">💼</span>
            <span>
                <div class="social-label">LinkedIn</div>
                <div class="social-name">Épiphane Egah</div>
            </span>
        </a>
        <a class="social-card" href="{GITHUB_URL}" target="_blank">
            <span class="social-icon">🐙</span>
            <span>
                <div class="social-label">GitHub</div>
                <div class="social-name">@epiphane-egah</div>
            </span>
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")


# Pied de page

st.markdown(
    f"""
    <p class="footer-credit">
        🖼️ Interface réalisée par
        <a href="{GITHUB_URL}" target="_blank">Épiphane Egah</a>
    </p>
    """,
    unsafe_allow_html=True,
)


# CSS local additionnel (optionnel — n'échoue pas si le fichier est absent)

def local_css(file_name: Path) -> None:
    if file_name.exists():
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


local_css(Path(__file__).resolve().parent / "style" / "style.css")
