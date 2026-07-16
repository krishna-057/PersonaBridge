import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "PersonaBridge",
  description: "Personal AI partner console with chat, memory, and approvals."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
