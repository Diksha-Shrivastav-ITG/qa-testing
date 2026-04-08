import { useState, useEffect, useRef } from "react";

const TEST_TYPES = [
  { key: "qa",          label: "QA Test",            desc: "AI-powered visual analysis of your Shopify store", icon: "🔍" },
  { key: "functional",  label: "Functionality Test",  desc: "Cart, checkout, search, mobile menu",              icon: "⚡" },
  { key: "ada",         label: "ADA Test",            desc: "WCAG 2.1 accessibility compliance",                icon: "♿" },
  { key: "seo",         label: "SEO Test",            desc: "GTM, GA4, GSC, Bing, meta tags",                   icon: "🔎" },
  { key: "performance", label: "Performance Test",    desc: "Load time, TTFB, resource size",                   icon: "📊" },
];

interface PageEntry {
  storeUrl: string;
  referenceUrl: string; // only used in design mode
}

interface RunQAModalProps {
  onConfirm: (pages: string, testMode: "design" | "ai", testTypes?: string[], referenceUrls?: string) => void;
  onCancel: () => void;
  isLoading: boolean;
  hasDesignSource?: boolean;
  shopifyUrl?: string;
  referenceUrl?: string; // pre-fills the homepage reference URL in design mode
}

/** Extract a path string from a full URL or a bare path. */
function toPath(input: string): string {
  const s = input.trim();
  if (!s) return "/";
  try {
    return new URL(s).pathname || "/";
  } catch {
    return s.startsWith("/") ? s : `/${s}`;
  }
}

const INPUT_CLS =
  "flex-1 px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm font-mono text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-400 transition-colors";

