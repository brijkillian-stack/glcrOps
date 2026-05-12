/**
 * /view/today — always redirects to the current published shift.
 *
 * Uses the 90-minute buffer rule: before 8:30 AM the current shift date
 * is yesterday (the shift that started last night).
 *
 * This is a server component so `getShiftDate()` runs at request time
 * with the correct server clock.
 */

import { redirect } from "next/navigation";
import { getShiftDate } from "@/lib/shift-date";

export const dynamic = "force-dynamic"; // never cache — shift date changes each day

export default function ViewTodayPage() {
  const date = getShiftDate();
  redirect(`/view/day/${date}`);
}
