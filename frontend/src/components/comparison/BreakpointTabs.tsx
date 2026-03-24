const BREAKPOINTS = [375, 425, 768, 1024, 1280, 1440, 1920];

interface BreakpointTabsProps {
  activeBreakpoint: number;
  onSelect: (bp: number) => void;
}

const BreakpointTabs = ({ activeBreakpoint, onSelect }: BreakpointTabsProps) => {
  return (
    <div className="flex flex-wrap gap-1">
      {BREAKPOINTS.map((bp) => (
        <button
          key={bp}
          onClick={() => onSelect(bp)}
          className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
            activeBreakpoint === bp
              ? "bg-blue-600 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          {bp}px
        </button>
      ))}
    </div>
  );
};

export default BreakpointTabs;
