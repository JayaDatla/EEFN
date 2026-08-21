// The "API Explorer" nav entry and "/showcase" ("Research Analytics") used to be
// two independently-maintained 615-line copies of the exact same conference/outreach
// deck, differing only in the exported component's name -- a real dead-code-drift
// bug (found during a full-page sweep), not an intentional two-track demo. Neither
// page's content actually matches either nav label ("API Explorer" / "Research
// Analytics"); building real distinct content for each is separate follow-up work,
// not attempted here. This file now re-exports the single canonical implementation
// so there is one source of truth instead of two copies that can silently diverge.
export { default } from "../showcase/page";
