import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

export interface InsightFact {
  label: string;
  value: string;
}

export interface InsightSection {
  title: string;
  facts: InsightFact[];
}

export interface InsightContent {
  title: string;
  subtitle?: string;
  description?: string;
  facts?: InsightFact[];
  sections?: InsightSection[];
}

interface DataInsightSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  content: InsightContent | null;
}

const DataInsightSheet = ({ open, onOpenChange, content }: DataInsightSheetProps) => (
  <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent side="right" className="w-full overflow-y-auto border-l border-slate-200 bg-white sm:max-w-xl">
      {content && (
        <div className="space-y-6">
          <SheetHeader className="space-y-3">
            <div className="inline-flex w-fit rounded-full bg-[#81BC06]/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.2em] text-[#81BC06]">
              Quick Insight
            </div>
            <SheetTitle className="text-left text-2xl font-black text-slate-900">{content.title}</SheetTitle>
            {content.subtitle && <p className="text-sm font-bold text-slate-500">{content.subtitle}</p>}
            {content.description && (
              <SheetDescription className="text-left text-sm leading-7 text-slate-600">
                {content.description}
              </SheetDescription>
            )}
          </SheetHeader>

          {(content.facts || []).length > 0 && (
            <div className="grid gap-3">
              {content.facts?.map((fact) => (
                <div key={`${fact.label}-${fact.value}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">{fact.label}</p>
                  <p className="mt-2 break-words text-sm font-bold text-slate-900">{fact.value || "N/A"}</p>
                </div>
              ))}
            </div>
          )}

          {(content.sections || []).length > 0 && (
            <div className="space-y-4">
              {content.sections?.map((section) => (
                <div key={section.title} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <h3 className="text-sm font-black uppercase tracking-[0.18em] text-slate-700">{section.title}</h3>
                  <div className="mt-4 grid gap-3">
                    {section.facts.map((fact) => (
                      <div key={`${section.title}-${fact.label}-${fact.value}`} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">{fact.label}</p>
                        <p className="mt-2 break-words text-sm font-bold text-slate-900">{fact.value || "N/A"}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </SheetContent>
  </Sheet>
);

export default DataInsightSheet;
