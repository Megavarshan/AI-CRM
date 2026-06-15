"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getSession } from "@/lib/auth";

/** Root page — route based on session: login if signed out, welcome if signed in. */
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getSession() ? "/welcome" : "/login");
  }, [router]);

  return null;
}
