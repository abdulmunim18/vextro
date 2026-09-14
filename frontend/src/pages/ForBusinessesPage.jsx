import InformationPage from "../components/InformationPage";

const sections = [
  { title: "Competitor visibility", content: ["Track comparable marketplace offers from a single workspace and spend less time checking product pages manually."], points: ["Structured product catalog", "Comparable marketplace offers", "Current availability signals"] },
  { title: "Pricing decisions", content: ["Use stored price history and transparent signals as decision support for promotions, purchasing and catalogue planning."], points: ["Historical price movement", "Pricing guidance", "No manufactured predictions"] },
  { title: "A workspace that grows with you", content: ["Create an organization, organize business products and use sales and competitor views designed for ecommerce teams in Pakistan."] },
];

function ForBusinessesPage() {
  return <InformationPage eyebrow="VEXTRO for business" title="Sharper market intelligence for growing stores" intro="Turn marketplace listings and your own commercial context into practical ecommerce decisions." sections={sections} highlights={[{ title: "One workspace", description: "Bring product, competitor and pricing views together." }, { title: "Clear provenance", description: "Marketplace sources stay visible throughout comparison." }, { title: "Actionable signals", description: "Focus on decisions, not raw rows of marketplace data." }]} primaryAction={{ label: "Create business account", to: "/register" }} secondaryAction={{ label: "Already a member? Login", to: "/login" }} theme="blue" />;
}

export default ForBusinessesPage;
