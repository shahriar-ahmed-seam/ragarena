import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-20">
      <p className="eyebrow">404</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">
        No such page
      </h1>
      <p className="mt-3 max-w-md text-sm text-muted">
        That run may not have been committed to the repository yet.
      </p>
      <Link
        href="/"
        className="mt-6 inline-block rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-bg transition-opacity hover:opacity-90"
      >
        Back to the leaderboard
      </Link>
    </div>
  );
}
