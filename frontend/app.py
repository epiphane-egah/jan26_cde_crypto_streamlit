import streamlit as st

st.set_page_config(
    page_title="Crypto Dashboard",
    page_icon="₿",
    layout="wide",
)

trading = st.Page(
    "pages/trading_bot.py",
    title="Bot",
    icon=":material/dashboard:",
    default=True,
)

backtest = st.Page(
    "pages/backtest.py",
    title="Backtest",
    icon=":material/account_balance_wallet:",
)

analytics = st.Page(
    "pages/analytics.py",
    title="Analytics",
    icon=":material/show_chart:",
)

contact = st.Page(
    "pages/contact.py",
    title="Contact",
    icon=":material/settings:",
)


pg = st.navigation(
    {
        "Trading": [
            trading,
            backtest,
            analytics,
        ],
        "Contact": [
            contact
        ],
    },
    position="sidebar",
)

pg.run()