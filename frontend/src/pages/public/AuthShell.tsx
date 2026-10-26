import type { ReactNode } from "react";

import { Logo } from "../../components/Layout";

export default function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center bg-gradient-to-b from-brand-50 to-slate-50 px-4 py-10">
      <Logo />
      <div className="card mt-8 w-full max-w-md p-6 sm:p-8">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        <p className="mb-6 mt-1 text-sm text-slate-500">{subtitle}</p>
        {children}
      </div>
    </div>
  );
}
