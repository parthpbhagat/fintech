import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Newspaper } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { fetchIBBIRecentAnnouncements } from "@/services/ibbiService";
import NewsDialog from "@/components/NewsDialog";
import type { NewsItem } from "@/data/types";

const NewsPage = () => {
  const navigate = useNavigate();
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const { data: announcements = [], isLoading } = useQuery({
    queryKey: ["ibbi-recent-announcements"],
    queryFn: () => fetchIBBIRecentAnnouncements(18),
  });

  return (
    <div className="min-h-screen bg-background">
      <div className="bg-card border-b px-4 py-4">
        <div className="max-w-[1400px] mx-auto flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <Newspaper className="w-5 h-5 text-primary" />
          <h1 className="text-xl font-bold">IBBI News & Updates</h1>
        </div>
      </div>
      <div className="max-w-[1400px] mx-auto px-4 py-6">
        {isLoading ? (
          <div className="py-20 text-center text-muted-foreground">Loading live IBBI announcements...</div>
        ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {announcements.map(n => (
            <button
              key={n.id}
              onClick={() => setSelectedNews(n)}
              className="data-card text-left hover:shadow-md transition-shadow"
            >
              <p className="font-medium text-sm mb-2">{n.title}</p>
              <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{n.summary}</p>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
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
