import { useState } from "react";

interface PageMapping {
  shopify_path: string;
  design_url: string;
}

interface ProjectFormData {
  name: string;
  shopify_url: string;
  source_type: string;
  shopify_password?: string;
  page_mappings?: Record<string, string>;
}

interface ProjectFormProps {
  onSubmit: (data: ProjectFormData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const ProjectForm = ({ onSubmit, onCancel, isLoading }: ProjectFormProps) => {
  const [name, setName] = useState("");
  const [shopifyUrl, setShopifyUrl] = useState("");
  const [shopifyPassword, setShopifyPassword] = useState("");
  const [mappingRows, setMappingRows] = useState<PageMapping[]>([
    { shopify_path: "/", design_url: "" },
  ]);

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

    // Convert rows to { shopify_path: design_url } dict, skip empty rows
    const mappings: Record<string, string> = {};
    for (const row of mappingRows) {
      if (row.shopify_path.trim() && row.design_url.trim()) {
        mappings[row.shopify_path.trim()] = row.design_url.trim();
      }
    }

    const hasMappings = Object.keys(mappings).length > 0;

    const data: ProjectFormData = {
      name,
      shopify_url: shopifyUrl,
      source_type: hasMappings ? "website" : "none",
    };

    if (hasMappings) {
      data.page_mappings = mappings;
    }
    if (shopifyPassword) {
      data.shopify_password = shopifyPassword;
    }

    onSubmit(data);
  };

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
              value={name}
              onChange={(e) => setName(e.target.value)}
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
              value={shopifyUrl}
              onChange={(e) => setShopifyUrl(e.target.value)}
              required
              placeholder="https://mystore.myshopify.com"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Design Reference Pages */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Design Reference Pages{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <p className="text-xs text-gray-400 mb-2">
              Add reference URLs to compare against your Shopify pages. Leave
              empty for AI-only analysis.
            </p>
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
                    placeholder="Design URL (any website)"
                    className="flex-[2] px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  {mappingRows.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeMappingRow(index)}
                      className="px-2 py-2 text-red-500 hover:text-red-700 text-sm"
                      title="Remove row"
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M6 18L18 6M6 6l12 12"
                        />
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

          {/* Optional: Shopify Password */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Shopify Password{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="password"
              value={shopifyPassword}
              onChange={(e) => setShopifyPassword(e.target.value)}
              placeholder="Password-protected store access"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

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
