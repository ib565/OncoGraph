import type { Metadata } from "next";
import "./globals.css";
import ClientWrapper from "./ClientWrapper";

export const metadata: Metadata = {
  title: "OncoGraph",
  description: "Answers oncology questions using knowledge graph backed citations.",
  icons: {
    icon: "/icon.png",
    apple: "/icon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" style={{ colorScheme: 'dark' }}>
      <body
        style={{
          height: "100%",
          background: "var(--bg-app)",
          color: "var(--text-1)",
          margin: 0,
          fontSmooth: "antialiased",
          WebkitFontSmoothing: "antialiased",
          MozOsxFontSmoothing: "grayscale",
        }}
      >
        <ClientWrapper>
          {children}
        </ClientWrapper>
      </body>
    </html>
  );
}

