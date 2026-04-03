import { useState, useEffect, useRef } from "react";

interface PageEntry {
  label: string;
  enabled: boolean;
  urls: string;
  pageMode: "design" | "ai";
  referenceUrl: string;
}

const DEFAULT_PAGES: PageEntry[] = [
  { label: "Homepage", enabled: true, urls: "/", pageMode: "design", referenceUrl: "" },
  { label: "Collection Pages", enabled: false, urls: "", pageMode: "design", referenceUrl: "" },
  { label: "Product Pages", enabled: false, urls: "", pageMode: "design", referenceUrl: "" },
  { label: "Other Pages", enabled: false, urls: "", pageMode: "design", referenceUrl: "" },
];

const TEST_MODES = [
  {
    value: "design",
    label: "Design Comparison",
    desc: "Compare against your reference site for visual differences",
    icon: "🎨",
  },
  {
    value: "ai",
    label: "AI Analysis Only",
    desc: "AI reviews the site for UX, layout, and quality — no design reference needed",
    icon: "🤖",
  },
];

const TEST_TYPES = [
  { key: "qa", label: "QA Test", desc: "Visual AI analysis & design comparison", icon: "🔍" },
  { key: "functional", label: "Functionality Test", desc: "Cart, checkout, search, mobile menu", icon: "⚡" },
  { key: "ada", label: "ADA Test", desc: "WCAG 2.1 accessibility compliance", icon: "♿" },
  { key: "seo", label: "SEO Test", desc: "GTM, GA4, GSC, Bing, meta tags", icon: "🔎" },
  { key: "performance", label: "Performance Test", desc: "Load time, TTFB, resource size", icon: "📊" },
];

interface RunQAModalProps {
  onConfirm: (pages: string, testMode: "design" | "ai", testTypes?: string[]) => void;
  onCancel: () => void;
  isLoading: boolean;
  hasDesignSource?: boolean;
}

/** Collect page paths from the pages array (shared logic for both tabs) */
function collectPagePaths(fullQA: boolean, pages: PageEntry[]): string {
  if (fullQA) return "";
  const allPaths: string[] = [];
  for (const page of pages) {
    if (!page.enabled) continue;
    const lines = page.urls.split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) {
      if (page.label === "Homepage") allPaths.push("/");
      else if (page.label === "Collection Pages") allPaths.push("/collections");
      else if (page.label === "Product Pages") allPaths.push("/products");
      else allPaths.push("__other__");
    } else {
      for (const line of lines) {
        try {
          const parsed = new URL(line);
          allPaths.push(parsed.pathname);
        } catch {
          allPaths.push(line.startsWith("/") ? line : `/${line}`);
        }
      }
    }
  }
  return allPaths.join(",");
}

