import { AppShell } from "@/components/app-shell";
import { AuthProvider } from "@/lib/auth";

export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
