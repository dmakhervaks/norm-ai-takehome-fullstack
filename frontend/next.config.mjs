/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const backendHost = process.env.BACKEND_HOST || 'localhost';
    const backendPort = process.env.BACKEND_PORT || '8000';
    const target = `http://${backendHost}:${backendPort}`;
    return [
      {
        source: '/api/:path*',
        destination: `${target}/:path*`, // e.g., /api/query -> http://localhost:8000/query
      },
    ];
  },
};

export default nextConfig;
