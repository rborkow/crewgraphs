import Link from "next/link";

const NAV = [
  { href: "/", label: "Directory" },
  { href: "/compare", label: "Compare" },
  { href: "/methods", label: "Methods" }
];

export function SiteHeader() {
  return (
    <header className="border-b border-mist">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-5 py-4 sm:px-8">
        <Link href="/" className="wordmark text-lg text-river no-underline">
          CrewGraphs
        </Link>
        <nav aria-label="Primary">
          <ul className="flex items-center gap-5 text-sm">
            {NAV.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="text-muted no-underline transition-colors hover:text-river"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
