// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Note: the /voice/* same-origin proxy to the voice service is implemented as a
  // STREAMING route handler (src/app/voice/[...path]/route.ts), NOT a rewrite.
  // Next's rewrite proxy buffers/times out long-lived SSE responses
  // (BodyTimeoutError), which broke the interview's live transcript stream.
};
module.exports = nextConfig;
