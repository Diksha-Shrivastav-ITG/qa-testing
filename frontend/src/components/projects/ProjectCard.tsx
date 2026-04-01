import { Link } from "react-router-dom";

interface Project {
  id: number;
  name: string;
  shopify_url: string;
  source_type: string;
}

interface ProjectCardProps {
  project: Project;
  onRunQA: (id: number) => void;
}

const sourceTypeBadge = (sourceType: string) => {
  if (sourceType === "figma") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
        Figma
      </span>
    );
  }
  if (sourceType === "website") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
        Website
      </span>
    );
  }
  if (sourceType === "none") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
        AI Only
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
      Framer
    </span>
  );
};

const ProjectCard = ({ project, onRunQA }: ProjectCardProps) => {
  const truncateUrl = (url: string, maxLen = 40) =>
    url.length > maxLen ? url.slice(0, maxLen) + "..." : url;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex flex-col gap-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-lg font-semibold text-gray-900 truncate">
          {project.name}
        </h3>
        {sourceTypeBadge(project.source_type)}
      </div>

      <p
        className="text-sm text-gray-500 truncate"
        title={project.shopify_url}
      >
        {truncateUrl(project.shopify_url)}
      </p>

      <div className="flex items-center gap-3 mt-auto">
        <button
          onClick={() => onRunQA(project.id)}
          className="flex-1 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
        >
          Run QA
        </button>
        <Link
          to={`/projects/${project.id}`}
          className="flex-1 px-4 py-2 text-sm font-medium text-center text-indigo-600 border border-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors"
        >
          View
        </Link>
      </div>
    </div>
  );
};

export default ProjectCard;
