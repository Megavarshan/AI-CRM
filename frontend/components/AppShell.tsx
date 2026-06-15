"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { getSession } from "@/lib/auth";

/** Routes that render full-screen without the sidebar or auth guard. */
const PUBLIC_ROUTES = ["/login", "/welcome"];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_ROUTES.some((r) => pathname.startsWith(r));
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (isPublic) {
      setReady(true);
      return;
    }
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [pathname, isPublic, router]);

  if (isPublic) {
    return (
      <main className="flex-1 overflow-y-auto h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-black">
        {children}
      </main>
    );
  }

  if (!ready) {
    return (
      <main className="flex-1 h-screen flex items-center justify-center bg-gradient-to-b from-slate-950 via-slate-900 to-black">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </main>
    );
  }

  return (
    <>
      <Sidebar />
      <main className="flex-1 overflow-y-auto h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-black">
        {children}
      </main>
    </>
  );
}
