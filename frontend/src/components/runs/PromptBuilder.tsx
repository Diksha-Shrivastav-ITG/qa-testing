import { useState, useMemo } from "react";
import api from "../../api/client";

interface Issue {
  id: number;
  type: string;
  severity: string;
  page?: string;
  description: string;
  ai_suggestion?: string;
  element_selector?: string;
}

interface AccItem {
  id: number;
  page: string;
  severity: string;
  description: string;
  wcag?: string;
  element?: string;
}

interface PromptBuilderProps {
  runId: number;
  issues: Issue[];
  accItems: AccItem[];
  projectName?: string;
  shopifyUrl?: string;
  onClose: () => void;
}

type Step = "select" | "loading" | "generated";

const sevColor: Record<string, string> = {
  critical: "border-red-400 bg-red-50",
  major: "border-orange-400 bg-orange-50",
  minor: "border-yellow-400 bg-yellow-50",
  high: "border-orange-400 bg-orange-50",
  medium: "border-yellow-400 bg-yellow-50",
  low: "border-gray-300 bg-gray-50",
  error: "border-red-400 bg-red-50",
  warning: "border-orange-400 bg-orange-50",
};

const sevBadge: Record<string, string> = {
  critical: "bg-red-600 text-white",
  major: "bg-orange-500 text-white",
  minor: "bg-yellow-500 text-white",
  high: "bg-orange-500 text-white",
  medium: "bg-yellow-500 text-white",
  low: "bg-gray-400 text-white",
};

