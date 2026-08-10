import apiClient from "../api/httpClient";

export async function getCategories() {
  const response = await apiClient.get("/categories");
  return response.data;
}

export async function getBrands() {
  const response = await apiClient.get("/brands");
  return response.data;
}

export async function getPlatforms() {
  const response = await apiClient.get("/platforms");
  return response.data;
}

export async function getProducts(params = {}) {
  const response = await apiClient.get("/products", {
    params,
  });

  return response.data;
}

export async function getProductById(productId) {
  const response = await apiClient.get(
    `/products/${productId}`,
  );

  return response.data;
}

export async function getProductListings(productId) {
  const response = await apiClient.get(
    `/products/${productId}/listings`,
  );

  return response.data;
}
export async function getProductPriceHistory(
  productId,
  params = {},
) {
  const response = await apiClient.get(
    `/products/${productId}/price-history`,
    {
      params,
    },
  );

  return response.data;
}
export async function getProductComparison(productIds) {
  const params = new URLSearchParams();

  productIds.forEach((productId) => {
    params.append("product_ids", String(productId));
  });

  const response = await apiClient.get(
    "/products/compare",
    {
      params,
    },
  );

  return response.data;
}