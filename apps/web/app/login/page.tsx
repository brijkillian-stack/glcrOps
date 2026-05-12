"use client";

export const dynamic = 'force-dynamic';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import { setAuthCookies, type UserRole } from '@/lib/auth';

// ── Inner component — uses useSearchParams() ──────────────────────────────────
// Must be wrapped in <Suspense> by the default export (Next.js 15 requirement).

function LoginForm() {
  const [email, setEmail]             = useState('');
  const [password, setPassword]       = useState('');
  const [stayLoggedIn, setStayLoggedIn] = useState(true);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState('');
  const router                        = useRouter();
  const searchParams                  = useSearchParams();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // ── 1. Authenticate ───────────────────────────────────────────────────
      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (authError) throw authError;

      // ── 2. Fetch role from users table ────────────────────────────────────
      let role: UserRole = 'ops_super'; // safe default → restricted access
      try {
        const { data: userData, error: roleError } = await supabase
          .from('users')
          .select('role')
          .eq('id', data.user!.id)
          .single();

        if (!roleError && userData?.role) {
          role = userData.role as UserRole;
        }
      } catch {
        // If the users table lookup fails, default to restricted (safest choice).
        console.warn('[auth] Could not fetch role; defaulting to ops_super');
      }

      // ── 3. Persist auth cookies ───────────────────────────────────────────
      setAuthCookies(role, stayLoggedIn);

      // ── 4. Redirect — honor ?next= set by middleware ──────────────────────
      const next = searchParams.get('next');
      router.push(next && next.startsWith('/') ? next : '/');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-xl shadow">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Sign in to ZDS Forge</h2>
          <p className="mt-2 text-gray-600">Gun Lake Casino Operations</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              checked={stayLoggedIn}
              onChange={(e) => setStayLoggedIn(e.target.checked)}
              className="h-4 w-4 text-blue-600 border-gray-300 rounded"
            />
            <label className="ml-2 text-sm text-gray-700">Stay logged in for 14 days</label>
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div className="text-center">
          <button
            onClick={() => router.push('/login/pin')}
            className="text-blue-600 hover:underline text-sm"
          >
            Sign in with PIN instead
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Page export — Suspense required by Next.js 15 for useSearchParams() ───────

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
