import { useState } from "react";

interface PageMapping {
  shopify_path: string;
  design_url: string;
}

interface ProjectFormData {
  name: string;
  shopify_url: string;
  source_type: string;
  source_url?: string;
  shopify_password?: string;
  figma_token?: string;
  page_mappings?: Record<string, string>;
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

  const [mappingRows, setMappingRows] = useState<PageMapping[]>([
    { shopify_path: "/", design_url: "" },
  ]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleMappingChange = (
    index: number,
    field: keyof PageMapping,
    value: string
  ) => {
    setMappingRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row))
    );
  };

  const addMappingRow = () => {
    setMappingRows((prev) => [...prev, { shopify_path: "", design_url: "" }]);
  };

  const removeMappingRow = (index: number) => {
    setMappingRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const data: ProjectFormData = {
      name: form.name,
      shopify_url: form.shopify_url,
      source_type: form.source_type,
    };
    if (form.source_type === "website") {
      // Convert rows to { shopify_path: design_url } dict
      const mappings: Record<string, string> = {};
      for (const row of mappingRows) {
        if (row.shopify_path.trim() && row.design_url.trim()) {
          mappings[row.shopify_path.trim()] = row.design_url.trim();
        }
      }
      if (Object.keys(mappings).length > 0) {
        data.page_mappings = mappings;
      }
    } else {
      if (form.source_url) data.source_url = form.source_url;
    }
    if (form.shopify_password) data.shopify_password = form.shopify_password;
    if (form.figma_token) data.figma_token = form.figma_token;
    onSubmit(data);
  };

  const isWebsite = form.source_type === "website";
  const hasDesignSource = form.source_type !== "none" && !isWebsite;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6 max-h-[90vh] overflow-y-auto">
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

          {/* Source Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Design Source
            </label>
            <select
              name="source_type"
              value={form.source_type}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="none">None (AI testing only)</option>
              <option value="framer">Framer</option>
              <option value="figma">Figma</option>
              <option value="website">Website</option>
            </select>
            {form.source_type === "none" && (
              <p className="mt-1 text-xs text-gray-400">
                No design reference — QA will use AI analysis to review your Shopify site
              </p>
            )}
            {isWebsite && (
              <p className="mt-1 text-xs text-gray-400">
                Custom website — provide individual page URLs below
              </p>
            )}
          </div>

          {/* Source URL — only shown when Framer/Figma selected */}
          {hasDesignSource && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {form.source_type === "figma" ? "Figma" : "Framer"} URL{" "}
                <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                name="source_url"
                value={form.source_url}
                onChange={handleChange}
                required
                placeholder="https://..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          {/* Page Mappings — only shown when Website selected */}
          {isWebsite && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Page Mappings <span className="text-red-500">*</span>
              </label>
              <div className="space-y-2">
                {mappingRows.map((row, index) => (
                  <div key={index} className="flex gap-2 items-start">
                    <input
                      type="text"
                      value={row.shopify_path}
                      onChange={(e) =>
                        handleMappingChange(index, "shopify_path", e.target.value)
                      }
                      placeholder="Shopify path, e.g. /"
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <input
                      type="url"
                      value={row.design_url}
                      onChange={(e) =>
                        handleMappingChange(index, "design_url", e.target.value)
                      }
                      placeholder="Design URL"
                      className="flex-[2] px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    {mappingRows.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeMappingRow(index)}
                        className="px-2 py-2 text-red-500 hover:text-red-700 text-sm"
                        title="Remove row"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={addMappingRow}
                className="mt-2 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
              >
                + Add Page
              </button>
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
