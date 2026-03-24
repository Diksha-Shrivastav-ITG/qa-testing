import { NavLink } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

const Sidebar = () => {
  const { role, logout } = useAuth();

  return (
    <div className="w-64 min-h-screen bg-gray-900 text-white flex flex-col">
      {/* App name */}
      <div className="p-6 border-b border-gray-700">
        <h1 className="text-xl font-bold text-white">Shopify QA AI</h1>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `block px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              isActive
                ? "bg-indigo-600 text-white"
                : "text-gray-300 hover:bg-gray-800 hover:text-white"
            }`
          }
        >
          Projects
        </NavLink>

        {role === "admin" && (
          <NavLink
            to="/admin/users"
            className={({ isActive }) =>
              `block px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-indigo-600 text-white"
                  : "text-gray-300 hover:bg-gray-800 hover:text-white"
              }`
            }
          >
            User Management
          </NavLink>
        )}
      </nav>

      {/* User info at bottom */}
      <div className="p-4 border-t border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-gray-300">Role:</span>
          <span
            className={`text-xs px-2 py-1 rounded-full font-medium ${
              role === "admin"
                ? "bg-red-600 text-white"
                : "bg-indigo-600 text-white"
            }`}
          >
            {role ?? "user"}
          </span>
        </div>
        <button
          onClick={logout}
          className="w-full px-4 py-2 text-sm text-gray-300 border border-gray-600 rounded-lg hover:bg-gray-800 hover:text-white transition-colors"
        >
          Logout
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