const RunQAModal = ({ onConfirm, onCancel, isLoading, hasDesignSource = false }: RunQAModalProps) => {
  const [modalTab, setModalTab] = useState<"full" | "customize">("full");
  const [fullQA, setFullQA] = useState(true);
  const [pages, setPages] = useState<PageEntry[]>(DEFAULT_PAGES);
  const [testMode, setTestMode] = useState<"design" | "ai">(hasDesignSource ? "design" : "ai");
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

  const updateUrls = (idx: number, value: string) => {
    setPages((prev) => prev.map((p, i) => (i === idx ? { ...p, urls: value } : p)));
  };

  const togglePageMode = (idx: number, mode: "design" | "ai") => {
    setPages((prev) => prev.map((p, i) => (i === idx ? { ...p, pageMode: mode } : p)));
  };

  const updateReferenceUrl = (idx: number, value: string) => {
    setPages((prev) => prev.map((p, i) => (i === idx ? { ...p, referenceUrl: value } : p)));
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
    const pageArg = collectPagePaths(fullQA, pages);
    if (modalTab === "full") {
      onConfirm(pageArg, testMode, undefined);
    } else {
      onConfirm(pageArg, testMode, Array.from(selectedTests));
    }
  };

  const anyEnabled = fullQA || pages.some((p) => p.enabled);
  const canStart = !isLoading && anyEnabled && (modalTab === "full" || selectedTests.size > 0);

  /** Shared page selection UI used in both tabs */
  const renderPageSelector = () => (
    <>
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

      <div>
        <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wide mb-2">
          Or select specific pages
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
                <div className="px-3 pb-3 space-y-2">
                  {/* Existing URLs textarea */}
                  <div>
                    <label htmlFor={`urls-${idx}`} className="sr-only">
                      {page.label} URLs
                    </label>
                    <textarea
                      id={`urls-${idx}`}
                      value={page.urls}
                      onChange={(e) => updateUrls(idx, e.target.value)}
                      rows={2}
                      placeholder={
                        page.label === "Homepage"
                          ? "/ (default — or paste a specific URL)"
                          : page.label === "Collection Pages"
                          ? "Paste collection URLs — one per line:\nhttps://store.com/collections/summer"
                          : page.label === "Product Pages"
                          ? "Paste product URLs — one per line:\nhttps://store.com/products/boot-1"
                          : "Paste page URLs:\nhttps://store.com/pages/about"
                      }
                      className="w-full px-2.5 py-1.5 border border-gray-200 dark:border-slate-600 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-200 placeholder-gray-400 dark:placeholder-slate-500"
                    />
                  </div>

                  {/* Per-page mode toggle — only for non-homepage pages in design mode */}
                  {page.label !== "Homepage" && testMode === "design" && (
                    <div className="space-y-1.5">
                      <p className="text-xs text-gray-500 dark:text-slate-400 font-medium">
                        Comparison mode
                      </p>
                      <div className="flex rounded-md overflow-hidden border border-gray-200 dark:border-slate-600">
                        <button
                          type="button"
                          onClick={() => togglePageMode(idx, "design")}
                          className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
                            page.pageMode === "design"
                              ? "bg-indigo-600 text-white"
                              : "bg-white dark:bg-slate-800 text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-white/5"
                          }`}
                        >
                          Design Comparison
                        </button>
                        <button
                          type="button"
                          onClick={() => togglePageMode(idx, "ai")}
                          className={`flex-1 py-1.5 text-xs font-medium border-l border-gray-200 dark:border-slate-600 transition-colors ${
                            page.pageMode === "ai"
                              ? "bg-indigo-600 text-white"
                              : "bg-white dark:bg-slate-800 text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-white/5"
                          }`}
                        >
                          AI Only
                        </button>
                      </div>

                      {/* Reference URL — required when Design Comparison selected */}
                      {page.pageMode === "design" && (
                        <div>
                          <label
                            htmlFor={`ref-url-${idx}`}
                            className="text-xs text-gray-500 dark:text-slate-400 mb-1 block"
                          >
                            Reference URL <span className="text-red-500" aria-hidden="true">*</span>
                          </label>
                          <input
                            id={`ref-url-${idx}`}
                            type="url"
                            value={page.referenceUrl}
                            onChange={(e) => updateReferenceUrl(idx, e.target.value)}
                            placeholder="https://live-site.com/collections/..."
                            className="w-full px-2.5 py-1.5 border border-gray-200 dark:border-slate-600 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-200 placeholder-gray-400 dark:placeholder-slate-500"
                          />
                        </div>
                      )}
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

  /** Shared testing mode UI */
  const renderTestingMode = (namePrefix: string) => (
    <div>
      <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wide mb-2">Testing mode</p>
      <div className="space-y-2">
        {TEST_MODES.map((mode) => (
          <label
            key={mode.value}
            className={`flex items-start gap-3 cursor-pointer px-3 py-2.5 rounded-lg border transition-colors ${
              testMode === mode.value
                ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 dark:border-indigo-400"
                : "border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-white/5"
            }`}
          >
            <input
              type="radio"
              name={namePrefix}
              value={mode.value}
              checked={testMode === mode.value}
              onChange={() => setTestMode(mode.value as "design" | "ai")}
              className="w-4 h-4 accent-indigo-600 mt-0.5"
            />
            <div>
              <div className="text-sm font-medium text-gray-800 dark:text-slate-200">
                <span aria-hidden="true">{mode.icon}</span> {mode.label}
              </div>
              <div className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">{mode.desc}</div>
            </div>
          </label>
        ))}
      </div>
    </div>
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
            <span aria-hidden="true">⚡</span> Full QA
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
            <span aria-hidden="true">⚙️</span> Customize
          </button>
        </div>

        {/* ── FULL QA TAB ── */}
        <div
          role="tabpanel"
          id="panel-full"
          aria-labelledby="tab-full"
          hidden={modalTab !== "full"}
          className="space-y-4"
        >
          {renderPageSelector()}
          {renderTestingMode("testModeFull")}
          <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20 rounded-lg px-3 py-2 text-xs text-blue-700 dark:text-blue-400">
            <strong>Always included:</strong> ADA compliance, link &amp; button audit, functional tests.
            QA runs in background — you can navigate away safely.
          </div>
        </div>

        {/* ── CUSTOMIZE TAB ── */}
        <div
          role="tabpanel"
          id="panel-customize"
          aria-labelledby="tab-customize"
          hidden={modalTab !== "customize"}
          className="space-y-4"
        >
          {/* 1. SELECT TESTS TO RUN — comes first */}
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

                  {/* Link & Button Audit sub-item — only visible when QA Test is checked */}
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
                          <span aria-hidden="true">🔗</span> Link &amp; Button Audit
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

          {/* 2. SELECT PAGES — comes second */}
          <div>
            <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wide mb-2">
              Select pages
            </p>
            {renderPageSelector()}
          </div>

          {/* 3. TESTING MODE */}
          {renderTestingMode("testModeCustomize")}
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
              ? <><span aria-hidden="true">⚙️</span> Run Selected Tests</>
              : <><span aria-hidden="true">🚀</span> Start QA Run</>}
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
