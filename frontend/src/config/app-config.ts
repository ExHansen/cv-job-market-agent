import packageJson from "../../package.json";

const currentYear = new Date().getFullYear();

export const APP_CONFIG = {
  name: "CareerOS Studio",
  url: "http://localhost:3000",
  repository: "https://github.com/ExHansen/cv-job-market-agent",
  version: packageJson.version,
  copyright: `© ${currentYear}, CareerOS — CV & Job Market AI Agent.`,
  meta: {
    title: "CareerOS Studio — Local AI CV & Job Market Intelligence Agent",
    description:
      "Local-first AI Agent for Company Intelligence, Job Market Skill Analytics, Anti-Hallucination CV Auditing, and ATS-Friendly PDF Generation.",
  },
};
