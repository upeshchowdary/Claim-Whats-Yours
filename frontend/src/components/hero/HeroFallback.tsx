const CENTER = { x: 200, y: 200 };
const RADIUS = 150;

const LABELS = [
  "Education",
  "Healthcare",
  "Housing",
  "Agriculture",
  "Pensions",
  "Livelihoods",
  "Women and child",
  "Employment",
  "Other",
];

const NODES = LABELS.map((label, index) => {
  const angle = (index / LABELS.length) * Math.PI * 2 - Math.PI / 2;
  return {
    label,
    x: CENTER.x + RADIUS * Math.cos(angle),
    y: CENTER.y + RADIUS * Math.sin(angle),
  };
});

/** Static SVG stand-in for the 3D hero. Used when WebGL, motion or viewport gating rules out the scene. */
export function HeroFallback() {
  return (
    <div aria-hidden="true" className="h-full w-full">
      <svg viewBox="0 0 400 400" className="h-full w-full" role="presentation">
        {NODES.map((node) => (
          <line
            key={`spoke-${node.label}`}
            x1={CENTER.x}
            y1={CENTER.y}
            x2={node.x}
            y2={node.y}
            style={{ stroke: "var(--border)" }}
            strokeWidth={1}
          />
        ))}
        {NODES.map((node, index) => {
          const next = NODES[(index + 1) % NODES.length];
          return (
            <line
              key={`ring-${node.label}`}
              x1={node.x}
              y1={node.y}
              x2={next.x}
              y2={next.y}
              style={{ stroke: "var(--border)" }}
              strokeWidth={1}
            />
          );
        })}
        <circle
          cx={CENTER.x}
          cy={CENTER.y}
          r={28}
          style={{ fill: "var(--primary)" }}
        />
        {NODES.map((node) => (
          <g key={`node-${node.label}`}>
            <circle
              cx={node.x}
              cy={node.y}
              r={9}
              style={{ fill: "var(--accent)" }}
            />
            <text
              x={node.x}
              y={node.y - 16}
              textAnchor="middle"
              fontSize={12}
              style={{ fill: "var(--primary)" }}
            >
              {node.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
