import { Link } from "react-router-dom";

const helpAreas = [
  ["Product data", "Report a wrong title, image, specification or marketplace match."],
  ["Prices & links", "Tell us when an offer, stock status or retailer destination needs review."],
  ["Account & alerts", "Get help with access, saved targets and alert management."],
  ["Business workspace", "Ask about organizations, competitor tracking or sales intelligence."],
];

function SupportPage() {
  return <section className="bg-vextro-canvas py-10 sm:py-16"><div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
    <header className="rounded-[2rem] border border-emerald-100 bg-gradient-to-br from-white via-emerald-50 to-blue-50 px-6 py-12 sm:px-12 lg:py-16"><span className="text-xs font-black uppercase tracking-[0.2em] text-vextro-primary">VEXTRO support</span><h1 className="mt-4 max-w-3xl text-4xl font-black tracking-[-0.05em] text-vextro-ink sm:text-6xl">Answers, fixes and a real way to reach us.</h1><p className="mt-5 max-w-2xl text-base leading-8 text-vextro-muted">Start with the area closest to your question. For data issues, include the VEXTRO product link and marketplace name.</p></header>
    <div className="mt-8 grid gap-4 sm:grid-cols-2">{helpAreas.map(([title, description], index) => <article className="rounded-3xl border border-vextro-border bg-white p-7 shadow-sm" key={title}><span className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-sm font-black text-vextro-primary">{index + 1}</span><h2 className="mt-5 text-xl font-black text-vextro-ink">{title}</h2><p className="mt-2 text-sm leading-7 text-vextro-muted">{description}</p></article>)}</div>
    <div className="mt-8 flex flex-col gap-6 rounded-3xl bg-vextro-ink p-7 text-white sm:p-10 lg:flex-row lg:items-center lg:justify-between"><div><span className="text-xs font-black uppercase tracking-widest text-emerald-300">Need more help?</span><h2 className="mt-2 text-2xl font-black">Contact the VEXTRO team</h2><p className="mt-2 text-sm text-slate-300">Typical response time is 1–2 business days.</p></div><div className="flex flex-wrap gap-3"><a className="rounded-xl bg-vextro-primary px-6 py-3 text-sm font-black text-white hover:bg-vextro-primary-dark" href="mailto:support@vextro.pk?subject=VEXTRO%20support%20request">support@vextro.pk</a><Link className="rounded-xl border border-white/20 px-6 py-3 text-sm font-black hover:bg-white/10" to="/contact">Contact options</Link></div></div>
  </div></section>;
}

export default SupportPage;
