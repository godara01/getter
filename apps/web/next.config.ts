import type { NextConfig } from "next";

// Static export: the site is plain files on Cloudflare Pages and talks to the
// API from the browser, so hosting costs nothing.
const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default config;
