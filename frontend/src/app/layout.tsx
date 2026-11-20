import type { Metadata } from "next";
import "./globals.css";
import "./theme.css";
import { ThemeSelector } from "../components/theme-selector";

// Resolve appearance before paint, without accessing authentication or user data.
const themeScript = `(()=>{let t='system';try{t=localStorage.getItem('documind.theme')||t}catch{}document.documentElement.dataset.theme=t==='dark'||t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'})()`;

export const metadata: Metadata = {
  title: {
    default: "DocuMind | Document Intelligence",
    template: "%s | DocuMind",
  },
  description:
    "Turn documents into grounded answers, structured insights and accountable workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        {children}
        <ThemeSelector />
      </body>
    </html>
  );
}
