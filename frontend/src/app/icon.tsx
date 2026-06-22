import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: "linear-gradient(135deg, #1C99BF 0%, #0B7A99 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          fontSize: 22,
          fontWeight: 900,
          fontFamily: "Arial Black, Arial, sans-serif",
          letterSpacing: "-1px",
        }}
      >
        O
      </div>
    ),
    { ...size }
  );
}
