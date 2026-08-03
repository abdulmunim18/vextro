import { Link } from "react-router-dom";
import SystemStatus from "../components/SystemStatus";

function HomePage() {
  return (
    <>
      <section className="hero-section">
        <div className="container hero-grid">
          <div className="hero-content">
            <SystemStatus />
            <span className="eyebrow">
              Ecommerce Intelligence Platform
            </span>

            <h1>
              Compare prices.
              <span> Buy smarter.</span>
            </h1>

            <p className="hero-description">
              Search products across Daraz and PriceOye, compare marketplace
              listings, explore price history and receive alerts when prices
              drop.
            </p>

            <div className="hero-actions">
              <Link className="primary-button" to="/products">
                Explore Products
              </Link>

              <Link className="secondary-button" to="/register">
                Create Free Account
              </Link>
            </div>

            <div className="hero-points">
              <span>✓ Marketplace comparison</span>
              <span>✓ Price-history tracking</span>
              <span>✓ Personalized price alerts</span>
            </div>
          </div>

          <div className="hero-panel">
            <div className="panel-heading">
              <div>
                <span className="panel-label">Best available price</span>
                <h2>Samsung Galaxy A55</h2>
              </div>

              <span className="live-badge">Updated</span>
            </div>

            <div className="price-summary">
              <span>Starting from</span>
              <strong>Rs. 119,999</strong>
            </div>

            <div className="marketplace-list">
              <article className="marketplace-row best-price-row">
                <div>
                  <strong>PriceOye</strong>
                  <span>Official marketplace listing</span>
                </div>

                <div className="marketplace-price">
                  <strong>Rs. 119,999</strong>
                  <span>Best Price</span>
                </div>
              </article>

              <article className="marketplace-row">
                <div>
                  <strong>Daraz</strong>
                  <span>Verified seller listing</span>
                </div>

                <div className="marketplace-price">
                  <strong>Rs. 121,999</strong>
                  <span>In Stock</span>
                </div>
              </article>
            </div>

            <div className="history-preview">
              <div className="history-header">
                <span>30-day price trend</span>
                <strong>-4.8%</strong>
              </div>

              <div className="chart-placeholder">
                <span className="chart-line" />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="feature-section">
        <div className="container">
          <div className="section-heading">
            <span className="eyebrow">Core Features</span>
            <h2>Everything needed for better buying decisions</h2>
          </div>

          <div className="feature-grid">
            <article className="feature-card">
              <span className="feature-number">01</span>
              <h3>Search and compare</h3>
              <p>
                View product listings from multiple marketplaces in one clean
                comparison.
              </p>
            </article>

            <article className="feature-card">
              <span className="feature-number">02</span>
              <h3>Track price history</h3>
              <p>
                Understand whether the current product price is high, low or
                trending downward.
              </p>
            </article>

            <article className="feature-card">
              <span className="feature-number">03</span>
              <h3>Create price alerts</h3>
              <p>
                Set your target price and track when a marketplace listing
                reaches it.
              </p>
            </article>
          </div>
        </div>
      </section>
    </>
  );
}

export default HomePage;