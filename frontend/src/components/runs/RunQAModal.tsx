import { useState, useEffect, useRef } from "react";
import type { PageConfig } from "../../api/runs";

interface PageEntry {
  label: string;
  enabled: boolean;
  mode: "ai" | "design";
  shopifyUrl: string;
  referenceUrl: string;
}

const DEFAULT_PAGES: PageEntry[] = [
  { label: "Homepage", enabled: true, mode: "ai", shopifyUrl: "/", referenceUrl: "" },
  { label: "Collection Pages", enabled: false, mode: "ai", shopifyUrl: "", referenceUrl: "" },
  { label: "Product Pages", enabled: false, mode: "ai", shopifyUrl: "", referenceUrl: "" },
  { label: "Other Pages", enabled: false, mode: "ai", shopifyUrl: "", referenceUrl: "" },
];

const TEST_TYPES = [
  { key: "qa", label: "QA Test", desc: "Visual AI analysis & design comparison", icon: "\u{1F50D}" },
  { key: "functional", label: "Functionality Test", desc: "Cart, checkout, search, mobile menu", icon: "\u26A1" },
  { key: "ada", label: "ADA Test", desc: "WCAG 2.1 accessibility compliance", icon: "\u267F" },
  { key: "seo", label: "SEO Test", desc: "GTM, GA4, GSC, Bing, meta tags", icon: "\u{1F50E}" },
  { key: "performance", label: "Performance Test", desc: "Load time, TTFB, resource size", icon: "\u{1F4CA}" },
];

interface RunQAModalProps {
  onConfirm: (
    pageConfigs: PageConfig[] | undefined,
    testMode: "design" | "ai",
    testTypes?: string[],
    pages?: string,
  ) => void;
  onCancel: () => void;
  isLoading: boolean;
  sourceType: string;
}

/** Parse a URL string (which may contain multiple lines) into path(s) */
function parseUrls(url: string): string[] {
  const paths: string[] = [];
  // Split by newlines to handle textarea multi-line input
  const lines = url.split(/\n/).map((l) => l.trim()).filter(Boolean);
  for (const line of lines) {
    try {
      const parsed = new URL(line);
      paths.push(parsed.pathname);
    } catch {
      paths.push(line.startsWith("/") ? line : `/${line}`);
    }
  }
  return paths;
}

/** Collect page paths from the pages array (used for Full QA tab) */
function collectPagePaths(fullQA: boolean, pages: PageEntry[]): string {
  if (fullQA) return "";
  const allPaths: string[] = [];
  for (const page of pages) {
    if (!page.enabled) continue;
    const url = page.shopifyUrl.trim();
    if (!url) {
      if (page.label === "Homepage") allPaths.push("/");
      else if (page.label === "Collection Pages") allPaths.push("/collections");
      else if (page.label === "Product Pages") allPaths.push("/products");
      else allPaths.push("__other__");
    } else {
      allPaths.push(...parseUrls(url));
    }
  }
  return allPaths.join(",");
}

