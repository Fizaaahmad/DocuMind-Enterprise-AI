import { notFound } from "next/navigation";
import { DemoWake } from "../../components/demo-mode";

export default async function Page({ searchParams }: {
  searchParams: Promise<{ next?: string }>;
}) {
  if (process.env.DEMO_MODE !== "true") notFound();
  const { next } = await searchParams;
  const safe = ["/dashboard", "/documents", "/assistant", "/intelligence", "/operations"];
  return <DemoWake next={next && safe.includes(next) ? next : "/dashboard"} />;
}
