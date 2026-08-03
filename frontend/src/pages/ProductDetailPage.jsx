import { Link, useParams } from "react-router-dom";

function ProductDetailPage() {
  const { productId } = useParams();

  return (
    <section className="page-section">
      <div className="container">
        <div className="page-card">
          <span className="eyebrow">Product Details</span>

          <h1>Product #{productId}</h1>

          <p>
            This route will display product information, variants, marketplace
            listings, price comparison and price-history charts.
          </p>

          <Link className="secondary-button inline-button" to="/products">
            Back to Products
          </Link>
        </div>
      </div>
    </section>
  );
}

export default ProductDetailPage;