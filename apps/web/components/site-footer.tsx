import Link from "next/link";
import { directory } from "@/lib/directory";
import { formatDate } from "@/lib/format";

export function SiteFooter() {
  return (
    <footer className="border-t border-mist">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-5 py-8 sm:flex-row sm:items-baseline sm:justify-between sm:px-8">
        <div className="flex flex-col gap-1">
          <p className="text-sm text-muted">
            {directory.data_through_label}. Published {formatDate(directory.published_at)}.
          </p>
          <p className="text-xs text-faint">
            Financial data derived from IRS Form 990 filings. Figures lag their fiscal year by 6–18 months.
          </p>
        </div>
        <Link href="/methods" className="text-sm no-underline hover:underline">
          Methods &amp; sources
        </Link>
      </div>
    </footer>
  );
}
