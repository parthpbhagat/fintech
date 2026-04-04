import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Newspaper } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { fetchIBBIRecentAnnouncements, fetchIBBIStats } from "@/services/ibbiService";
import NewsDialog from "@/components/NewsDialog";
import type { NewsItem } from "@/data/types";

const NewsPage = () => {
  const navigate = useNavigate();
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const {
    data: announcements = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ["ibbi-recent-announcements"],
    queryFn: () => fetchIBBIRecentAnnouncements(18),
    retry: false,
  });
  const { data: stats } = useQuery({
    queryKey: ["ibbi-news-stats"],
    queryFn: fetchIBBIStats,
    retry: false,
  });
  const isRegistryDegraded = stats?.ibbiStatus === "degraded";

  return (
    <div className="min-h-screen bg-background">
      <div className="sticky top-0 z-30 bg-card/95 border-b px-4 py-3 backdrop-blur">
        <div className="max-w-[1400px] mx-auto flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <Newspaper className="w-5 h-5 text-primary" />
          <h1 className="text-lg font-bold">IBBI News & Updates</h1>
        </div>
      </div>
      <div className="max-w-[1400px] mx-auto px-4 py-4">
        {isLoading ? (
          <div className="py-20 text-center text-muted-foreground">Loading live IBBI announcements...</div>
        ) : error instanceof Error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-6 py-8 text-center text-sm text-red-700">
            News load na thai. {error.message}
          </div>
        ) : isRegistryDegraded && announcements.length === 0 ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-6 py-8 text-center text-sm text-amber-800">
            Live IBBI announcement feed atyaare unavailable chhe, etle news empty dekhay chhe.
            {stats?.ibbiError ? <div className="mt-2 text-xs text-amber-700">{stats.ibbiError}</div> : null}
          </div>
        ) : announcements.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center text-sm text-slate-500">
            Aaje sudhi no koi live announcement available nathi.
          </div>
        ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {announcements.map(n => (
            <button
              key={n.id}
              onClick={() => setSelectedNews(n)}
              className="data-card text-left hover:shadow-md transition-shadow p-3"
            >
              <p className="font-medium text-xs mb-1.5 line-clamp-2">{n.title}</p>
              <p className="text-[11px] text-muted-foreground line-clamp-2 mb-2">{n.summary}</p>
              <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                <span className="text-primary font-medium">{n.source}</span>
                <span>{n.date}</span>
              </div>
            </button>
          ))}
        </div>
        )}
      </div>
      <NewsDialog news={selectedNews} open={!!selectedNews} onOpenChange={(o) => !o && setSelectedNews(null)} />
    </div>
  );
};

export default NewsPage;
