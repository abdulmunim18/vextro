import { Link } from "react-router-dom";

const steps = [
  ["01", "Search a product", "Find a phone or other product by its familiar brand and model name."],
  ["02", "We normalize listings", "VEXTRO groups equivalent Daraz and PriceOye titles into one product while keeping variants separate."],
  ["03", "Compare with context", "Review current offers, seller links, specifications and historical price movement before deciding."],
];

function HowItWorksPage() {
  return <section className="bg-vextro-canvas py-10 sm:py-16"><div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
    <div className="overflow-hidden rounded-[2rem] bg-gradient-to-br from-emerald-950 via-vextro-ink to-slate-900 px-6 py-14 text-white sm:px-12 lg:px-16 lg:py-20"><span className="text-xs font-black uppercase tracking-[0.2em] text-emerald-300">How VEXTRO works</span><h1 className="mt-5 max-w-4xl text-4xl font-black tracking-[-0.05em] sm:text-6xl">From scattered listings to one clear comparison.</h1><p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">We collect marketplace information, identify equivalent products and present the useful differences without hiding where the data came from.</p></div>
    <div className="relative mt-8 grid gap-5 lg:grid-cols-3">{steps.map(([number, title, description]) => <article className="rounded-3xl border border-vextro-border bg-white p-7 shadow-sm" key={number}><span className="text-4xl font-black text-emerald-200">{number}</span><h2 className="mt-6 text-2xl font-black text-vextro-ink">{title}</h2><p className="mt-3 text-sm leading-7 text-vextro-muted">{description}</p></article>)}</div>
    <div className="mt-8 grid gap-6 rounded-3xl border border-vextro-border bg-white p-7 sm:p-10 lg:grid-cols-2"><div><span className="text-xs font-black uppercase tracking-widest text-vextro-primary">Built for trust</span><h2 className="mt-3 text-3xl font-black tracking-tight text-vextro-ink">What happens when no exact match exists?</h2></div><div className="text-sm leading-7 text-vextro-muted"><p>VEXTRO does not invent a price or combine a similar-looking model. The product page clearly marks the missing marketplace and offers a direct search option.</p><Link className="mt-6 inline-flex rounded-xl bg-vextro-primary px-6 py-3 font-black text-white hover:bg-vextro-primary-dark" to="/products">Try product search →</Link></div></div>
  </div></section>;
}

export default HowItWorksPage;
