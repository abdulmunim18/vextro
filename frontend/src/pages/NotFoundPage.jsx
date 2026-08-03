import { Link } from "react-router-dom";

function NotFoundPage() {
  return (
    <section className="page-section">
      <div className="container">
        <div className="page-card centered-card">
          <span className="error-code">404</span>
          <h1>Page not found</h1>

          <p>
            The page you are looking for does not exist or may have been moved.
          </p>

          <Link className="primary-button inline-button" to="/">
            Return Home
          </Link>
        </div>
      </div>
    </section>
  );
}

export default NotFoundPage;