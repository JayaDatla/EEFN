import { redirect } from "next/navigation";

// UPGRADE_PLAN.md H.3.1: "Home = the triage queue, not a landing page" -- the triage
// queue now lives at "/" directly. This route is kept only so old links/bookmarks to
// /candidates still land somewhere real.
export default function CandidatesRedirect() {
  redirect("/");
}
