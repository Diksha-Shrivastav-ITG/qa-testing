import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listProjects, createProject } from "../api/projects";
import { startRun } from "../api/runs";
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
    mutationFn: ({ projectId, pages, testMode }: { projectId: number; pages?: string; testMode?: "design" | "ai" }) =>
      startRun(projectId, pages || undefined, testMode || "design"),
    onSuccess: (res) => {
      setRunModalProjectId(null);
      navigate(`/runs/${res.data.id}`);
    },
  });

  const projects: Project[] = data?.items ?? [];

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
        >
          + New Project
        </button>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="text-gray-500">Loading projects...</div>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="flex items-center justify-center py-16">
          <div className="text-red-500">Failed to load projects.</div>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && projects.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="text-gray-400 text-lg mb-2">No projects yet</div>
          <p className="text-gray-500 text-sm mb-6">
            Create your first project to start running QA checks.
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
          >
            + New Project
          </button>
        </div>
      )}

      {/* Projects grid */}
      {!isLoading && !isError && projects.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
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
          onConfirm={(pages, testMode) =>
            runMutation.mutate({ projectId: runModalProjectId, pages, testMode })
          }
          onCancel={() => setRunModalProjectId(null)}
          isLoading={runMutation.isPending}
        />
      )}
    </div>
  );
};

export default ProjectsPage;
