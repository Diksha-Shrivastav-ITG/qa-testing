import { useState } from "react";

interface PageEntry {
  label: string;
  enabled: boolean;
  urls: string; // newline-separated URLs/paths
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

interface RunQAModalProps {
  onConfirm: (pages: string, testMode: "design" | "ai") => void;
  onCancel: () => void;
  isLoading: boolean;
}

const RunQAModal = ({ onConfirm, onCancel, isLoading }: RunQAModalProps) => {
  const [fullQA, setFullQA] = useState(true);
  const [pages, setPages] = useState<PageEntry[]>(DEFAULT_PAGES);
  const [testMode, setTestMode] = useState<"design" | "ai">("ai");

  const togglePage = (idx: number) => {
    setFullQA(false);
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

  const handleConfirm = () => {
    if (fullQA) {
      onConfirm("", testMode);
      return;
    }

    // Collect all paths from enabled pages
    const allPaths: string[] = [];
    for (const page of pages) {
      if (!page.enabled) continue;
      const lines = page.urls
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);

      if (lines.length === 0) {
        // Use default path mapping
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

    onConfirm(allPaths.join(","), testMode);
  };

  const anyEnabled = fullQA || pages.some((p) => p.enabled);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg space-y-4 p-6 max-h-[90vh] overflow-y-auto">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Start QA Run</h2>
          <p className="text-sm text-gray-500 mt-0.5">Select pages and paste specific URLs to test.</p>
        </div>

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

                {/* URL input — shown when page is enabled */}
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
                          ? "Paste collection URLs — one per line:\nhttps://store.com/collections/summer\nhttps://store.com/collections/winter"
                          : page.label === "Product Pages"
                          ? "Paste product URLs — one per line:\nhttps://store.com/products/boot-1\nhttps://store.com/products/jacket-2"
                          : "Paste page URLs:\nhttps://store.com/pages/about\nhttps://store.com/pages/contact"
                      }
                      className="w-full px-2.5 py-1.5 border border-gray-200 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white"
                    />
                    <p className="text-[10px] text-gray-400 mt-1">
                      Paste full URLs or paths. Each line = one page to test.
                      {page.label === "Collection Pages" && " Add multiple collection templates here."}
                      {page.label === "Product Pages" && " Add multiple product templates here."}
                    </p>
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

        {/* Actions */}
        <div className="flex gap-3 pt-1">
          <button
            onClick={handleConfirm}
            disabled={isLoading || !anyEnabled}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
          >
            {isLoading ? "Starting..." : "Start QA"}
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
