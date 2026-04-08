import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listProjects, createProject } from "../api/projects";
import { startRun } from "../api/runs";
import type { PageConfig } from "../api/runs";
import ProjectCard from "../components/projects/ProjectCard";
import ProjectForm from "../components/projects/ProjectForm";
import RunQAModal from "../components/runs/RunQAModal";

interface Project {
  id: number;
  name: string;
  shopify_url: string;
  source_type: string;
}

interface ProjectFormData {
  name: string;
  shopify_url: string;
  source_type: string;
  source_url?: string;
  shopify_password?: string;
  figma_token?: string;
}

const ProjectsPage = () => {
  const [showForm, setShowForm] = useState(false);
  const [runModalProjectId, setRunModalProjectId] = useState<number | null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(1, 20).then((res) => res.data),
  });

  const createMutation = useMutation({
    mutationFn: (formData: ProjectFormData) => createProject(formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setShowForm(false);
    },
  });

  const runMutation = useMutation({
    mutationFn: ({
      projectId,
      pageConfigs,
      testMode,
      testTypes,
      pages,
    }: {
      projectId: number;
      pageConfigs?: PageConfig[];
      testMode: "design" | "ai";
      testTypes?: string[];
      pages?: string;
    }) => startRun(projectId, pageConfigs, testMode, testTypes, pages),
    onSuccess: (res) => {
      setRunModalProjectId(null);
      navigate(`/runs/${res.data.id}`);
    },
  });

  const projects: Project[] = data?.items ?? [];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">Projects</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-0.5">
            {projects.length > 0 ? `${projects.length} project${projects.length !== 1 ? "s" : ""}` : "Manage your Shopify QA projects"}
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl hover:from-violet-700 hover:to-indigo-700 shadow-lg shadow-violet-500/25 hover:shadow-violet-500/40 transition-all"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Project
        </button>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <div className="w-8 h-8 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
          <p className="text-gray-500 dark:text-slate-400 text-sm">Loading projects...</p>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
            <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
          </div>
          <p className="text-red-400 font-medium">Failed to load projects.</p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && projects.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/10 to-indigo-500/10 border border-violet-500/20 flex items-center justify-center mb-5">
            <svg className="w-8 h-8 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-1">No projects yet</h3>
          <p className="text-gray-600 dark:text-slate-500 text-sm mb-6 max-w-xs">
            Create your first project to start running AI-powered QA checks on your Shopify store.
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl hover:from-violet-700 hover:to-indigo-700 shadow-lg shadow-violet-500/25 transition-all"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            New Project
          </button>
        </div>
      )}

      {/* Projects grid */}
      {!isLoading && !isError && projects.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {projects.map((project: Project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onRunQA={(id) => setRunModalProjectId(id)}
            />
          ))}
        </div>
      )}

      {/* Project form modal */}
      {showForm && (
        <ProjectForm
          onSubmit={(data) => createMutation.mutate(data)}
          onCancel={() => setShowForm(false)}
          isLoading={createMutation.isPending}
        />
      )}

      {/* Run QA modal */}
      {runModalProjectId !== null && (
        <RunQAModal
          onConfirm={(pageConfigs, testMode, testTypes, pages) =>
            runMutation.mutate({ projectId: runModalProjectId, pageConfigs, testMode, testTypes, pages })
          }
          onCancel={() => setRunModalProjectId(null)}
          isLoading={runMutation.isPending}
          sourceType={projects.find((p) => p.id === runModalProjectId)?.source_type ?? "none"}
        />
      )}
    </div>
  );
};

export default ProjectsPage;
