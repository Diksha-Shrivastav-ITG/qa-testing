import { Link } from "react-router-dom";

interface Project {
  id: number;
  name: string;
  shopify_url: string;
  source_type?: string;
}

interface ProjectCardProps {
  project: Project;
  onRunQA: (id: number) => void;
}

const SOURCE_CONFIG: Record<string, { label: string; bg: string; text: string; border: string }> = {
  figma:  { label: "Figma",   bg: "bg-green-500/10",  text: "text-green-600 dark:text-green-400",  border: "border-green-500/25" },
  none:   { label: "AI",      bg: "bg-purple-500/10", text: "text-purple-600 dark:text-purple-400", border: "border-purple-500/25" },
  framer: { label: "Framer",  bg: "bg-blue-500/10",   text: "text-blue-600 dark:text-blue-400",   border: "border-blue-500/25" },
};

const getSourceConfig = (type: string) =>
  SOURCE_CONFIG[type] ?? { label: type, bg: "bg-gray-100 dark:bg-slate-700/50", text: "text-gray-500 dark:text-slate-400", border: "border-gray-300 dark:border-slate-600" };

const AVATAR_COLORS = [
  "from-violet-500 to-indigo-600",
  "from-emerald-500 to-teal-600",
  "from-rose-500 to-pink-600",
  "from-amber-500 to-orange-600",
  "from-blue-500 to-cyan-600",
];

const getAvatarColor = (name: string) =>
  AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];

const ProjectCard = ({ project, onRunQA }: ProjectCardProps) => {
  const src = getSourceConfig(project.source_type ?? "none");
  const avatarColor = getAvatarColor(project.name);

  return (
    <div className="group bg-white dark:bg-slate-800/50 rounded-2xl border border-gray-200 dark:border-slate-700/60 p-5 flex flex-col gap-4 hover:bg-gray-50 dark:hover:bg-slate-800/70 hover:border-gray-300 dark:hover:border-slate-600/60 hover:-translate-y-0.5 transition-all duration-200 backdrop-blur-sm shadow-sm dark:shadow-none">
      {/* Top row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${avatarColor} flex items-center justify-center shrink-0 shadow-lg`}>
            <span className="text-sm font-bold text-white">{project.name[0]?.toUpperCase()}</span>
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white truncate leading-tight">
              {project.name}
            </h3>
            <p className="text-[11px] text-gray-500 dark:text-slate-500 truncate mt-0.5" title={project.shopify_url}>
              {project.shopify_url}
            </p>
          </div>
        </div>
        <span className={`shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${src.bg} ${src.text} ${src.border}`}>
          {src.label}
        </span>
      </div>

      {/* Divider */}
      <div className="border-t border-gray-200 dark:border-slate-700/50" />

      {/* Actions */}
      <div className="flex items-center gap-2 mt-auto">
        <button
          onClick={() => onRunQA(project.id)}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold text-white bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl hover:from-violet-700 hover:to-indigo-700 shadow-lg shadow-violet-500/20 transition-all"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
          </svg>
          Run QA
        </button>
        <Link
          to={`/projects/${project.id}`}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold text-gray-600 dark:text-slate-300 border border-gray-300 dark:border-slate-700 rounded-xl hover:bg-gray-100 dark:hover:bg-slate-700/50 hover:text-gray-900 dark:hover:text-white transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Details
        </Link>
      </div>
    </div>
  );
};

export default ProjectCard;
