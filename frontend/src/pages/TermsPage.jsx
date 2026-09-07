import InformationPage from "../components/InformationPage";

const sections = [
  {
    title: "Using VEXTRO",
    content: [
      "You may use VEXTRO for lawful product research, price comparison and ecommerce intelligence. You are responsible for keeping your account credentials secure and for activity performed through your account.",
    ],
  },
  {
    title: "Prices and marketplace information",
    content: [
      "Prices, stock, delivery, seller details and promotions can change after they are collected. Always confirm the final price and purchase terms on the retailer's website before completing a transaction.",
    ],
  },
  {
    title: "Acceptable use",
    content: [
      "You must not attempt to disrupt the service, access another user's account, misuse automated interfaces or use VEXTRO in a way that violates applicable law or third-party rights.",
    ],
  },
  {
    title: "Service availability",
    content: [
      "Features may change as VEXTRO improves. We aim to keep the platform available and accurate, but uninterrupted operation or complete marketplace coverage cannot be guaranteed.",
    ],
  },
];

function TermsPage() {
  return (
    <InformationPage
      eyebrow="Last updated August 24, 2026"
      title="Terms and conditions"
      intro="These terms describe the basic rules for accessing and using the VEXTRO platform."
      sections={sections}
    />
  );
}

export default TermsPage;
