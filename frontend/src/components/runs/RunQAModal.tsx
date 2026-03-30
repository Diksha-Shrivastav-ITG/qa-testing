import { useState } from "react";

interface PageEntry {
  label: string;
  enabled: boolean;
  urls: string;
}

const DEFAULT_PAGES: PageEntry[] = [
  { label: "Homepage", enabled: true, urls: "/" },
  { label: "Collection Pages", enabled: false, urls: "" },
  { label: "Product Pages", enabled: false, urls: "" },
  { label: "Other Pages", enabled: false, urls: "" },
];

const TEST_MODES = [
  {
    value: "design",
    label: "Design Comparison",
    desc: "Compare against Framer / Figma reference",
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
}

const RunQAModal = ({ onConfirm, onCancel, isLoading }: RunQAModalProps) => {
  const [modalTab, setModalTab] = useState<"full" | "customize">("full");
  const [fullQA, setFullQA] = useState(true);
  const [pages, setPages] = useState<PageEntry[]>(DEFAULT_PAGES);
  const [testMode, setTestMode] = useState<"design" | "ai">("ai");
  const [selectedTests, setSelectedTests] = useState<Set<string>>(
    () => new Set(TEST_TYPES.map((t) => t.key))
  );

  const togglePage = (idx: number) => {
    setFullQA(false);
    setPages((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, enabled: !p.enabled } : p))
    );
  };

  const toggleCustomizePage = (idx: number) => {
    setPages((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, enabled: !p.enabled } : p))
    );
  };

  const updateUrls = (idx: number, value: string) => {
    setPages((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, urls: value } : p))
    );
  };

  const handleFullQA = () => {
    setFullQA(true);
    setPages(DEFAULT_PAGES);
  };

  const toggleTestType = (key: string) => {
    setSelectedTests((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const handleConfirm = () => {
    let pageArg = "";

    if (modalTab === "full") {
      if (!fullQA) {
        const allPaths: string[] = [];
        for (const page of pages) {
          if (!page.enabled) continue;
          const lines = page.urls
            .split("\n")
            .map((l) => l.trim())
            .filter(Boolean);
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
        pageArg = allPaths.join(",");
      }
      onConfirm(pageArg, testMode, undefined);
    } else {
      // Customize tab — collect enabled pages
      const allPaths: string[] = [];
      for (const page of pages) {
        if (!page.enabled) continue;
        allPaths.push(page.label === "Homepage" ? "/" : page.label === "Collection Pages" ? "/collections" : page.label === "Product Pages" ? "/products" : "__other__");
      }
      pageArg = allPaths.join(",");
      onConfirm(pageArg, testMode, Array.from(selectedTests));
    }
  };

  const anyEnabled = modalTab === "full"
    ? (fullQA || pages.some((p) => p.enabled))
    : pages.some((p) => p.enabled) || true; // customize always has "all pages" option

  const canStart = !isLoading &&
    anyEnabled &&
    (modalTab === "full" || selectedTests.size > 0);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg space-y-4 p-6 max-h-[90vh] overflow-y-auto">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Start QA Run</h2>
          <p className="text-sm text-gray-500 mt-0.5">Select pages and test scope.</p>
        </div>

        {/* Full QA | Customize tab bar */}
        <div className="flex border border-gray-200 rounded-lg overflow-hidden">
          <button
            type="button"
            onClick={() => setModalTab("full")}
            className={`flex-1 py-2 text-sm font-semibold transition-colors ${
              modalTab === "full"
                ? "bg-indigo-600 text-white"
                : "bg-gray-50 text-gray-500 hover:bg-gray-100"
            }`}
          >
            ⚡ Full QA
          </button>
          <button
            type="button"
            onClick={() => setModalTab("customize")}
            className={`flex-1 py-2 text-sm font-semibold border-l border-gray-200 transition-colors ${
              modalTab === "customize"
                ? "bg-indigo-600 text-white"
                : "bg-gray-50 text-gray-500 hover:bg-gray-100"
            }`}
          >
            ⚙️ Customize
          </button>
        </div>

        {/* ── FULL QA TAB ── */}
        {modalTab === "full" && (
          <>
            {/* Full QA toggle */}
            <label
              className={`flex items-center gap-3 cursor-pointer px-3 py-2.5 rounded-lg border transition-colors ${
                fullQA ? "border-indigo-500 bg-indigo-50" : "border-gray-200 hover:bg-gray-50"
              }`}
              onClick={handleFullQA}
            >
              <input type="radio" checked={fullQA} readOnly className="w-4 h-4 accent-indigo-600" />
              <div>
                <span className="text-sm font-medium text-gray-800">Full QA — all discovered pages</span>
                <p className="text-xs text-gray-400">Automatically discovers and tests all pages</p>
              </div>
            </label>

            {/* Per-page selection */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Or select specific pages
              </p>
              <div className="space-y-2">
                {pages.map((page, idx) => (
                  <div key={idx} className={`rounded-lg border transition-colors ${
                    !fullQA && page.enabled ? "border-indigo-400 bg-indigo-50/50" : "border-gray-200"
                  }`}>
                    <label
                      className="flex items-center gap-3 cursor-pointer px-3 py-2.5"
                      onClick={(e) => { e.preventDefault(); togglePage(idx); }}
                    >
                      <input
                        type="checkbox"
                        checked={!fullQA && page.enabled}
                        readOnly
                        className="w-4 h-4 accent-indigo-600 rounded"
                      />
                      <span className="text-sm font-medium text-gray-700">{page.label}</span>
                    </label>
                    {!fullQA && page.enabled && (
                      <div className="px-3 pb-3">
                        <textarea
                          value={page.urls}
                          onChange={(e) => updateUrls(idx, e.target.value)}
                          rows={2}
                          placeholder={
                            page.label === "Homepage"
                              ? "/ (default — or paste a specific URL)"
                              : page.label === "Collection Pages"
                              ? "Paste collection URLs — one per line"
                              : page.label === "Product Pages"
                              ? "Paste product URLs — one per line"
                              : "Paste page URLs"
                          }
                          className="w-full px-2.5 py-1.5 border border-gray-200 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white"
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Testing mode */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Testing mode</p>
              <div className="space-y-2">
                {TEST_MODES.map((mode) => (
                  <label
                    key={mode.value}
                    className={`flex items-start gap-3 cursor-pointer px-3 py-2.5 rounded-lg border transition-colors ${
                      testMode === mode.value
                        ? "border-indigo-500 bg-indigo-50"
                        : "border-gray-200 hover:bg-gray-50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="testMode"
                      value={mode.value}
                      checked={testMode === mode.value}
                      onChange={() => setTestMode(mode.value as "design" | "ai")}
                      className="w-4 h-4 accent-indigo-600 mt-0.5"
                    />
                    <div>
                      <div className="text-sm font-medium text-gray-800">{mode.icon} {mode.label}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{mode.desc}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Info */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-xs text-blue-700">
              <strong>Always included:</strong> ADA compliance, link &amp; button audit, functional tests.
              QA runs in background — you can navigate away safely.
            </div>
          </>
        )}

        {/* ── CUSTOMIZE TAB ── */}
        {modalTab === "customize" && (
          <>
            {/* Page selector */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Select pages
              </p>
              <div className="space-y-2">
                {pages.map((page, idx) => (
                  <div
                    key={idx}
                    className={`rounded-lg border transition-colors ${
                      page.enabled ? "border-indigo-400 bg-indigo-50/50" : "border-gray-200"
                    }`}
                  >
                    <label
                      className="flex items-center gap-3 cursor-pointer px-3 py-2.5"
                      onClick={(e) => { e.preventDefault(); toggleCustomizePage(idx); }}
                    >
                      <input
                        type="checkbox"
                        checked={page.enabled}
                        readOnly
                        className="w-4 h-4 accent-indigo-600 rounded"
                      />
                      <span className="text-sm font-medium text-gray-700">{page.label}</span>
                    </label>
                  </div>
                ))}
              </div>
            </div>

            {/* Test type checkboxes */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Select tests to run
              </p>
              <div className="space-y-2">
                {TEST_TYPES.map((t) => (
                  <label
                    key={t.key}
                    className={`flex items-start gap-3 cursor-pointer px-3 py-2.5 rounded-lg border transition-colors ${
                      selectedTests.has(t.key)
                        ? "border-indigo-400 bg-indigo-50/50"
                        : "border-gray-200 hover:bg-gray-50"
                    }`}
                    onClick={(e) => { e.preventDefault(); toggleTestType(t.key); }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedTests.has(t.key)}
                      readOnly
                      className="w-4 h-4 accent-indigo-600 rounded mt-0.5"
                    />
                    <div>
                      <div className="text-sm font-medium text-gray-800">
                        {t.icon} {t.label}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">{t.desc}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Testing mode */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Testing mode</p>
              <div className="space-y-2">
                {TEST_MODES.map((mode) => (
                  <label
                    key={mode.value}
                    className={`flex items-start gap-3 cursor-pointer px-3 py-2.5 rounded-lg border transition-colors ${
                      testMode === mode.value
                        ? "border-indigo-500 bg-indigo-50"
                        : "border-gray-200 hover:bg-gray-50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="testModeCustomize"
                      value={mode.value}
                      checked={testMode === mode.value}
                      onChange={() => setTestMode(mode.value as "design" | "ai")}
                      className="w-4 h-4 accent-indigo-600 mt-0.5"
                    />
                    <div>
                      <div className="text-sm font-medium text-gray-800">{mode.icon} {mode.label}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{mode.desc}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {selectedTests.size === 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-700">
                Select at least one test to run.
              </div>
            )}
          </>
        )}

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
              ? "⚙️ Run Selected Tests"
              : "🚀 Start QA Run"}
          </button>
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

export default RunQAModal;
