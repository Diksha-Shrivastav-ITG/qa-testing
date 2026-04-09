import { useState } from "react";

interface ProjectFormData {
  name: string;
  shopify_url: string;
  source_type: string;
  source_url?: string;
  shopify_password?: string;
  figma_token?: string;
}

interface ProjectFormProps {
  onSubmit: (data: ProjectFormData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const ProjectForm = ({ onSubmit, onCancel, isLoading }: ProjectFormProps) => {
  const [form, setForm] = useState<ProjectFormData>({
    name: "",
    shopify_url: "",
    source_type: "none",
    source_url: "",
    shopify_password: "",
    figma_token: "",
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const data: ProjectFormData = {
      name: form.name,
      shopify_url: form.shopify_url,
      source_type: form.source_type,
    };
    if (form.source_url) data.source_url = form.source_url;
    if (form.shopify_password) data.shopify_password = form.shopify_password;
    if (form.figma_token) data.figma_token = form.figma_token;
    onSubmit(data);
  };

  const hasDesignSource = form.source_type !== "none";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">
          New Projectss 
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Project Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              name="name"
              value={form.name}
              onChange={handleChange}
              required
              placeholder="My Shopify Store"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Shopify URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Shopify URL <span className="text-red-500">*</span>
            </label>
            <input
              type="url"
              name="shopify_url"
              value={form.shopify_url}
              onChange={handleChange}
              required
              placeholder="https://mystore.myshopify.com"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Source Type — tab-style radio buttons */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Design Source
            </label>
            <div className="grid grid-cols-4 gap-2">
              {[
                { value: "none", label: "AI Testing", icon: "\u{1F916}" },
                { value: "framer", label: "Framer", icon: "\u{1F3A8}" },
                { value: "figma", label: "Figma", icon: "\u{1F58C}\uFE0F" },
                { value: "other", label: "Other", icon: "\u{1F517}" },
              ].map((opt) => (
                <label
                  key={opt.value}
                  className={`flex flex-col items-center gap-1 cursor-pointer px-2 py-2.5 rounded-lg border-2 text-center transition-all ${
                    form.source_type === opt.value
                      ? "border-indigo-500 bg-indigo-50 text-indigo-700 shadow-sm"
                      : "border-gray-200 text-gray-500 hover:border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="source_type"
                    value={opt.value}
                    checked={form.source_type === opt.value}
                    onChange={handleChange}
                    className="sr-only"
                  />
                  <span className="text-lg" aria-hidden="true">{opt.icon}</span>
                  <span className="text-xs font-semibold">{opt.label}</span>
                </label>
              ))}
            </div>
            {form.source_type === "none" && (
              <p className="mt-2 text-xs text-gray-400">
                No design reference — QA will use AI analysis to review your Shopify site
              </p>
            )}
          </div>

          {/* Source URL — shown when Framer/Figma/Other selected */}
          {hasDesignSource && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {form.source_type === "figma"
                  ? "Figma URL"
                  : form.source_type === "framer"
                  ? "Framer URL"
                  : "Reference URL"}{" "}
                <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                name="source_url"
                value={form.source_url}
                onChange={handleChange}
                required
                placeholder={
                  form.source_type === "other"
                    ? "https://example.com (any reference URL)"
                    : "https://..."
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          {/* Optional: Shopify Password */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Shopify Password{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="password"
              name="shopify_password"
              value={form.shopify_password}
              onChange={handleChange}
              placeholder="Password-protected store access"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Optional: Figma Token */}
          {form.source_type === "figma" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Figma Token{" "}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <input
                type="password"
                name="figma_token"
                value={form.figma_token}
                onChange={handleChange}
                placeholder="figd_..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
            >
              {isLoading ? "Creating..." : "Create Project"}
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={isLoading}
              className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-60 transition-colors"
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
