// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a self-contained server bundle (.next/standalone) so the Docker runtime
  // image can ship just the traced node_modules instead of the full tree.
  output: "standalone",
  // Note: the /voice/* same-origin proxy to the voice service is implemented as a
  // STREAMING route handler (src/app/voice/[...path]/route.ts), NOT a rewrite.
  // Next's rewrite proxy buffers/times out long-lived SSE responses
  // (BodyTimeoutError), which broke the interview's live transcript stream.
};
module.exports = nextConfig;
