/** The nine report sections, in fixed display + TOC order. */
export const REPORT_SECTIONS = [
  { id: "overview", title: "Company Overview" },
  { id: "products", title: "Products & Services" },
  { id: "customers", title: "Target Customers" },
  { id: "signals", title: "Business Signals" },
  { id: "risks", title: "Risks & Challenges" },
  { id: "questions", title: "Discovery Questions" },
  { id: "outreach", title: "Outreach Strategy" },
  { id: "unknowns", title: "Unknowns" },
  { id: "sources", title: "Sources" },
] as const;

export type ReportSectionId = (typeof REPORT_SECTIONS)[number]["id"];
