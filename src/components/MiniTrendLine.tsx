import { TrendingUp } from "lucide-react";

interface MiniTrendLineProps {
  data: number[];
  positive?: boolean;
  width?: number;
  height?: number;
}

const MiniTrendLine = ({ data, positive, width = 60, height = 24 }: MiniTrendLineProps) => {
  if (!data || data.length < 2) return null;

  const isUp = positive ?? data[data.length - 1] > data[0];
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((val - min) / range) * height;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline
        points={points}
        fill="none"
        stroke={isUp ? "hsl(142, 71%, 45%)" : "hsl(0, 72%, 51%)"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

export default MiniTrendLine;
