import type { Metadata } from "next";
import { Workspace } from "../components/workspace";
import "./globals.css";
export const metadata: Metadata = {
  title: "Кибердайджест — редакция безопасности",
  description:
    "Проверяемый новостной дайджест по кибербезопасности за последние 24 часа.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>
        <Workspace>{children}</Workspace>
      </body>
    </html>
  );
}
