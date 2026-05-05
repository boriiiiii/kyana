import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kyana — Dashboard",
  description: "Tableau de bord IA pour la gestion des DMs Instagram",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className="bg-[#0d0d0d] text-white antialiased">{children}</body>
    </html>
  );
}
