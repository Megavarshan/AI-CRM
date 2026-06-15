/**
 * Supabase browser client — used for Realtime subscriptions in the frontend.
 *
 * NOTE: Only uses the anon key. Service role key stays on the backend only.
 */

import { createBrowserClient } from "@supabase/ssr";

export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

/**
 * Subscribe to live campaign stat updates.
 *
 * Usage:
 *   const unsub = subscribeToCampaign("campaign-uuid", (payload) => { ... });
 *   return () => unsub();
 */
export function subscribeToCampaign(
  campaignId: string,
  onChange: (payload: any) => void
) {
  const channel = supabase
    .channel(`campaign:${campaignId}`)
    .on(
      "postgres_changes",
      {
        event: "UPDATE",
        schema: "public",
        table: "campaigns",
        filter: `id=eq.${campaignId}`,
      },
      onChange
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}
