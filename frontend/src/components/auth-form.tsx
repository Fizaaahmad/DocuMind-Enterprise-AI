"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "../lib/api";
import { Brand, Icon } from "./ui";
import { DemoEntry, useDemo } from "./demo-mode";

export function AuthForm({ signup = false }: { signup?: boolean }) {
  const demo = useDemo();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);

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
    <div className="auth-layout">
      <aside className="auth-story">
        <div className="absolute -right-32 top-32 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <Link href="/" className="relative">
          <Brand />
        </Link>
        <div className="relative max-w-md">
          <div className="mb-6 h-1 w-12 bg-indigo-400" />
          <p className="auth-eyebrow">DOCUMENTS → CLARITY → ACTION</p>
          <h2>
            Clarity in every document.
            <br />
            <span>Confidence in every decision.</span>
          </h2>
          <p className="mt-6 leading-7 text-slate-400">
            Bring your organization’s knowledge together. Find answers with
            evidence, uncover what matters, and turn commitments into action.
          </p>
        </div>
        <div className="auth-capabilities">
          <div>
            <Icon name="quote" />
            <span>Answers with source evidence</span>
          </div>
          <div>
            <Icon name="intelligence" />
            <span>Structured insights, ready for review</span>
          </div>
          <div>
            <Icon name="shield" />
            <span>Organization-scoped team access</span>
          </div>
        </div>
      </aside>
      <main className="auth-form-area">
        <div className="w-full max-w-sm">
          <Link
            href="/"
            className="mb-10 block text-xl font-bold tracking-tight text-indigo-600 lg:hidden"
          >
            <Brand />
          </Link>
          <p className="eyebrow">Your secure workspace</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">
            {demo ? "Explore DocuMind" : signup ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mb-8 mt-3 text-sm leading-6 text-slate-500">
            {signup
              ? "Start with your account. Create or join an organization next."
              : "Your documents, insights and team. All in one workspace."}
          </p>
          {demo ? <DemoEntry /> : <form onSubmit={submit} className="space-y-5">
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
            <div className="password-field">
              <label className="field-label" htmlFor="auth-password">
                Password
              </label>
              <input
                id="auth-password"
                className="input"
                type={showPassword ? "text" : "password"}
                name="password"
                autoComplete={signup ? "new-password" : "current-password"}
                minLength={signup ? 12 : 1}
                maxLength={128}
                required
                disabled={pending}
              />
              <button
                type="button"
                className="password-toggle"
                aria-pressed={showPassword}
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? "Hide password" : "Show password"}
              </button>
            </div>
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
              {!pending && <Icon name="arrow" />}
            </button>
          </form>}
          {!demo && <p className="mt-7 text-center text-sm text-slate-500">
            {signup ? "Already have an account? " : "New to DocuMind? "}
            <Link
              className="font-medium text-indigo-600 hover:underline"
              href={signup ? "/login" : "/signup"}
            >
              {signup ? "Sign in" : "Create an account"}
            </Link>
          </p>}
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
