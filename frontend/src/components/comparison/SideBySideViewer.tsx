import { useState } from "react";

type ZoomLevel = 100 | 150 | 200;

interface SideBySideViewerProps {
  designImageUrl?: string;
  shopifyImageUrl?: string;
  diffOverlayUrl?: string;
}

const SideBySideViewer = ({
  designImageUrl,
  shopifyImageUrl,
  diffOverlayUrl,
}: SideBySideViewerProps) => {
  const [zoom, setZoom] = useState<ZoomLevel>(100);
  const [showOverlay, setShowOverlay] = useState(false);

  const zoomStyle = {
    width: `${zoom}%`,
    minWidth: zoom > 100 ? `${zoom}%` : undefined,
  };

  const ImagePanel = ({
    url,
    label,
  }: {
    url?: string;
    label: string;
  }) => (
    <div className="flex-1 min-w-0 flex flex-col gap-2">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
        {label}
      </div>
      <div className="overflow-auto border border-gray-200 rounded bg-gray-50 relative" style={{ maxHeight: "600px" }}>
        {url ? (
          <div style={zoomStyle} className="relative">
            <img
              src={url}
              alt={label}
              className="w-full object-contain"
            />
            {showOverlay && diffOverlayUrl && label === "Shopify" && (
              <img
                src={diffOverlayUrl}
                alt="Diff overlay"
                className="absolute inset-0 w-full h-full object-contain opacity-60 pointer-events-none"
              />
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
            No screenshot available
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1">
          <span className="text-xs text-gray-500 mr-1">Zoom:</span>
          {([100, 150, 200] as ZoomLevel[]).map((z) => (
            <button
              key={z}
              onClick={() => setZoom(z)}
              className={`px-2 py-1 text-xs rounded font-medium transition-colors ${
                zoom === z
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {z}%
            </button>
          ))}
        </div>
        {diffOverlayUrl && (
          <button
            onClick={() => setShowOverlay((v) => !v)}
            className={`px-2 py-1 text-xs rounded font-medium transition-colors ${
              showOverlay
                ? "bg-orange-500 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {showOverlay ? "Hide Diff" : "Show Diff"}
          </button>
        )}
      </div>

      {/* Panels */}
      <div className="flex gap-4">
        <ImagePanel url={designImageUrl} label="Design" />
        <ImagePanel url={shopifyImageUrl} label="Shopify" />
      </div>
    </div>
  );
};

export default SideBySideViewer;
