/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Enable build caching optimizations
  experimental: {
    // optimizePackageImports for better caching
    optimizePackageImports: ['@supabase/supabase-js'],
  },
};

export default nextConfig;