import { useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ProjectFormData {
  name: string;
  shopify_url: string;
  source_type: string;
  source_url?: string;
  shopify_password?: string;
}

interface ProjectFormProps {
  onSubmit: (data: ProjectFormData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isValidUrl(value: string): boolean {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

const PLATFORM_RULES: [string, RegExp[]][] = [
  ["figma",   [/figma\.com\/(file|proto|design|board)/i]],
  ["framer",  [/framer\.com/i, /\.framer\.app/i, /\.framer\.website/i]],
  ["webflow", [/webflow\.io/i, /\.webflow\.com/i]],
  ["vercel",  [/\.vercel\.app/i]],
];

function detectSourceType(url: string): string {
  for (const [platform, patterns] of PLATFORM_RULES) {
    if (patterns.some((re) => re.test(url))) return platform;
  }
  return "url";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function InputLabel({
  children,
  required,
  optional,
}: {
  children: React.ReactNode;
  required?: boolean;
  optional?: boolean;
}) {
  return (
    <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
      {children}
      {required && <span className="text-red-500 ml-0.5">*</span>}
      {optional && (
        <span className="text-gray-400 font-normal ml-1">(optional)</span>
      )}
    </label>
  );
}

const INPUT_CLS =
  "w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-400 dark:focus:border-violet-500 transition-colors";

const INPUT_ERROR_CLS =
  "w-full px-3 py-2 border border-red-400 dark:border-red-500 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-red-400 focus:border-red-400 transition-colors";

// ---------------------------------------------------------------------------
// Main form
// ---------------------------------------------------------------------------

type Mode = "ai" | "visual_design";

const ProjectForm = ({ onSubmit, onCancel, isLoading }: ProjectFormProps) => {
  const [name, setName]                   = useState("");
  const [storeUrl, setStoreUrl]           = useState("");
  const [storePassword, setStorePassword] = useState("");
  const [mode, setMode]                   = useState<Mode>("ai");
  const [referenceUrl, setReferenceUrl]   = useState("");

  // Validation errors (only shown after first submit attempt)
  const [submitted, setSubmitted] = useState(false);

  const storeUrlError   = submitted && storeUrl.trim() && !isValidUrl(storeUrl.trim());
  const referenceError  = submitted && mode === "visual_design" && referenceUrl.trim() && !isValidUrl(referenceUrl.trim());

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);

    // Validate URLs
    if (!isValidUrl(storeUrl.trim())) return;
    if (mode === "visual_design" && !isValidUrl(referenceUrl.trim())) return;

    const data: ProjectFormData = {
      name: name.trim(),
      shopify_url: storeUrl.trim(),
      source_type: mode === "ai" ? "none" : detectSourceType(referenceUrl.trim()),
    };

    if (mode === "visual_design") {
      data.source_url = referenceUrl.trim();
    }

    if (storePassword.trim()) {
      data.shopify_password = storePassword.trim();
    }

    onSubmit(data);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full max-w-md mx-auto overflow-y-auto max-h-[90vh] border border-gray-200 dark:border-slate-700">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-gray-100 dark:border-slate-800">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">New Project</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
            Set up your store and choose a testing mode
          </p>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {/* Project Name */}
          <div>
            <InputLabel required>Project Name</InputLabel>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="My Shopify Store"
              className={INPUT_CLS}
            />
          </div>

          {/* Store URL */}
          <div>
            <InputLabel required>Store URL</InputLabel>
            <input
              type="text"
              value={storeUrl}
              onChange={(e) => { setStoreUrl(e.target.value); setSubmitted(false); }}
              required
              placeholder="https://mystore.myshopify.com"
              className={storeUrlError ? INPUT_ERROR_CLS : INPUT_CLS}
            />
            {storeUrlError && (
              <p className="mt-1 text-xs text-red-500">Please enter a valid URL (e.g. https://mystore.com)</p>
            )}
          </div>

          {/* Mode selection */}
          <div>
            <InputLabel>Testing Mode</InputLabel>
            <div className="grid grid-cols-2 gap-3">
              {/* AI Testing */}
              <button
                type="button"
                onClick={() => setMode("ai")}
                className={`flex flex-col items-start gap-1 px-4 py-3 rounded-lg border-2 text-left transition-all ${
                  mode === "ai"
                    ? "border-violet-500 bg-violet-50 dark:bg-violet-500/10 dark:border-violet-400"
                    : "border-gray-200 dark:border-slate-600 hover:border-gray-300 dark:hover:border-slate-500 bg-white dark:bg-slate-800"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                      mode === "ai" ? "border-violet-500" : "border-gray-300 dark:border-slate-500"
                    }`}
                  >
                    {mode === "ai" && <span className="w-2 h-2 rounded-full bg-violet-500" />}
                  </span>
                  <span
                    className={`text-sm font-medium ${
                      mode === "ai" ? "text-violet-700 dark:text-violet-300" : "text-gray-700 dark:text-slate-300"
                    }`}
                  >
                    AI Testing
                  </span>
                </div>
                <p className="text-xs text-gray-400 pl-6">
                  AI audits your store automatically
                </p>
              </button>

              {/* Visual Design Comparison */}
              <button
                type="button"
                onClick={() => setMode("visual_design")}
                className={`flex flex-col items-start gap-1 px-4 py-3 rounded-lg border-2 text-left transition-all ${
                  mode === "visual_design"
                    ? "border-violet-500 bg-violet-50 dark:bg-violet-500/10 dark:border-violet-400"
                    : "border-gray-200 dark:border-slate-600 hover:border-gray-300 dark:hover:border-slate-500 bg-white dark:bg-slate-800"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                      mode === "visual_design" ? "border-violet-500" : "border-gray-300 dark:border-slate-500"
                    }`}
                  >
                    {mode === "visual_design" && <span className="w-2 h-2 rounded-full bg-violet-500" />}
                  </span>
                  <span
                    className={`text-sm font-medium ${
                      mode === "visual_design"
                        ? "text-violet-700 dark:text-violet-300"
                        : "text-gray-700 dark:text-slate-300"
                    }`}
                  >
                    Visual Design Comparison
                  </span>
                </div>
                <p className="text-xs text-gray-400 pl-6">
                  Compare store against a reference URL
                </p>
              </button>
            </div>
          </div>

          {/* Reference URL — only shown for Visual Design Comparison */}
          {mode === "visual_design" && (
            <div>
              <InputLabel required>Reference URL</InputLabel>
              <input
                type="text"
                value={referenceUrl}
                onChange={(e) => { setReferenceUrl(e.target.value); setSubmitted(false); }}
                placeholder="https://design.example.com"
                className={referenceError ? INPUT_ERROR_CLS : INPUT_CLS}
              />
              {referenceError && (
                <p className="mt-1 text-xs text-red-500">Please enter a valid URL (e.g. https://design.example.com)</p>
              )}
              {!referenceError && (
                <p className="mt-1 text-xs text-gray-400">
                  Figma, Framer, Webflow, Vercel, or any web URL
                </p>
              )}
            </div>
          )}

          {/* Store Password */}
          <div>
            <InputLabel optional>Store Password</InputLabel>
            <input
              type="password"
              value={storePassword}
              onChange={(e) => setStorePassword(e.target.value)}
              placeholder="Password-protected store access"
              className={INPUT_CLS}
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-violet-600 rounded-lg hover:bg-violet-700 disabled:opacity-60 transition-colors"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  Creating…
                </span>
              ) : (
                "Create Project"
              )}
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={isLoading}
              className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-slate-300 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700/50 disabled:opacity-60 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ProjectForm;
