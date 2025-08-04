// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for Node.js server deployment
  output: 'standalone',
  // Disable image optimization if needed
  images: {
    unoptimized: true,
  },
  // Add async/await transpilation for streaming support
  webpack: (config) => {
    config.experiments = {
      ...config.experiments,
      topLevelAwait: true,
    };
    return config;
  },
};

export default nextConfig;
