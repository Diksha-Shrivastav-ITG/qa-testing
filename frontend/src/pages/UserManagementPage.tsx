import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../api/client";

interface User {
  id: number;
  name?: string;
  email: string;
  role: string;
  created_at: string;
}

interface UsersResponse {
  users: User[];
}

const fetchUsers = () =>
  api.get<UsersResponse | User[]>("/api/users").then((res) => res.data);

const roleBadge = (role: string) => {
  switch (role.toLowerCase()) {
    case "admin":
      return "bg-purple-100 text-purple-700";
    case "editor":
      return "bg-blue-100 text-blue-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
};

const UserManagementPage = () => {
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery<UsersResponse | User[]>({
    queryKey: ["users"],
    queryFn: fetchUsers,
    retry: false,
  });

  const users: User[] = Array.isArray(data)
    ? data
    : (data as UsersResponse)?.users ?? [];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="text-sm text-gray-500 hover:text-gray-700 mb-1 flex items-center gap-1"
          >
            &larr; Back
          </button>
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          <p className="text-sm text-gray-500 mt-0.5">Admin access only</p>
        </div>
      </div>

      {/* Table card */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {isLoading && (
          <div className="py-12 text-center text-sm text-gray-500">
            Loading users...
          </div>
        )}

        {isError && (
          <div className="py-12 text-center">
            <p className="text-sm text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 inline-block">
              Could not load users — the <code className="font-mono">/api/users</code>{" "}
              endpoint may not be available yet.
            </p>
          </div>
        )}

        {!isLoading && !isError && users.length === 0 && (
          <div className="py-12 text-center text-sm text-gray-400">
            No users found.
          </div>
        )}

        {!isLoading && !isError && users.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Name
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Email
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Role
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {user.name ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{user.email}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${roleBadge(
                        user.role
                      )}`}
                    >
                      {user.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {new Date(user.created_at).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs text-gray-400 mt-3">
        Note: Role editing is not yet available — a PATCH endpoint is required.
      </p>
    </div>
  );
};

export default UserManagementPage;