const pageLabel = (p: string) => {
  if (!p || p === "home" || p === "/") return "Homepage";
  return p.replace(/^\//, "").split("/").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(" > ");
};

const PromptBuilder = ({ runId, issues, accItems, projectName, shopifyUrl, onClose }: PromptBuilderProps) => {
  const [step, setStep] = useState<Step>("select");
  const [selectedIssues, setSelectedIssues] = useState<Set<number>>(new Set());
  const [selectedAcc, setSelectedAcc] = useState<Set<number>>(new Set());
  const [generatedPrompt, setGeneratedPrompt] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Combine all items for the selection UI
  const allItems = useMemo(() => {
    const items: Array<{
      id: string;
      severity: string;
      description: string;
      element?: string;
      page: string;
      category: "issue" | "accessibility";
      originalId: number;
    }> = [];

    issues.forEach(i => {
      items.push({
        id: `issue-${i.id}`,
        severity: i.severity,
        description: i.description,
        element: i.element_selector,
        page: i.page ?? "home",
        category: "issue",
        originalId: i.id,
      });
    });

    accItems.forEach(a => {
      items.push({
        id: `acc-${a.id}`,
        severity: a.severity,
        description: a.description,
        element: a.element,
        page: a.page,
        category: "accessibility",
        originalId: a.id,
      });
    });

    return items;
  }, [issues, accItems]);

  // Group by page
  const byPage = useMemo(() => {
    const groups: Record<string, typeof allItems> = {};
    allItems.forEach(item => {
      (groups[item.page] ??= []).push(item);
    });
    return groups;
  }, [allItems]);

  const toggleIssue = (id: number) => {
    setSelectedIssues(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAcc = (id: number) => {
    setSelectedAcc(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleItem = (item: typeof allItems[0]) => {
    if (item.category === "issue") toggleIssue(item.originalId);
    else toggleAcc(item.originalId);
  };

  const isSelected = (item: typeof allItems[0]) => {
    if (item.category === "issue") return selectedIssues.has(item.originalId);
    return selectedAcc.has(item.originalId);
  };

  const selectAll = () => {
    setSelectedIssues(new Set(issues.map(i => i.id)));
    setSelectedAcc(new Set(accItems.map(a => a.id)));
  };

  const selectNone = () => {
    setSelectedIssues(new Set());
    setSelectedAcc(new Set());
  };

  const totalSelected = selectedIssues.size + selectedAcc.size;

  // Call Groq AI via backend to generate the prompt
  const handleGenerate = async () => {
    setStep("loading");
    setError(null);

    try {
      const res = await api.post(`/api/runs/${runId}/generate-prompt`, {
        issue_ids: Array.from(selectedIssues),
        acc_ids: Array.from(selectedAcc),
        project_name: projectName,
        shopify_url: shopifyUrl,
      });
      setGeneratedPrompt(res.data.prompt);
      setStep("generated");
    } catch (err) {
      setError("Failed to generate prompt. Please try again.");
      setStep("select");
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(generatedPrompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = generatedPrompt;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {step === "select" ? "Select Issues to Fix" : step === "loading" ? "Generating Prompt..." : "AI-Generated Fix Prompt"}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {step === "select"
                ? "Choose which issues you want Claude to fix"
                : step === "loading"
                ? "Groq AI is analyzing the issues and writing the fix prompt..."
                : "Copy this prompt and paste it in Claude Code or VS Code Claude"}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {step === "select" && (
            <div className="space-y-4">
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">{error}</div>
              )}

              {/* Quick actions */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">
                  {totalSelected} of {allItems.length} selected
                </span>
                <div className="flex gap-2">
                  <button onClick={selectAll} className="text-xs text-indigo-600 hover:text-indigo-800 font-medium">
                    Select All
                  </button>
                  <span className="text-gray-300">|</span>
                  <button onClick={selectNone} className="text-xs text-gray-500 hover:text-gray-700 font-medium">
                    Clear
                  </button>
                </div>
              </div>

              {/* Issues grouped by page */}
              {Object.entries(byPage).map(([page, items]) => (
                <div key={page}>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                    {pageLabel(page)} ({items.length})
                  </h3>
                  <div className="space-y-1.5">
                    {items.map((item) => {
                      const selected = isSelected(item);
                      return (
                        <button
                          key={item.id}
                          onClick={() => toggleItem(item)}
                          className={`w-full text-left px-3 py-2.5 rounded-lg border-l-4 transition-all ${
                            selected
                              ? `${sevColor[item.severity] ?? "border-gray-300 bg-gray-50"} ring-2 ring-indigo-300`
                              : "border-gray-200 bg-white hover:bg-gray-50"
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <div className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                              selected ? "bg-indigo-600 border-indigo-600" : "border-gray-300"
                            }`}>
                              {selected && (
                                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                </svg>
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-0.5">
                                <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${sevBadge[item.severity] ?? "bg-gray-400 text-white"}`}>
                                  {item.severity.toUpperCase()}
                                </span>
                                {item.category === "accessibility" && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-medium">ADA</span>
                                )}
                              </div>
                              <p className="text-sm text-gray-800 leading-snug">{item.description}</p>
                              {item.element && (
                                <p className="text-xs text-gray-400 mt-0.5 truncate">{item.element}</p>
                              )}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {step === "loading" && (
            <div className="flex flex-col items-center justify-center py-16 space-y-4">
              <div className="w-12 h-12 rounded-full border-4 border-indigo-200 border-t-indigo-600 animate-spin" />
              <div className="text-center">
                <p className="text-sm font-medium text-gray-700">AI is generating your fix prompt...</p>
                <p className="text-xs text-gray-400 mt-1">Groq AI is analyzing {totalSelected} issues and writing specific code fixes</p>
              </div>
            </div>
          )}

          {step === "generated" && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-xs text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Generated by Groq AI ({totalSelected} issues analyzed)
              </div>

              <div className="bg-gray-900 rounded-lg p-4 overflow-auto max-h-[50vh]">
                <pre className="text-sm text-gray-100 whitespace-pre-wrap font-mono leading-relaxed">
                  {generatedPrompt}
                </pre>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-800">
                <strong>How to use:</strong>
                <ol className="mt-1 ml-4 list-decimal space-y-1">
                  <li>Click <strong>"Copy Prompt"</strong> below</li>
                  <li>Open <strong>Claude Code</strong> in your terminal or <strong>Claude for VS Code</strong></li>
                  <li>Paste the prompt — Claude will read your theme files and fix each issue</li>
                </ol>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between shrink-0">
          {step === "select" && (
            <>
              <span className="text-sm text-gray-500">{totalSelected} issues selected</span>
              <div className="flex gap-3">
                <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Cancel</button>
                <button
                  onClick={handleGenerate}
                  disabled={totalSelected === 0}
                  className="px-5 py-2 text-sm font-medium text-white bg-gradient-to-r from-violet-600 to-indigo-600 rounded-lg hover:shadow-lg hover:shadow-violet-500/25 disabled:opacity-40 transition-all"
                >
                  Generate with AI ({totalSelected})
                </button>
              </div>
            </>
          )}

          {step === "loading" && (
            <div className="w-full text-center">
              <button onClick={() => setStep("select")} className="text-sm text-gray-500 hover:text-gray-700">Cancel</button>
            </div>
          )}

          {step === "generated" && (
            <>
              <button
                onClick={() => setStep("select")}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                &larr; Back to selection
              </button>
              <div className="flex gap-3">
                <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Close</button>
                <button
                  onClick={handleCopy}
                  className={`px-5 py-2 text-sm font-medium rounded-lg transition-all ${
                    copied
                      ? "bg-green-600 text-white"
                      : "bg-gradient-to-r from-violet-600 to-indigo-600 text-white hover:shadow-lg hover:shadow-violet-500/25"
                  }`}
                >
                  {copied ? "Copied!" : "Copy Prompt"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default PromptBuilder;
