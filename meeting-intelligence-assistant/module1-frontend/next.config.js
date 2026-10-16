// Purpose: Next.js configuration.
//
// The browser only ever talks to this Next.js server. Requests to /api/* are
// proxied to the backend (module2), so the backend does not need CORS and the
// backend URL never has to be baked into client code.
//
// BACKEND_URL is read at build time (rewrites are compiled into the build).

/** @type {import('next').NextConfig} */
const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'

const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
