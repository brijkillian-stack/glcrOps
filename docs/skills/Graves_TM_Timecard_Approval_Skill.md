# Graves TM Timecard Approval Skill & Knowledge Base

**Purpose:** Recurring protocol for reviewing and approving graves Team Member (TM) timecards in Paycom. Incorporates lessons from the Oct 2026 cycle to reduce friction, redundant checks, and errors.

**Deadline context:** Approvals typically due by noon on Sunday for the period; first check on the 16th. Grave hours stay on the punch-in date.

## Standing Review Checklist (per card)
1. Punches complete? (IN/OUT present and accurate)
2. Codes correct? (or locked by system)
3. Points accurate?
4. Schedule match?
5. Primary supervisor identified?
6. EE self-approval status?
7. Exceptions: needs human real-times confirm vs. external payroll action vs. leave-as-is

## System Locks & Quirks (Paycom)
- Time-off request types cannot be changed post-approval → deny-and-recreate OR leave as-is if hours/points already correct.
- Grave hours remain on the punch-in date (per 10/9 memo).
- Certain missing OUT punches belong to payroll (Rosie) for edit.
- Primary supervisor map:
  - Lincoln Varano → Selner-bell
  - Tara Martin → Marcia Little
  - Others under Director of Operations as applicable.

## Process Rules
- **No redundant pulls:** Once a verified status is <30–60 min old and no new action has occurred, do not re-pull unless deadline is inside the next hour or explicitly requested. Use last verified data.
- **Outlier tracker:** Maintain living list of open payroll actions (person, date, exact punch times needed, owner). Persist across turns until closed.
- **Approved tagging:** Tag any live Paycom edit or approval so status is clear and not re-verified unnecessarily.
- **Hold for confirmation:** Never send emails or force locked changes. Always draft and hold.

## Email Drafting Rules
- Confirm current recipients on the thread before naming anyone.
- Prefer short, precise language matching Director style: “Graves is approved, minus the few TMs we already discussed that still need Payroll to make punch edits.”
- Use “previously discussed TMs” when the thread already knows the list; do not re-list names unnecessarily.
- Apple Mail / Mac setup: no send cards. Always provide body for paste. Never assume send capability.

## Communication & Facilitation Style (C-Suite)
- Own the direction from 1:1 (never “Brian said”).
- Lock after one clear recommendation + evidence.
- Track promised items to close.
- No restating. Tighter stand-up format.
- Hierarchy awareness: avoid incorrect direct messaging patterns (e.g., Docket).

## Example Outliers from Recent Cycle (for reference)
- Carter Campbell 9/24 — OUT ~6:45 AM (payroll)
- Andrew Meeks 9/25 — OUT ~7:00 AM (payroll)
- Silvia Reyes Tolentino 10/8 — IN 10:55 PM / OUT 6:56 AM (payroll)
- Tawnya Elders 9/24: proposed IN 9:00 PM / OUT 6:45 AM + J53 Job Coach (needs real-times confirm)

## Prompt Pattern for Grok Bot
"Review remaining exceptions only. List SUP-approved status. Draft reply-all short. Flag any needing real-times confirm. Update outlier tracker. Do not re-pull verified data."

**Last updated:** 2026-10-11 from process post-mortem.
**Status:** Active skill for Paycom Pro / Grok Bot / Directors.
