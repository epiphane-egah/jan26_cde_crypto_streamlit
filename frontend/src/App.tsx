import { NavLink, Route, Routes } from "react-router-dom";
import { Bot, FlaskConical, Mail, WalletCards } from "lucide-react";
import TradingPage from "./pages/TradingPage";
import BacktestPage from "./pages/BacktestPage";
import ContactPage from "./pages/ContactPage";

const links = [
  { to: "/", label: "Bot", icon: Bot, end: true },
  { to: "/backtest", label: "Backtest", icon: WalletCards },
  { to: "/contact", label: "Contact", icon: Mail },
];

export default function App() {
  return (
    <div className="site-shell">
      <header className="site-header">
        <NavLink to="/" className="wordmark">
          <span className="wordmark-symbol">₿</span>
          <span>crypto.bot</span>
        </NavLink>

        <nav className="main-nav" aria-label="Navigation principale">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

      </header>

      <main className="site-main">
        <Routes>
          <Route path="/" element={<TradingPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/contact" element={<ContactPage />} />
        </Routes>
      </main>

      <footer className="site-footer">
        <span>Crypto Bot</span>
      </footer>
    </div>
  );
}
