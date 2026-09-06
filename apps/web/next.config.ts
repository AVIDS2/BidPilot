import type { NextConfig } from 'next';

// Define the base Next.js configuration
const baseConfig: NextConfig = {
  // The local browser commonly uses 127.0.0.1 while Next binds to localhost.
  // Allow the dev HMR endpoint from both loopback hostnames so client-side
  // navigation can be inspected without a false full-page fallback.
  allowedDevOrigins: ['localhost', '127.0.0.1'],
  output: process.env.BUILD_STANDALONE === 'true' ? 'standalone' : undefined,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'api.slingacademy.com',
        port: ''
      }
    ]
  },
  transpilePackages: ['geist'],
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production'
  }
};

export default baseConfig;
