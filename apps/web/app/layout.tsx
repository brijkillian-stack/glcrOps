import type { Metadata, Viewport } from "next";
import { SWRProvider } from "@/components/SWRProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "ZDS Forge",
  description: "Gun Lake Casino Resort — Zone Deployment System",
  applicationName: "ZDS Forge",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "ZDS Forge",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
      </head>
      <body className="bg-[#F5F5F7] min-h-dvh overflow-x-hidden">
        <SWRProvider>{children}</SWRProvider>
      </body>
    </html>
  );
}