const RunQAModal = ({ onConfirm, onCancel, isLoading, sourceType }: RunQAModalProps) => {
  const isAIProject = sourceType === "none";
  const [modalTab, setModalTab] = useState<"full" | "customize">("full");
  // Non-AI projects can't use "all discovered pages", so default to specific pages
  const [fullQA, setFullQA] = useState(isAIProject);
  const [pages, setPages] = useState<PageEntry[]>(DEFAULT_PAGES);
  // link_audit is included by default and coupled to "qa"
  const [selectedTests, setSelectedTests] = useState<Set<string>>(
    () => new Set([...TEST_TYPES.map((t) => t.key), "link_audit"])
  );

  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Move focus into the modal on mount and restore on unmount
  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement;
    dialogRef.current?.focus();
    return () => {
      previousFocusRef.current?.focus();
    };
  }, []);

  // Trap focus within the modal
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      onCancel();
      return;
    }
    if (e.key !== "Tab") return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable || focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };

  const togglePage = (idx: number) => {
    setFullQA(false);
    setPages((prev) => prev.map((p, i) => (i === idx ? { ...p, enabled: !p.enabled } : p)));
  };

  const updatePageField = (idx: number, field: keyof PageEntry, value: string) => {
    setPages((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, [field]: value } : p))
    );
  };

  const setPageMode = (idx: number, mode: "ai" | "design") => {
    setPages((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, mode } : p))
    );
  };

  const handleFullQA = () => {
    setFullQA(true);
    setPages(DEFAULT_PAGES);
  };

  const toggleTestType = (key: string) => {
    setSelectedTests((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
        // Unchecking QA Test also removes Link & Button Audit
        if (key === "qa") next.delete("link_audit");
      } else {
        next.add(key);
        // Checking QA Test also adds Link & Button Audit
        if (key === "qa") next.add("link_audit");
      }
      return next;
    });
  };

  const handleConfirm = () => {
    // Test mode is determined by project source type
    const projectTestMode: "design" | "ai" = isAIProject ? "ai" : "design";

    if (modalTab === "full") {
      // Full QA: use legacy path — send pages + global test mode
      const pageArg = collectPagePaths(fullQA, pages);
      onConfirm(undefined, projectTestMode, undefined, pageArg);
    } else {
      // Customize: build per-page configs — expand multi-line URLs into separate configs
      const configs: PageConfig[] = [];
      for (const p of pages) {
        if (!p.enabled) continue;
        const mode = isAIProject ? "ai" as const : p.mode;
        const rawUrl = p.shopifyUrl.trim();
        // For Homepage or single-line URLs, create one config
        if (p.label === "Homepage" || !rawUrl.includes("\n")) {
          configs.push({
            label: p.label,
            mode,
            shopifyUrl: rawUrl || (p.label === "Homepage" ? "/" : ""),
            referenceUrl: !isAIProject && p.mode === "design" ? p.referenceUrl : undefined,
          });
        } else {
          // Multi-line: create one config per URL
          const urls = rawUrl.split(/\n/).map((l) => l.trim()).filter(Boolean);
          for (const url of urls) {
            configs.push({
              label: p.label,
              mode,
              shopifyUrl: url,
              referenceUrl: !isAIProject && p.mode === "design" ? p.referenceUrl : undefined,
            });
          }
        }
      }
      onConfirm(configs, projectTestMode, Array.from(selectedTests));
    }
  };

  const hasValidPages = fullQA || pages.some((p) => p.enabled);
  const canStart = !isLoading && hasValidPages && (modalTab === "full" || selectedTests.size > 0);

  /** Shared page selection UI used in both tabs */
  const renderPageSelector = (showModeSelector: boolean) => (
    <>
      {/* Full QA all discovered pages — only for AI testing projects */}
      {isAIProject && (
        <label
          className={`flex items-center gap-3 cursor-pointer px-3 py-2.5 rounded-lg border transition-colors ${
            fullQA
              ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 dark:border-indigo-400"
              : "border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-white/5"
          }`}
        >
          <input
            type="radio"
            checked={fullQA}
            onChange={handleFullQA}
            className="w-4 h-4 accent-indigo-600"
          />
          <div>
            <span className="text-sm font-medium text-gray-800 dark:text-slate-200">Full QA — all discovered pages</span>
            <p className="text-xs text-gray-400 dark:text-slate-500">Automatically discovers and tests all pages</p>
          </div>
        </label>
      )}

      <div>
        <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wide mb-2">
          {isAIProject ? "Or select specific pages" : "Select pages"}
        </p>
        <div className="space-y-2">
          {pages.map((page, idx) => (
            <div
              key={idx}
              className={`rounded-lg border transition-colors ${
                !fullQA && page.enabled
                  ? "border-indigo-400 bg-indigo-50/50 dark:bg-indigo-500/10 dark:border-indigo-400"
                  : "border-gray-200 dark:border-slate-700"
              }`}
            >
              <label className="flex items-center gap-3 cursor-pointer px-3 py-2.5">
                <input
                  type="checkbox"
                  checked={!fullQA && page.enabled}
                  onChange={() => togglePage(idx)}
                  className="w-4 h-4 accent-indigo-600 rounded"
                />
                <span className="text-sm font-medium text-gray-700 dark:text-slate-300">{page.label}</span>
              </label>
              {!fullQA && page.enabled && (
                <div className="px-3 pb-3 space-y-3">
                  {/* Mode selector — only in Customize tab, hidden for AI-only projects */}
                  {showModeSelector && !isAIProject && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 dark:text-slate-400 mb-1.5">Testing mode</p>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setPageMode(idx, "ai")}
                          className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                            page.mode === "ai"
                              ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400 dark:border-indigo-400"
                              : "border-gray-200 text-gray-500 dark:border-slate-600 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-white/5"
                          }`}
                        >
                          <span aria-hidden="true">{"\u{1F916}"}</span> AI Check
                        </button>
                        <button
                          type="button"
                          onClick={() => setPageMode(idx, "design")}
                          className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                            page.mode === "design"
                              ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400 dark:border-indigo-400"
                              : "border-gray-200 text-gray-500 dark:border-slate-600 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-white/5"
                          }`}
                        >
                          <span aria-hidden="true">{"\u{1F3A8}"}</span> Design Comparison
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Shopify URL input */}
                  <div>
                    <label htmlFor={`shopify-url-${idx}`} className="text-xs font-medium text-gray-500 dark:text-slate-400">
                      Shopify URL{page.label !== "Homepage" ? "s (one per line)" : ""}
                    </label>
                    {page.label === "Homepage" ? (
                      <input
                        id={`shopify-url-${idx}`}
                        type="url"
                        value={page.shopifyUrl}
                        onChange={(e) => updatePageField(idx, "shopifyUrl", e.target.value)}
                        placeholder="/ (default)"
                        className="mt-1 w-full px-2.5 py-1.5 border border-gray-200 dark:border-slate-600 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-200 placeholder-gray-400 dark:placeholder-slate-500"
                      />
                    ) : (
                      <textarea
                        id={`shopify-url-${idx}`}
                        value={page.shopifyUrl}
                        onChange={(e) => updatePageField(idx, "shopifyUrl", e.target.value)}
                        placeholder={
                          page.label === "Collection Pages"
                            ? "https://store.com/collections/summer\nhttps://store.com/collections/winter"
                            : page.label === "Product Pages"
                            ? "https://store.com/products/boot-1\nhttps://store.com/products/sneaker-2"
                            : "https://store.com/pages/about\nhttps://store.com/pages/contact"
                        }
                        rows={3}
                        className="mt-1 w-full px-2.5 py-1.5 border border-gray-200 dark:border-slate-600 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-200 placeholder-gray-400 dark:placeholder-slate-500 resize-y"
                      />
                    )}
                  </div>

                  {/* Reference URL input — only for Design Comparison mode, hidden for AI projects */}
                  {showModeSelector && !isAIProject && page.mode === "design" && (
                    <div>
                      <label htmlFor={`ref-url-${idx}`} className="text-xs font-medium text-gray-500 dark:text-slate-400">
                        Reference URL <span className="text-gray-400 dark:text-slate-500">(Vercel, staging, HTML — any URL)</span>
                      </label>
                      <input
                        id={`ref-url-${idx}`}
                        type="url"
                        value={page.referenceUrl}
                        onChange={(e) => updatePageField(idx, "referenceUrl", e.target.value)}
                        placeholder="https://my-preview.vercel.app/collections"
                        className="mt-1 w-full px-2.5 py-1.5 border border-gray-200 dark:border-slate-600 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-200 placeholder-gray-400 dark:placeholder-slate-500"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </>
  );

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full max-w-lg space-y-4 p-6 max-h-[90vh] overflow-y-auto border border-gray-200 dark:border-slate-700 focus:outline-none"
      >
        <div>
          <h2 id="modal-title" className="text-lg font-semibold text-gray-900 dark:text-white">Start QA Run</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-0.5">Select pages and test scope.</p>
        </div>

        {/* Full QA | Customize tab bar */}
        <div role="tablist" aria-label="Test scope" className="flex border border-gray-200 dark:border-slate-700 rounded-lg overflow-hidden">
          <button
            type="button"
            role="tab"
            id="tab-full"
            aria-selected={modalTab === "full"}
            aria-controls="panel-full"
            onClick={() => setModalTab("full")}
            className={`flex-1 py-2 text-sm font-semibold transition-colors ${
              modalTab === "full"
                ? "bg-indigo-600 text-white"
                : "bg-gray-50 dark:bg-slate-800 text-gray-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-700"
            }`}
          >
            <span aria-hidden="true">{"\u26A1"}</span> Full QA
          </button>
          <button
            type="button"
            role="tab"
            id="tab-customize"
            aria-selected={modalTab === "customize"}
            aria-controls="panel-customize"
            onClick={() => setModalTab("customize")}
            className={`flex-1 py-2 text-sm font-semibold border-l border-gray-200 dark:border-slate-700 transition-colors ${
              modalTab === "customize"
                ? "bg-indigo-600 text-white"
                : "bg-gray-50 dark:bg-slate-800 text-gray-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-700"
            }`}
          >
            <span aria-hidden="true">{"\u2699\uFE0F"}</span> Customize
          </button>
        </div>

        {/* -- FULL QA TAB -- */}
        <div
          role="tabpanel"
          id="panel-full"
          aria-labelledby="tab-full"
          hidden={modalTab !== "full"}
          className="space-y-4"
        >
          {renderPageSelector(true)}
          <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20 rounded-lg px-3 py-2 text-xs text-blue-700 dark:text-blue-400">
            <strong>Always included:</strong> ADA compliance, link &amp; button audit, functional tests.
            QA runs in background — you can navigate away safely.
          </div>
        </div>

        {/* -- CUSTOMIZE TAB -- */}
        <div
          role="tabpanel"
          id="panel-customize"
          aria-labelledby="tab-customize"
          hidden={modalTab !== "customize"}
          className="space-y-4"
        >
          {/* 1. SELECT TESTS TO RUN */}
          <div>
            <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wide mb-2">
              Select tests to run
            </p>
            <div className="space-y-2">
              {TEST_TYPES.map((t) => (
                <div key={t.key}>
                  <label
                    className={`flex items-start gap-3 cursor-pointer px-3 py-2.5 rounded-lg border transition-colors ${
                      selectedTests.has(t.key)
                        ? "border-indigo-400 bg-indigo-50/50 dark:bg-indigo-500/10 dark:border-indigo-400"
                        : "border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-white/5"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedTests.has(t.key)}
                      onChange={() => toggleTestType(t.key)}
                      className="w-4 h-4 accent-indigo-600 rounded mt-0.5"
                    />
                    <div>
                      <div className="text-sm font-medium text-gray-800 dark:text-slate-200">
                        <span aria-hidden="true">{t.icon}</span> {t.label}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">{t.desc}</div>
                    </div>
                  </label>

                  {/* Link & Button Audit sub-item */}
                  {t.key === "qa" && selectedTests.has("qa") && (
                    <label
                      className={`flex items-start gap-3 cursor-pointer px-3 py-2 rounded-lg border mt-1 ml-6 transition-colors ${
                        selectedTests.has("link_audit")
                          ? "border-indigo-300 bg-indigo-50/30 dark:bg-indigo-500/10 dark:border-indigo-400/50"
                          : "border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-white/5"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedTests.has("link_audit")}
                        onChange={() => toggleTestType("link_audit")}
                        className="w-3.5 h-3.5 accent-indigo-600 rounded mt-0.5"
                      />
                      <div>
                        <div className="text-xs font-medium text-gray-700 dark:text-slate-300">
                          <span aria-hidden="true">{"\u{1F517}"}</span> Link &amp; Button Audit
                        </div>
                        <div className="text-[10px] text-gray-400 dark:text-slate-500">Check all links and buttons for broken URLs and accessibility issues</div>
                      </div>
                    </label>
                  )}
                </div>
              ))}
            </div>
            {selectedTests.size === 0 && (
              <div role="alert" className="mt-2 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 rounded-lg px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
                Select at least one test to run.
              </div>
            )}
          </div>

          {/* 2. SELECT PAGES — with per-page mode selector */}
          <div>
            <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wide mb-2">
              Select pages
            </p>
            {renderPageSelector(true)}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-1">
          <button
            onClick={handleConfirm}
            disabled={!canStart}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
          >
            {isLoading
              ? "Starting..."
              : modalTab === "customize"
              ? <><span aria-hidden="true">{"\u2699\uFE0F"}</span> Run Selected Tests</>
              : <><span aria-hidden="true">{"\u{1F680}"}</span> Start QA Run</>}
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
