/** @type {import('next').NextConfig} */
const nextConfig = {
  reactCompiler: true,
  compiler: {
    removeConsole: process.env.NODE_ENV === "production",
  },
  async redirects() {
    return [
      {
        source: "/",
        destination: "/dashboard/cv-studio",
        permanent: false,
      },
      {
        source: "/dashboard",
        destination: "/dashboard/cv-studio",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