const RunQAModal = ({
  onConfirm,
  onCancel,
  isLoading,
  hasDesignSource = false,
  shopifyUrl,
  referenceUrl,
}: RunQAModalProps) => {
  // Derive the locked test mode from project config
  const testMode: "design" | "ai" = hasDesignSource ? "design" : "ai";

  // Page entry list — pre-populate with the store homepage and reference URL
  const defaultPage = shopifyUrl?.trim() || "/";
  const defaultRef = testMode === "design" ? (referenceUrl?.trim() || "") : "";
  const [pageEntries, setPageEntries] = useState<PageEntry[]>([
    { storeUrl: defaultPage, referenceUrl: defaultRef },
  ]);

  // Customize tests — all checked by default
  const [showCustomize, setShowCustomize] = useState(false);
  const [selectedTests, setSelectedTests] = useState<Set<string>>(
    () => new Set([...TEST_TYPES.map((t) => t.key), "link_audit"])
  );

  const toggleTest = (key: string) => {
    setSelectedTests((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
        if (key === "qa") next.delete("link_audit");
      } else {
        next.add(key);
        if (key === "qa") next.add("link_audit");
      }
      return next;
    });
  };

  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement;
    dialogRef.current?.focus();
    return () => {
      previousFocusRef.current?.focus();
    };
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      onCancel();
      return;
    }
    if (e.key !== "Tab") return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable || focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus(); }
    } else {
      if (document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };

  const updateStoreUrl = (idx: number, value: string) => {
    setPageEntries((prev) => prev.map((e, i) => (i === idx ? { ...e, storeUrl: value } : e)));
  };

  const updateReferenceUrl = (idx: number, value: string) => {
    setPageEntries((prev) => prev.map((e, i) => (i === idx ? { ...e, referenceUrl: value } : e)));
  };

  const addPage = () => {
    setPageEntries((prev) => [...prev, { storeUrl: "", referenceUrl: "" }]);
  };

  const removePage = (idx: number) => {
    setPageEntries((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleConfirm = () => {
    const paths = pageEntries.map((e) => toPath(e.storeUrl)).filter(Boolean).join(",");
    const tests = selectedTests.size > 0 ? Array.from(selectedTests) : undefined;
    // In design mode, collect per-page reference URLs if any were filled in
    let referenceUrls: string | undefined;
    if (testMode === "design") {
      const refs = pageEntries.map((e) => e.referenceUrl.trim());
      if (refs.some((r) => r !== "")) {
        referenceUrls = refs.join(",");
      }
    }
    onConfirm(paths || "/", testMode, tests, referenceUrls);
  };

  const canStart = !isLoading && pageEntries.some((e) => e.storeUrl.trim() !== "") && selectedTests.size > 0;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className={`bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full space-y-5 p-6 max-h-[90vh] overflow-y-auto border border-gray-200 dark:border-slate-700 focus:outline-none ${testMode === "design" ? "max-w-2xl" : "max-w-md"}`}
      >
        {/* Header */}
        <div>
          <h2 id="modal-title" className="text-lg font-semibold text-gray-900 dark:text-white">
            Start QA Run
          </h2>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-0.5">
            Review pages before starting the run.
          </p>
        </div>

        {/* Locked mode badge */}
        <div className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg border ${
          testMode === "design"
            ? "border-indigo-200 dark:border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/10"
            : "border-violet-200 dark:border-violet-500/30 bg-violet-50 dark:bg-violet-500/10"
        }`}>
          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
            testMode === "design" ? "bg-indigo-500" : "bg-violet-500"
          }`} />
          <div>
            <span className={`text-sm font-semibold ${
              testMode === "design"
                ? "text-indigo-700 dark:text-indigo-300"
                : "text-violet-700 dark:text-violet-300"
            }`}>
              {testMode === "design" ? "Visual Design Comparison" : "AI Testing"}
            </span>
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
              {testMode === "design"
                ? "Compares your store against the reference URL side-by-side."
                : "AI audits your store pages for visual and functional issues."}
            </p>
          </div>
        </div>

        {/* Pages */}
        <div>
          <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wide mb-2">
            Pages to test
          </p>

          {/* Column headers for design mode */}
          {testMode === "design" && (
            <div className="grid grid-cols-2 gap-2 px-1 mb-1">
              <span className="text-[10px] font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wide">Store Page URL</span>
              <span className="text-[10px] font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wide">Reference URL</span>
            </div>
          )}

          <div className="space-y-2">
            {pageEntries.map((entry, idx) => (
              <div key={idx} className={`flex items-center gap-2 ${testMode === "design" ? "grid grid-cols-2" : ""}`}>
                <input
                  type="text"
                  value={entry.storeUrl}
                  onChange={(e) => updateStoreUrl(idx, e.target.value)}
                  placeholder={idx === 0 ? "https://mystore.com  or  /" : "/collections/all"}
                  className={INPUT_CLS}
                />
                {testMode === "design" && (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={entry.referenceUrl}
                      onChange={(e) => updateReferenceUrl(idx, e.target.value)}
                      placeholder="https://reference.com/page"
                      className={INPUT_CLS}
                    />
                    {pageEntries.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removePage(idx)}
                        className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                        title="Remove page"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}
                  </div>
                )}
                {testMode !== "design" && pageEntries.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removePage(idx)}
                    className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                    title="Remove page"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Add Page */}
          <button
            type="button"
            onClick={addPage}
            className="mt-3 flex items-center gap-1.5 text-sm font-medium text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Add Page
          </button>
        </div>

        {/* Customize Tests — collapsible */}
        <div className="border border-gray-200 dark:border-slate-700 rounded-lg overflow-hidden">
          <button
            type="button"
            onClick={() => setShowCustomize((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              Customize Tests
              {selectedTests.size < TEST_TYPES.length + 1 && (
                <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-violet-100 dark:bg-violet-500/20 text-violet-700 dark:text-violet-300">
                  {selectedTests.size} selected
                </span>
              )}
            </span>
            <svg
              className={`w-4 h-4 text-gray-400 transition-transform ${showCustomize ? "rotate-180" : ""}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {showCustomize && (
            <div className="border-t border-gray-200 dark:border-slate-700 px-4 py-3 space-y-2 bg-gray-50/50 dark:bg-slate-800/40">
              {TEST_TYPES.map((t) => (
                <div key={t.key}>
                  <label className={`flex items-start gap-3 cursor-pointer px-3 py-2.5 rounded-lg border transition-colors ${
                    selectedTests.has(t.key)
                      ? "border-violet-400 bg-violet-50/50 dark:bg-violet-500/10 dark:border-violet-400"
                      : "border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-white/5"
                  }`}>
                    <input
                      type="checkbox"
                      checked={selectedTests.has(t.key)}
                      onChange={() => toggleTest(t.key)}
                      className="w-4 h-4 accent-violet-600 rounded mt-0.5"
                    />
                    <div>
                      <div className="text-sm font-medium text-gray-800 dark:text-slate-200">
                        <span aria-hidden="true">{t.icon}</span> {t.label}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">{t.desc}</div>
                    </div>
                  </label>

                  {t.key === "qa" && selectedTests.has("qa") && (
                    <label className={`flex items-start gap-3 cursor-pointer px-3 py-2 rounded-lg border mt-1 ml-6 transition-colors ${
                      selectedTests.has("link_audit")
                        ? "border-violet-300 bg-violet-50/30 dark:bg-violet-500/10 dark:border-violet-400/50"
                        : "border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-white/5"
                    }`}>
                      <input
                        type="checkbox"
                        checked={selectedTests.has("link_audit")}
                        onChange={() => toggleTest("link_audit")}
                        className="w-3.5 h-3.5 accent-violet-600 rounded mt-0.5"
                      />
                      <div>
                        <div className="text-xs font-medium text-gray-700 dark:text-slate-300">
                          🔗 Link &amp; Button Audit
                        </div>
                        <div className="text-[10px] text-gray-400 dark:text-slate-500">Check all links and buttons for broken URLs</div>
                      </div>
                    </label>
                  )}
                </div>
              ))}

              {selectedTests.size === 0 && (
                <div role="alert" className="mt-1 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 rounded-lg px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
                  Select at least one test to run.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-1">
          <button
            onClick={handleConfirm}
            disabled={!canStart}
            className={`flex-1 px-4 py-2.5 text-sm font-medium text-white rounded-lg disabled:opacity-60 transition-colors ${
              testMode === "design"
                ? "bg-indigo-600 hover:bg-indigo-700"
                : "bg-violet-600 hover:bg-violet-700"
            }`}
          >
            {isLoading ? "Starting…" : testMode === "design" ? "Start Design Comparison" : "Start QA Run"}
          </button>
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-slate-300 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

export default RunQAModal;
