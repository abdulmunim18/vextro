function RouteLoadingState({
  message = "Loading VEXTRO...",
}) {
  return (
    <section
      className="relative grid min-h-[calc(100vh-145px)] place-items-center overflow-hidden bg-vextro-canvas px-4 py-16"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="pointer-events-none absolute -left-32 top-10 size-80 rounded-full bg-blue-300/20 blur-3xl" />

      <div className="pointer-events-none absolute -right-32 bottom-0 size-80 rounded-full bg-violet-300/20 blur-3xl" />

      <div className="relative flex flex-col items-center text-center">
        <div className="relative grid size-20 place-items-center">
          <span className="absolute size-20 animate-ping rounded-full bg-blue-200/60" />

          <span className="absolute size-15 animate-pulse rounded-full bg-blue-100" />

          <span className="relative grid size-12 place-items-center rounded-2xl bg-vextro-primary text-lg font-black text-white shadow-lg shadow-blue-500/25">
            V
          </span>
        </div>

        <h1 className="mt-7 text-xl font-black tracking-tight text-vextro-ink">
          Please wait
        </h1>

        <p className="mt-2 text-sm font-medium text-vextro-muted">
          {message}
        </p>

        <div className="mt-6 flex items-center gap-2">
          {[0, 1, 2].map((item) => (
            <span
              className="size-2 animate-bounce rounded-full bg-vextro-primary"
              key={item}
              style={{
                animationDelay: `${item * 150}ms`,
              }}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

export default RouteLoadingState;