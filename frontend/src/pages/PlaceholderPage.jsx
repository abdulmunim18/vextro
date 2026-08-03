function PlaceholderPage({ eyebrow = "VEXTRO", title, description }) {
  return (
    <section className="page-section">
      <div className="container">
        <div className="page-card">
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>

          <div className="development-status">
            <span className="status-dot" />
            Frontend route working successfully
          </div>
        </div>
      </div>
    </section>
  );
}

export default PlaceholderPage;