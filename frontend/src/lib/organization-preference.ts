import type { Organization } from "./types";

// A UI preference only. Membership from the API is always authoritative.
export function preferredOrganization(items: Organization[], initial?: string) {
  let preferred = initial;
  try {
    preferred ??=
      new URL(window.location.href).searchParams.get("organization") ??
      sessionStorage.getItem("documind.organization") ??
      undefined;
  } catch {
    /* Storage may be disabled. */
  }
  return items.find((item) => item.id === preferred)?.id ?? items[0]?.id ?? "";
}
