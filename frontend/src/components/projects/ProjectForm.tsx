import { useState } from "react";

interface ProjectFormData {
  name: string;
  shopify_url: string;
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
    source_url: "",
    shopify_password: "",
    figma_token: "",
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const data: ProjectFormData = {
      name: form.name,
      shopify_url: form.shopify_url,
    };
    if (form.source_url) data.source_url = form.source_url;
    if (form.shopify_password) data.shopify_password = form.shopify_password;
    if (form.figma_token) data.figma_token = form.figma_token;
    onSubmit(data);
  };

  const isFigmaUrl = (form.source_url || "").includes("figma.com/");
  const hasSourceUrl = !!(form.source_url && form.source_url.trim());

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">
          New Project
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

          {/* Reference URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Reference URL{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="url"
              name="source_url"
              value={form.source_url}
              onChange={handleChange}
              placeholder="https://my-design.vercel.app"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {!hasSourceUrl && (
              <p className="mt-1 text-xs text-gray-400">
                No reference — QA will use AI analysis to review your Shopify site
              </p>
            )}
            {hasSourceUrl && !isFigmaUrl && (
              <p className="mt-1 text-xs text-gray-400">
                Any live site URL works — Vercel, Webflow, Netlify, static HTML, etc.
              </p>
            )}
            {isFigmaUrl && (
              <p className="mt-1 text-xs text-gray-400">
                Figma design detected — provide a token below for API access
              </p>
            )}
          </div>

          {/* Figma Token — only shown when URL contains figma.com/ */}
          {isFigmaUrl && (
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
