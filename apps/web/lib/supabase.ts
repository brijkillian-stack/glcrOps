import { createClient, type SupabaseClient } from '@supabase/supabase-js';

/**
 * Lazy Supabase singleton.
 *
 * createClient() is NOT called at module load time — only on first property
 * access. This prevents Next.js build-time prerendering from throwing
 * "supabaseUrl is required" when env vars are absent during `next build`.
 */
let _client: SupabaseClient | null = null;

function getClient(): SupabaseClient {
  if (!_client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !key) {
      throw new Error(
        'NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set'
      );
    }
    _client = createClient(url, key);
  }
  return _client;
}

export const supabase = new Proxy({} as SupabaseClient, {
  get(_, prop: string | symbol) {
    return Reflect.get(getClient(), prop);
  },
});
