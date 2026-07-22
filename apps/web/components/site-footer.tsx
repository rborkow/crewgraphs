import Link from "next/link";
import { getPublishMeta } from "@/lib/directory";
import { formatDate } from "@/lib/format";

/**
 * Async server component: reads the publish metadata (data-through label +
 * publish date) live from the published snapshot. Rendered once in the root
 * layout, so a single lightweight query serves every page's footer.
 */
export async function SiteFooter() {
  const meta = await getPublishMeta();

  return (
    <footer className="border-t border-mist">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-5 py-8 sm:flex-row sm:items-baseline sm:justify-between sm:px-8">
        <div className="flex flex-col gap-1">
          {meta ? (
            <p className="text-sm text-muted">
              {meta.data_through_label}. Published {formatDate(meta.published_at)}.
            </p>
          ) : null}
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
