import React, { useState, useEffect } from "react";
import { Plus, Minus } from "lucide-react";
import { DEFAULT_LIST_LIMIT } from "@/data/types";

interface ShowMoreContainerProps<T> {
  items: T[];
  renderItems: (visibleItems: T[]) => React.ReactNode;
  initialLimit?: number;
  increment?: number;
  label?: string;
  className?: string;
}

export const ShowMoreContainer = <T,>({
  items,
  renderItems,
  initialLimit = DEFAULT_LIST_LIMIT,
  increment = 10,
  label = "Items",
  className = "",
}: ShowMoreContainerProps<T>) => {
  const [limit, setLimit] = useState(initialLimit);
  
  useEffect(() => {
    setLimit(initialLimit);
  }, [items, initialLimit]);

  if (!items || items.length === 0) {
    return <div className={className}>{renderItems([])}</div>;
  }

  const visibleItems = items.slice(0, limit);
  const hasMore = items.length > limit;
  const isExpanded = limit > initialLimit;

  return (
    <div className={`space-y-6 ${className}`}>
      {renderItems(visibleItems)}

      {(hasMore || isExpanded) && (
        <div className="flex flex-col items-center gap-3 pt-2">
          {hasMore && (
            <button
              onClick={() => setLimit((prev) => prev + increment)}
              className="px-6 py-2.5 bg-primary/10 border border-primary/30 text-primary rounded-full text-[10px] font-black uppercase tracking-[0.2em] hover:bg-primary hover:text-white transition-all shadow-sm active:scale-95 flex items-center gap-2 group"
            >
              <Plus className="w-3.5 h-3.5 group-hover:rotate-90 transition-transform duration-300" />
              Show More {label}
            </button>
          )}

          {isExpanded && (
            <button
              onClick={() => setLimit(initialLimit)}
              className="px-6 py-2.5 bg-slate-50 border border-slate-200 text-slate-400 rounded-full text-[10px] font-black uppercase tracking-[0.2em] hover:bg-slate-100 hover:text-slate-600 transition-all shadow-sm active:scale-95 flex items-center gap-2"
            >
              <Minus className="w-3.5 h-3.5" />
              Show Less
            </button>
          )}
        </div>
      )}
    </div>
  );
};
