import InformationPage from "../components/InformationPage";

const sections = [
  {
    title: "What VEXTRO does",
    content: [
      "VEXTRO organizes product and marketplace listings into a normalized catalog so equivalent offers can be compared clearly.",
      "Consumers can review prices and product information, while SMEs can use pricing and competitor intelligence to make more informed ecommerce decisions.",
    ],
  },
  {
    title: "Why we built it",
    content: [
      "Online prices are scattered across marketplaces, product names are inconsistent and the lowest visible price is not always the clearest deal. VEXTRO is designed to make that information easier to understand.",
    ],
  },
  {
    title: "Our approach",
    content: [
      "We focus on transparent comparisons, normalized data and useful price signals. Marketplace availability and prices may change, so VEXTRO presents the latest information available from connected sources and directs users to the retailer for final purchase details.",
    ],
  },
];

function AboutPage() {
  return (
    <InformationPage
      eyebrow="Our story"
      title="Smarter ecommerce decisions for Pakistan"
      intro="VEXTRO is a price comparison and ecommerce intelligence platform built to turn scattered marketplace data into clear, useful decisions."
      sections={sections}
    />
  );
}

export default AboutPage;
