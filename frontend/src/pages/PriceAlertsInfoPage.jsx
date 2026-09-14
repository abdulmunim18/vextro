import InformationPage from "../components/InformationPage";

const sections = [
  { title: "Choose the right product", content: ["Open a normalized VEXTRO product and review its current marketplace offers before creating an alert."] },
  { title: "Set your target price", content: ["Choose the amount that would make the product worth buying for you. Your target remains connected to the selected product."] },
  { title: "We evaluate fresh prices", content: ["When new marketplace data is ingested, VEXTRO checks eligible alerts against available listing prices."] },
  { title: "Verify before purchasing", content: ["An alert is a decision aid, not a guarantee. Confirm final price, delivery, stock, warranty and seller terms on the marketplace."] },
];

function PriceAlertsInfoPage() {
  return <InformationPage eyebrow="Price alert guide" title="Let the right price come to you" intro="Create a target once and use VEXTRO's latest stored marketplace data to monitor when a product reaches it." sections={sections} highlights={[{ title: "Product-specific", description: "Every alert belongs to a normalized catalog product." }, { title: "Price-aware", description: "Checks use available current marketplace listings." }, { title: "Under your control", description: "Review and manage alerts from your account." }]} notice={{ title: "Important:", text: "Prices and availability can change between collection and checkout. The retailer's checkout page is the final source of truth." }} primaryAction={{ label: "Open price alerts", to: "/alerts" }} secondaryAction={{ label: "Browse products", to: "/products" }} theme="amber" />;
}

export default PriceAlertsInfoPage;
