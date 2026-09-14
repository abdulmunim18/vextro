import { Link } from "react-router-dom";

const themes = {
  emerald: { glow: "bg-emerald-400/20", eyebrow: "text-emerald-300", badge: "border-emerald-200 bg-emerald-50 text-emerald-800", number: "bg-emerald-100 text-emerald-800", button: "bg-vextro-primary hover:bg-vextro-primary-dark" },
  blue: { glow: "bg-blue-400/20", eyebrow: "text-blue-300", badge: "border-blue-200 bg-blue-50 text-blue-800", number: "bg-blue-100 text-blue-800", button: "bg-blue-700 hover:bg-blue-800" },
  amber: { glow: "bg-amber-300/20", eyebrow: "text-amber-300", badge: "border-amber-200 bg-amber-50 text-amber-900", number: "bg-amber-100 text-amber-900", button: "bg-amber-600 hover:bg-amber-700" },
};

function InformationPage({ eyebrow, title, intro, sections, highlights = [], notice, primaryAction, secondaryAction, theme = "emerald" }) {
  const colors = themes[theme] || themes.emerald;

  return (
    <section className="overflow-hidden bg-vextro-canvas py-10 sm:py-16">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <header className="relative overflow-hidden rounded-[2rem] bg-vextro-ink px-6 py-12 text-white shadow-xl sm:px-10 sm:py-16 lg:px-16">
          <div className={`absolute -right-16 -top-20 size-72 rounded-full ${colors.glow} blur-3xl`} />
          <div className="relative max-w-4xl">
            <span className={`text-xs font-black uppercase tracking-[0.18em] ${colors.eyebrow}`}>{eyebrow}</span>
            <h1 className="mt-5 text-4xl font-black tracking-[-0.05em] sm:text-5xl lg:text-6xl">{title}</h1>
            <p className="mt-6 max-w-3xl text-base leading-8 text-slate-300 sm:text-lg">{intro}</p>
            {(primaryAction || secondaryAction) ? (
              <div className="mt-8 flex flex-wrap gap-3">
                {primaryAction ? <Link className={`inline-flex min-h-12 items-center rounded-xl px-6 text-sm font-black text-white transition ${colors.button}`} to={primaryAction.to}>{primaryAction.label}<span className="ml-2" aria-hidden="true">→</span></Link> : null}
                {secondaryAction ? <Link className="inline-flex min-h-12 items-center rounded-xl border border-white/20 bg-white/5 px-6 text-sm font-black text-white transition hover:bg-white/10" to={secondaryAction.to}>{secondaryAction.label}</Link> : null}
              </div>
            ) : null}
          </div>
        </header>

        {highlights.length ? (
          <div className="relative z-10 mx-4 -mt-5 grid gap-3 sm:grid-cols-3 lg:mx-10">
            {highlights.map((item) => <div className="rounded-2xl border border-vextro-border bg-white p-5 shadow-lg shadow-slate-200/50" key={item.title}><strong className="text-sm text-vextro-ink">{item.title}</strong><p className="mt-2 text-sm leading-6 text-vextro-muted">{item.description}</p></div>)}
          </div>
        ) : null}

        <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="space-y-4">
            {sections.map((section, index) => (
              <article className="rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-8" id={`section-${index + 1}`} key={section.title}>
                <div className="flex items-start gap-4">
                  <span className={`grid size-10 shrink-0 place-items-center rounded-xl text-sm font-black ${colors.number}`}>{String(index + 1).padStart(2, "0")}</span>
                  <div><h2 className="text-xl font-black tracking-tight text-vextro-ink sm:text-2xl">{section.title}</h2><div className="mt-3 space-y-3 text-sm leading-7 text-vextro-muted sm:text-base">{section.content.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}</div>
                    {section.points?.length ? <ul className="mt-5 grid gap-3 sm:grid-cols-2">{section.points.map((point) => <li className={`rounded-xl border px-4 py-3 text-sm font-bold ${colors.badge}`} key={point}>✓ {point}</li>)}</ul> : null}
                  </div>
                </div>
              </article>
            ))}
          </div>

          <aside className="h-fit rounded-3xl border border-vextro-border bg-white p-6 shadow-sm lg:sticky lg:top-36">
            <strong className="text-sm font-black text-vextro-ink">On this page</strong>
            <nav className="mt-4 grid gap-1" aria-label="Page sections">{sections.map((section, index) => <a className="rounded-lg px-3 py-2 text-sm font-semibold text-vextro-muted hover:bg-vextro-canvas hover:text-vextro-primary" href={`#section-${index + 1}`} key={section.title}>{section.title}</a>)}</nav>
            <div className="my-5 h-px bg-vextro-border" />
            <strong className="text-sm font-black text-vextro-ink">VEXTRO information</strong>
            <nav className="mt-3 grid gap-1 text-sm font-semibold text-vextro-muted" aria-label="VEXTRO information pages">
              <Link className="rounded-lg px-3 py-2 hover:bg-vextro-canvas hover:text-vextro-primary" to="/about">About VEXTRO</Link>
              <Link className="rounded-lg px-3 py-2 hover:bg-vextro-canvas hover:text-vextro-primary" to="/privacy">Privacy policy</Link>
              <Link className="rounded-lg px-3 py-2 hover:bg-vextro-canvas hover:text-vextro-primary" to="/terms">Terms & conditions</Link>
              <Link className="rounded-lg px-3 py-2 hover:bg-vextro-canvas hover:text-vextro-primary" to="/support">Help & support</Link>
            </nav>
          </aside>
        </div>

        {notice ? <div className={`mt-8 rounded-2xl border px-5 py-4 text-sm leading-6 ${colors.badge}`}><strong>{notice.title}</strong> {notice.text}</div> : null}
      </div>
    </section>
  );
}

export default InformationPage;
