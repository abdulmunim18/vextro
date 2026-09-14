function ContactPage() {
  return (
    <section className="bg-vextro-canvas py-12 sm:py-16">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="grid overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm lg:grid-cols-[0.9fr_1.1fr]">
          <div className="bg-vextro-ink p-7 text-white sm:p-10 lg:p-12">
            <span className="text-xs font-black uppercase tracking-[0.14em] text-emerald-300">Contact VEXTRO</span>
            <h1 className="mt-4 text-4xl font-black tracking-[-0.045em] sm:text-5xl">How can we help?</h1>
            <p className="mt-5 max-w-lg leading-8 text-slate-300">Reach out about product data, price alerts, business intelligence or general platform feedback.</p>

            <div className="mt-10 grid gap-4">
              <a className="rounded-2xl border border-white/15 bg-white/5 p-5 transition hover:bg-white/10" href="mailto:support@vextro.pk">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-300">Email</span>
                <strong className="mt-2 block">support@vextro.pk</strong>
              </a>
              <div className="rounded-2xl border border-white/15 bg-white/5 p-5">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-300">Response time</span>
                <strong className="mt-2 block">Usually within 1–2 business days</strong>
              </div>
            </div>
          </div>

          <div className="p-7 sm:p-10 lg:p-12">
            <span className="text-xs font-black uppercase tracking-[0.14em] text-vextro-primary">Send a message</span>
            <h2 className="mt-3 text-2xl font-black tracking-tight text-vextro-ink">Tell us what you need</h2>
            <p className="mt-3 text-sm leading-7 text-vextro-muted">Email us directly and include the product, marketplace or account area related to your question.</p>

            <div className="mt-8 space-y-4">
              {[
                ["Product & price data", "Report an incorrect listing, price or availability status."],
                ["Account & alerts", "Get help with sign-in, saved products or price alerts."],
                ["Business enquiries", "Discuss SME tools, competitor tracking and pricing intelligence."],
              ].map(([title, description]) => (
                <div key={title} className="rounded-2xl border border-vextro-border p-5">
                  <strong className="text-sm text-vextro-ink">{title}</strong>
                  <p className="mt-2 text-sm leading-6 text-vextro-muted">{description}</p>
                </div>
              ))}
            </div>

            <a className="mt-7 inline-flex min-h-12 items-center justify-center rounded-xl bg-vextro-primary px-6 text-sm font-black text-white hover:bg-vextro-primary-dark" href="mailto:support@vextro.pk?subject=VEXTRO%20support%20request">Open email app</a>
          </div>
        </div>
      </div>
    </section>
  );
}

export default ContactPage;
