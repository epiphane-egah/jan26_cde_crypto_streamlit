import { FormEvent, useState } from "react";
import { Github, Linkedin, Mail, Send } from "lucide-react";
import { api } from "../api";

export default function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault(); setLoading(true); setNotice(null);
    try {
      const result = await api.sendContact({ name, email, subject, message });
      setNotice({ kind: "success", text: result.message });
    } catch (err) {
      setNotice({ kind: "error", text: err instanceof Error ? err.message : "Erreur" });
    } finally { setLoading(false); }
  }

  return <div className="page-stack">
    <section className="page-intro"><span className="eyebrow orange">CONTACT / SUPPORT</span><h2>Une question ou une idée ?</h2><p>Utilise le formulaire pour préparer un message ou retrouve les liens du projet.</p></section>
    <div className="content-grid">
      <form className="panel form-panel" onSubmit={submit}>
        <div className="panel-title"><div className="icon-tile blue"><Mail size={19}/></div><div><h3>Envoyer un message</h3><p>Les champs marqués sont obligatoires.</p></div></div>
        <label>Nom<input value={name} onChange={e => setName(e.target.value)} required maxLength={120}/></label>
        <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254}/></label>
        <label>Sujet<input value={subject} onChange={e => setSubject(e.target.value)} maxLength={160}/></label>
        <label>Message<textarea value={message} onChange={e => setMessage(e.target.value)} required rows={5} maxLength={5000}/></label>
        {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
        <button className="primary-button" type="submit" disabled={loading}>{loading ? "Envoi..." : "Soumettre le message"} <Send size={16}/></button>

      </form>
      <aside className="panel side-summary"><span className="eyebrow">LIENS</span><h3>Retrouve-moi en ligne</h3>
        <a className="social-link" href="https://www.linkedin.com/in/egahepiphane/" target="_blank" rel="noreferrer"><Linkedin size={20}/><span><strong>LinkedIn</strong><small>Épiphane Egah</small></span></a>
        <a className="social-link" href="https://github.com/epiphane-egah" target="_blank" rel="noreferrer"><Github size={20}/><span><strong>GitHub</strong><small>@epiphane-egah</small></span></a>
      </aside>
    </div>
  </div>;
}
