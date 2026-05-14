"use client";

export function Header({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <header className="flex items-center justify-between border-b bg-white px-6 py-4">
      <h1 className="text-xl font-semibold">{title}</h1>
      <div>{action}</div>
    </header>
  );
}
