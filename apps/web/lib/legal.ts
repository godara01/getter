/** The terms text version the API expects. Change it together with GETTER_TERMS_VERSION. */
export const TERMS_VERSION = "practice-terms-draft-v2";

/** Where people send privacy and deletion requests. Set before launch. */
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "";

export function contactText(): string {
  return CONTACT_EMAIL
    ? CONTACT_EMAIL
    : "the contact address that will be published here before launch";
}
