import type { RoleAddress } from "../../ui/theme/brand.ts";
import type { MessageKey } from "./messages.ts";

export const ROLE_LABELS: Readonly<Record<RoleAddress["role"], MessageKey>> = { corrections: "contactCorrections",
  privacy: "contactPrivacy", press: "contactPress" };
