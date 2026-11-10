"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "../lib/api";

export function AuthForm({ signup = false }: { signup?: boolean }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const data = new FormData(event.currentTarget);
    setError("");
    setPending(true);
    try {
      await api(`/auth/${signup ? "register" : "login"}`, {
        method: "POST",
        body: JSON.stringify({
          email: data.get("email"),
          password: data.get("password"),
          ...(signup ? { name: data.get("name") } : {}),
        }),
      });
      router.replace("/dashboard");
      router.refresh();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to sign in. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <aside className="relative hidden w-[42%] flex-col justify-between overflow-hidden bg-slate-950 p-12 text-white lg:flex">
        <div className="absolute -right-32 top-32 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <Link href="/" className="relative text-2xl font-bold tracking-tight">
          DocuMind<span className="text-indigo-400">.</span>
        </Link>
        <div className="relative max-w-md">
          <div className="mb-6 h-1 w-12 bg-indigo-400" />
          <p className="text-4xl font-semibold leading-tight tracking-tight">
            One workspace.
            <br />
            The right people.
            <br />A stronger foundation.
          </p>
          <p className="mt-6 leading-7 text-slate-400">
            Bring your teams together with secure access and clear organization
            boundaries.
          </p>
        </div>
        <p className="relative text-xs text-slate-500">
          DOCUMENT INTELLIGENCE · BUILT FOR TEAMS
        </p>
      </aside>
      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <Link
            href="/"
            className="mb-10 block text-xl font-bold tracking-tight text-indigo-600 lg:hidden"
          >
            DocuMind.
          </Link>
          <p className="eyebrow">Your secure workspace</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">
            {signup ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mb-8 mt-3 text-sm leading-6 text-slate-500">
            {signup
              ? "Start with your account. Create or join an organization next."
              : "Sign in to manage your organizations and team."}
          </p>
          <form onSubmit={submit} className="space-y-5">
            {signup && (
              <label className="field-label">
                Full name
                <input
                  className="input"
                  name="name"
                  autoComplete="name"
                  maxLength={100}
                  required
                  disabled={pending}
                />
              </label>
            )}
            <label className="field-label">
              Email address
              <input
                className="input"
                type="email"
                name="email"
                autoComplete="email"
                maxLength={254}
                required
                disabled={pending}
              />
            </label>
            <label className="field-label">
              Password
              <input
                className="input"
                type="password"
                name="password"
                autoComplete={signup ? "new-password" : "current-password"}
                minLength={signup ? 12 : 1}
                maxLength={128}
                required
                disabled={pending}
              />
            </label>
            {signup && (
              <p className="text-xs leading-5 text-slate-500">
                Use 12–128 characters. A long, unique passphrase works well.
              </p>
            )}
            {error && (
              <p role="alert" className="error-box">
                {error}
              </p>
            )}
            <button className="btn-primary w-full" disabled={pending}>
              {pending ? "Please wait…" : signup ? "Create account" : "Sign in"}
            </button>
          </form>
          <p className="mt-7 text-center text-sm text-slate-500">
            {signup ? "Already have an account? " : "New to DocuMind? "}
            <Link
              className="font-medium text-indigo-600 hover:underline"
              href={signup ? "/login" : "/signup"}
            >
              {signup ? "Sign in" : "Create an account"}
            </Link>
          </p>
          <Link
            href="/"
            className="mt-10 block text-center text-xs text-slate-400 hover:text-slate-600"
          >
            View system status
          </Link>
        </div>
      </main>
    </div>
  );
}
