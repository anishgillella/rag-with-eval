/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://rag-with-eval-production.up.railway.app',
  },
  output: 'standalone',
}

module.exports = nextConfig

