export interface Profile {
  readonly network: string;
  readonly url: string;
}

export interface RoleAddress {
  readonly role: "corrections" | "privacy" | "press";
  readonly address: string;
}

interface BrandConfig {
  wordmark: string;
  shortWordmark: string;
  tagline: string;
  profiles: readonly Profile[];
  contact: readonly RoleAddress[];
  licence: { readonly name: string; readonly url: string };
}

export const BRAND_CONFIG: BrandConfig = {
  wordmark: "Machine Vision Radar",
  shortWordmark: "MV radar",
  tagline: "All machine vision knowledge, in one place.",
  profiles: [{ network: "LinkedIn", url: "https://www.linkedin.com/company/machine-vision-radar" }],
  contact: [{ role: "corrections", address: "" }, { role: "privacy", address: "" }, { role: "press", address: "" }],
  licence: { name: "CC BY-NC 4.0", url: "https://creativecommons.org/licenses/by-nc/4.0/" },
};
