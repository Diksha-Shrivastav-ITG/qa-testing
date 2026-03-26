import { useState, useMemo } from "react";

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
  issues: Issue[];
  accItems: AccItem[];
  projectName?: string;
  shopifyUrl?: string;
  onClose: () => void;
}

type Step = "select" | "generated";

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

const PromptBuilder = ({ issues, accItems, projectName, shopifyUrl, onClose }: PromptBuilderProps) => {
  const [step, setStep] = useState<Step>("select");
  const [selectedIssues, setSelectedIssues] = useState<Set<number>>(new Set());
  const [selectedAcc, setSelectedAcc] = useState<Set<number>>(new Set());
  const [copied, setCopied] = useState(false);

  // Combine all items for the selection UI
  const allItems = useMemo(() => {
    const items: Array<{
      id: string;
      severity: string;
      description: string;
      element?: string;
      suggestion?: string;
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
        suggestion: i.ai_suggestion,
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
        suggestion: a.wcag ? `Fix WCAG ${a.wcag} violation` : undefined,
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

  // Generate the prompt
  const generatedPrompt = useMemo(() => {
    const selectedItems = allItems.filter(item => isSelected(item));
    if (selectedItems.length === 0) return "";

    const grouped: Record<string, typeof allItems> = {};
    selectedItems.forEach(item => {
      (grouped[item.page] ??= []).push(item);
    });

    let prompt = `I need you to fix the following QA issues on my Shopify store.\n\n`;
    prompt += `**Store:** ${shopifyUrl || "my Shopify store"}\n`;
    if (projectName) prompt += `**Project:** ${projectName}\n`;
    prompt += `**Total issues to fix:** ${selectedItems.length}\n\n`;
    prompt += `---\n\n`;

    let issueNum = 0;
    for (const [page, items] of Object.entries(grouped)) {
      prompt += `## ${pageLabel(page)}\n\n`;
      for (const item of items) {
        issueNum++;
        prompt += `### Issue ${issueNum} [${item.severity.toUpperCase()}]\n`;
        prompt += `**Problem:** ${item.description}\n`;
        if (item.element) prompt += `**Element:** ${item.element}\n`;
        if (item.suggestion) prompt += `**Suggested fix:** ${item.suggestion}\n`;
        prompt += `\n`;
      }
    }

    prompt += `---\n\n`;
    prompt += `**Instructions:**\n`;
    prompt += `- Fix each issue listed above in the Shopify theme code (Liquid, CSS, or JS as needed).\n`;
    prompt += `- For each fix, explain what file you changed and why.\n`;
    prompt += `- Prioritize critical issues first, then major, then minor.\n`;
    prompt += `- Make sure fixes don't break existing functionality.\n`;
    prompt += `- Test responsive behavior after changes.\n`;

    return prompt;
  }, [allItems, selectedIssues, selectedAcc, projectName, shopifyUrl]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(generatedPrompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
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
              {step === "select" ? "Select Issues to Fix" : "Your Fix Prompt"}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {step === "select"
                ? "Choose which issues you want Claude to fix"
                : "Copy this prompt and paste it in Claude Code or VS Code Claude"}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {step === "select" && (
            <div className="space-y-4">
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

          {step === "generated" && (
            <div className="space-y-4">
              <div className="bg-gray-900 rounded-lg p-4 overflow-auto max-h-[50vh]">
                <pre className="text-sm text-gray-100 whitespace-pre-wrap font-mono leading-relaxed">
                  {generatedPrompt}
                </pre>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-800">
                <strong>How to use:</strong>
                <ol className="mt-1 ml-4 list-decimal space-y-1">
                  <li>Click "Copy Prompt" below</li>
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
                  onClick={() => setStep("generated")}
                  disabled={totalSelected === 0}
                  className="px-5 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-40 transition-colors"
                >
                  Generate Prompt ({totalSelected})
                </button>
              </div>
            </>
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
                  className={`px-5 py-2 text-sm font-medium rounded-lg transition-colors ${
                    copied
                      ? "bg-green-600 text-white"
                      : "bg-indigo-600 text-white hover:bg-indigo-700"
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
