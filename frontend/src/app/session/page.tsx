"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { refreshSession } from "../../lib/api";

export default function SessionPage() {
  const router = useRouter();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    refreshSession()
      .then(() => {
        if (active) router.replace("/dashboard");
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [router]);
  return (
    <main className="grid min-h-screen place-content-center gap-4 px-6 text-center">
      <h1 className="text-2xl font-semibold">
        {failed ? "Please sign in again" : "Restoring your workspace…"}
      </h1>
      <p className="text-slate-500">
        {failed
          ? "Your session has expired or the service is unavailable."
          : "Securely renewing your session."}
      </p>
      {failed && (
        <Link className="btn-primary" href="/login">
          Go to sign in
        </Link>
      )}
    </main>
  );
}
