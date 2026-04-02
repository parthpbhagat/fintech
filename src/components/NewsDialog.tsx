import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { NewsItem } from "@/data/types";
import { Newspaper, ExternalLink, Calendar } from "lucide-react";

interface NewsDialogProps {
  news: NewsItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const NewsDialog = ({ news, open, onOpenChange }: NewsDialogProps) => {
  if (!news) return null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-start gap-2 text-lg leading-tight">
            <Newspaper className="w-5 h-5 text-primary shrink-0 mt-0.5" />
            {news.title}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span className="font-medium text-primary">{news.source}</span>
            <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{news.date}</span>
          </div>
          <p className="text-sm leading-relaxed text-foreground">{news.summary}</p>
          <a href={news.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
            Read full article <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default NewsDialog;
