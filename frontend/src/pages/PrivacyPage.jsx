import InformationPage from "../components/InformationPage";

const sections = [
  {
    title: "Information we handle",
    content: [
      "VEXTRO may process account details you provide, saved product preferences, price-alert settings and basic technical information needed to operate and secure the service.",
    ],
  },
  {
    title: "How information is used",
    content: [
      "We use information to provide product comparisons, personalize alerts, maintain account access, improve platform reliability and protect the service from misuse.",
    ],
  },
  {
    title: "Data sharing and retention",
    content: [
      "We do not present personal information for sale. Information may be processed by service providers needed to operate VEXTRO or disclosed when required by applicable law. We retain data only for as long as it is reasonably needed for the purpose it was collected.",
    ],
  },
  {
    title: "Your choices",
    content: [
      "You can update relevant account information and alert preferences from the platform. For privacy questions or requests, contact the VEXTRO team through the contact page.",
    ],
  },
];

function PrivacyPage() {
  return (
    <InformationPage
      eyebrow="Last updated August 24, 2026"
      title="Privacy policy"
      intro="This page explains the types of information VEXTRO may process and the principles used to protect it."
      sections={sections}
    />
  );
}

export default PrivacyPage;
