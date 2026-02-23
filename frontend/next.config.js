/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_API_URL || 'http://beacon-api:8000'}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
