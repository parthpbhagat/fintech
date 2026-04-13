import { useState, useMemo, useEffect } from "react";
import {
  Download,
  ChevronRight,
  FileText,
  FileJson,
  Globe,
  ExternalLink,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Filter,
  CheckCircle2,
  Plus,
  User as UserIcon,
  Landmark,
  MapPin,
  BadgeCheck,
  ChevronLeft,
  ArrowRight,
  BarChart2,
  Table as TableIcon,
  Info,
  Trash2,
  Link as LinkIcon,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  Cell
} from "recharts";
import { useQuery } from "@tanstack/react-query";
import type { Company, CorporateProcessRow, CorporateProcessSection } from "@/data/types";
import {
  API_BASE_URL,
  fetchIBBICompanyDetails,
  fetchProfessionalDetails,
  fetchProfessionalMetadata,
  updateProfessionalMetadata
} from "@/services/ibbiService";

interface IBBICorporateProcessProps {
  company: Company;
}

// ── Format amounts to Crores ────────────────────────────────────────────────
const formatToCr = (amount?: number) => {
  if (amount === undefined || amount === null || amount === 0) return "0.00 Cr";
  const cr = amount / 10000000;
  return `₹ ${cr.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Cr`;
};

// ── Resolve relative backend doc URLs ──────────────────────────────────────

const resolveDocUrl = (url?: string): string => {
  if (!url) return "#";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${API_BASE_URL}${url}`;
};

// ── Convert hyphenated slug filename to readable title ─────────────────────
const prettifyFileName = (fileName: string): string => {
  // Remove extension
  const withoutExt = fileName.replace(/\.[^/.]+$/, "");
  // Replace hyphens/underscores with spaces and trim
  const spaced = withoutExt.replace(/[-_]+/g, " ").trim();
  // Title-case: first letter of each word uppercase
  return spaced.replace(/\b\w/g, (c) => c.toUpperCase());
};

// ── Force-download a file as blob (handles cross-origin PDFs) ──────────────
const downloadPdf = async (url: string, fileName: string) => {
  try {
    const res = await fetch(url, { mode: "cors" });
    if (!res.ok) throw new Error("fetch failed");
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(blobUrl);
  } catch {
    // Fallback: open in new tab if CORS/network blocks direct fetch
    window.open(url, "_blank", "noreferrer");
  }
};

// ── Detect real file type from fileType field or URL extension ──────────────
const getFileInfo = (doc: { fileType?: string; url?: string; fileName: string }) => {
  const ft = doc.fileType || "";
  const urlLower = (doc.url || "").toLowerCase();
  const nameLower = doc.fileName.toLowerCase();

  if (ft === "pdf" || nameLower.endsWith(".pdf") || urlLower.includes(".pdf"))
    return { label: "PDF", color: "bg-red-600 hover:bg-red-700", icon: <FileText className="w-3.5 h-3.5" /> };
  if (ft === "json" || nameLower.endsWith(".json"))
    return { label: "JSON", color: "bg-blue-600 hover:bg-blue-700", icon: <FileJson className="w-3.5 h-3.5" /> };
  if (ft === "txt" || nameLower.endsWith(".txt"))
    return { label: "TXT", color: "bg-slate-600 hover:bg-slate-700", icon: <FileText className="w-3.5 h-3.5" /> };
  if (ft === "html" || nameLower.endsWith(".html") || urlLower.includes("ibbi.gov.in"))
    return { label: "View", color: "bg-amber-600 hover:bg-amber-700", icon: <Globe className="w-3.5 h-3.5" /> };
  return { label: "Open", color: "bg-slate-500 hover:bg-slate-600", icon: <ExternalLink className="w-3.5 h-3.5" /> };
};

// ── Sub-components ──────────────────────────────────────────────────────────
const TabLoader = () => (
  <div className="py-12 flex flex-col items-center gap-3 text-slate-400">
    <Loader2 className="w-6 h-6 animate-spin" />
    <p className="text-sm">Loading data...</p>
  </div>
);

const TabError = ({ message }: { message: string }) => (
  <div className="py-12 flex flex-col items-center gap-3 text-amber-600">
    <AlertTriangle className="w-6 h-6" />
    <p className="text-sm text-center max-w-md">{message}</p>
  </div>
);

const EmptyTab = ({ tab }: { tab: string }) => (
  <div className="py-14 text-center border border-dashed border-slate-200 rounded bg-slate-50 text-slate-400">
    No data currently available for the{" "}
    <strong className="text-slate-600">{tab}</strong> section.
  </div>
);

const renderLinkedCell = (header: string, row: CorporateProcessRow) => {
  const values = row.values ?? {};
  const links = row.links ?? {};
  const value = values[header] || "-";
  const link = links[header];

  if (!link) {
    return <span>{value || "-"}</span>;
  }

  const isPdf = link.toLowerCase().includes(".pdf");
  return (
    <a
      href={resolveDocUrl(link)}
      target="_blank"
      rel="noreferrer"
      className={`inline-flex items-center gap-1 ${isPdf ? "text-red-600 hover:text-red-700" : "text-blue-600 hover:text-blue-700"} underline`}
    >
      <span>{value || (isPdf ? "PDF" : "Open")}</span>
      <ExternalLink className="w-3 h-3" />
    </a>
  );
};

const ProcessTable = ({ section }: { section: CorporateProcessSection }) => {
  if (!section.rows.length) {
    return <EmptyTab tab={section.title} />;
  }

  return (
    <div className="overflow-x-auto border border-slate-300 rounded">
      <table className="w-full text-left text-sm min-w-[820px]">
        <thead className="bg-[#002D62] text-white">
          <tr>
            {section.headers.map((header) => (
              <th key={header} className="p-2.5 font-bold border-r border-blue-700 last:border-r-0">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {section.rows.map((row) => (
            <tr key={row.id} className="border-b border-slate-200 last:border-0 hover:bg-slate-50 align-top">
              {section.headers.map((header) => (
                <td key={`${row.id}-${header}`} className="p-2.5 border-r border-slate-200 last:border-r-0 text-slate-700 text-xs">
                  {renderLinkedCell(header, row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// ── Assignment Analytics Summary Component ──────────────────────────────────
const AssignmentAnalyticsSummary = ({ data }: { data: any[] }) => {
  const summary = useMemo(() => {
    if (!data || data.length === 0) return null;

    const rows = data.filter(r => r && (r.Year || r.Particulars) && r.Year !== "Total" && r.Particulars !== "Total");
    if (rows.length === 0) return null;

    const total = rows.reduce((acc, r) => acc + (parseInt(String(r.Total).replace(/[^\d]/g, "")) || 0), 0);
    const roles = ["IRP", "RP", "Liquidator", "Voluntary Liquidator", "RP for Pre-pack"];
    const roleCounts = roles.map(role => ({
      role,
      count: rows.reduce((acc, r) => acc + (parseInt(String(r[role]).replace(/[^\d]/g, "")) || 0), 0)
    }));

    const topRole = roleCounts.sort((a, b) => b.count - a.count)[0];
    const years = rows.map(r => r.Year || r.Particulars).sort();
    const activeSpan = years.length > 1 ? `${years[0]} - ${years[years.length - 1]}` : years[0];

    return {
      total,
      topRole,
      activeSpan,
      recentYear: years[years.length - 1]
    };
  }, [data]);

  if (!summary) return null;

  return (
    <div className="bg-gradient-to-r from-[#002D62] to-[#004a8f] p-5 rounded-xl text-white shadow-lg mb-6 border-l-4 border-[#81BC06]">
      <div className="flex items-start gap-4">
        <div className="bg-white/10 p-3 rounded-lg flex-shrink-0">
          <Info className="w-5 h-5 text-[#81BC06]" />
        </div>
        <div className="space-y-1">
          <h5 className="text-[10px] font-black uppercase tracking-[0.2em] text-blue-200/70">Overall Professional Insight</h5>
          <p className="text-sm font-medium leading-relaxed">
            This professional has handled <span className="text-[#81BC06] font-bold">{summary.total}</span> total assignments
            across <span className="font-bold">{summary.activeSpan}</span>. Their most frequent role is as a
            <span className="text-yellow-400 font-bold"> {summary.topRole.role}</span> ({summary.topRole.count} cases).
            Ongoing activity was observed as recently as <span className="font-bold">{summary.recentYear}</span>.
          </p>
        </div>
      </div>
    </div>
  );
};

// ── Main Component ──────────────────────────────────────────────────────────
// ── Assignment Analytics Graph Component ─────────────────────────────────────
const AssignmentAnalyticsGraph = ({ data }: { data: any[] }) => {
  // Prep data for Recharts (remove Total, convert to numbers)
  const chartData = useMemo(() => {
    return data
      .filter(row => row && (row.Year || row.Particulars) && (row.Year !== "Total" && row.Particulars !== "Total"))
      .map(row => ({
        name: row.Year || row.Particulars,
        IRP: parseInt(String(row.IRP).replace(/[^\d]/g, "")) || 0,
        RP: parseInt(String(row.RP).replace(/[^\d]/g, "")) || 0,
        Liquidator: parseInt(String(row.Liquidator).replace(/[^\d]/g, "")) || 0,
        "Voluntary Liquidator": parseInt(String(row["Voluntary Liquidator"]).replace(/[^\d]/g, "")) || 0,
        "RP for Pre-pack": parseInt(String(row["RP for Pre-pack"]).replace(/[^\d]/g, "")) || 0,
      }))
      .reverse(); // Chronological order
  }, [data]);

  const roles = ["IRP", "RP", "Liquidator", "Voluntary Liquidator", "RP for Pre-pack"];
  const colors = ["#002D62", "#81BC06", "#F5B841", "#6366f1", "#ec4899"];

  return (
    <div className="h-[350px] w-full pt-4">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
          <XAxis
            dataKey="name"
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#64748B", fontSize: 10, fontWeight: 700 }}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#64748B", fontSize: 10 }}
          />
          <RechartsTooltip
            cursor={{ fill: "#F8FAFC" }}
            contentStyle={{ borderRadius: "12px", border: "none", boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1)" }}
          />
          <Legend
            verticalAlign="top"
            align="right"
            iconType="circle"
            wrapperStyle={{ paddingBottom: "20px", fontSize: "10px", fontWeight: 700, textTransform: "uppercase" }}
          />
          {roles.map((role, i) => (
            <Bar key={role} dataKey={role} stackId="a" fill={colors[i]} radius={i === 0 ? [0, 0, 0, 0] : i === roles.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

// ── Required Links Section Component ──────────────────────────────────────────
const RequiredLinksView = ({ metadata, onAdd, onDelete }: { metadata: any, onAdd: (l: string, u: string) => void, onDelete: (id: number) => void }) => {
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");

  return (
    <div className="space-y-6">
      <div className="bg-slate-50 p-6 rounded-xl border border-slate-200 shadow-sm">
        <h5 className="text-xs font-black uppercase text-slate-500 mb-4 flex items-center gap-2 tracking-widest">
          <Plus className="w-3 h-3" /> Add Required Document / Link
        </h5>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label className="text-[10px] uppercase font-bold text-slate-400 px-1 italic">Link Label</label>
            <input
              type="text"
              placeholder="e.g. Compliance Certificate"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-[#81BC06] focus:border-transparent outline-none transition-all"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] uppercase font-bold text-slate-400 px-1 italic">Reference URL</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-300" />
                <input
                  type="url"
                  placeholder="https://..."
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className="w-full pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-[#81BC06] focus:border-transparent outline-none transition-all"
                />
              </div>
              <button
                onClick={() => { if (label && url) { onAdd(label, url); setLabel(""); setUrl(""); } }}
                className="bg-[#81BC06] text-white px-6 rounded-lg font-black text-[10px] uppercase shadow-md shadow-[#81BC06]/20 hover:bg-[#72a605] transform hover:-translate-y-0.5 transition-all active:translate-y-0"
              >
                Attach
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <h5 className="text-[10px] font-black uppercase text-slate-400 tracking-widest flex items-center gap-2">
          <LinkIcon className="w-3 h-3" /> Attached Documents ({metadata?.links?.length || 0})
        </h5>
        {metadata?.links?.length > 0 ? (
          <div className="grid gap-3">
            {metadata.links.map((item: any) => (
              <div key={item.id} className="flex items-center justify-between p-4 bg-white border border-slate-200 rounded-xl hover:border-blue-200 hover:shadow-md transition-all group">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center text-blue-600 transition-colors group-hover:bg-blue-600 group-hover:text-white">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <h6 className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors">{item.label}</h6>
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-slate-400 hover:text-blue-500 hover:underline flex items-center gap-1"
                    >
                      {item.url} <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
                <button
                  onClick={() => onDelete(item.id)}
                  className="p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-20 text-center border-2 border-dashed border-slate-100 rounded-2xl bg-slate-50/50">
            <LinkIcon className="w-12 h-12 text-slate-200 mx-auto mb-4" />
            <p className="text-slate-400 font-medium">No external documents attached yet.</p>
          </div>
        )}
      </div>
    </div>
  );
};

const IBBICorporateProcess = ({ company }: IBBICorporateProcessProps) => {
  const [activeTab, setActiveTab] = useState("Details About CD");
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [selectedDesignation, setSelectedDesignation] = useState("All");
  const [refreshStatus, setRefreshStatus] = useState<"idle" | "loading" | "success">("idle");
  const [selectedProf, setSelectedProf] = useState<string | null>(null);
  const [profData, setProfData] = useState<any | null>(null);
  const [profMetadata, setProfMetadata] = useState<any>({ links: [] });
  const [isLoadingProf, setIsLoadingProf] = useState(false);
  const [activeProfTab, setActiveProfTab] = useState<string>("IP Detail");
  const [analyticsViewMode, setAnalyticsViewMode] = useState<"table" | "graph">("table");

  // ── Background Sync for Professionals ─────────────────────────────────────
  useEffect(() => {
    // Only sync if we have a list of professionals and aren't viewing one
    const ips = company.insolvencyProfessionals || [];
    if (!selectedProf && ips.length > 0) {
      const syncProfessionals = async () => {
        const profsToSync = ips.slice(0, 10); // Sync first 10 for performance

        console.log(`[SYNC] Starting background sync for ${profsToSync.length} professionals...`);

        for (const name of profsToSync) {
          try {
            // Check React Query cache or just hit the API silently
            // The backend now has its own cache, so this is fast
            await fetchProfessionalDetails(name);
            await new Promise(r => setTimeout(r, 1500)); // Be gentle with IBBI
          } catch (e) {
            console.warn(`[SYNC] Failed to pre-fetch ${name}`);
          }
        }
        console.log("[SYNC] Background sync complete.");
      };

      const timer = setTimeout(syncProfessionals, 3000); // Wait 3s after load
      return () => clearTimeout(timer);
    }
  }, [selectedProf, company.insolvencyProfessionals]);


  const detailLookupId =
    (company.cin && company.cin !== "N/A" ? company.cin : "") ||
    (company.name && company.name !== "N/A" ? company.name : "") ||
    company.id;

  // Fetch enriched company profile (which includes full announcement history + documents)
  const {
    data: enriched,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["ibbi-corporate-process", detailLookupId],
    queryFn: () => fetchIBBICompanyDetails(detailLookupId, { fresh: false }),
    refetchInterval: (query) => {
      // If enrichment is in progress, poll every 3 seconds to get the full data once ready
      return query.state.data?.enrichmentInProgress ? 3000 : false;
    },
    staleTime: 1000 * 60 * 5, // 5 mins
    retry: 1,
    enabled: !!detailLookupId,
  });





  // ── Refresh Handler — forces fresh scrape from IBBI & saves to DB ──────────
  const handleRefresh = async () => {
    setRefreshStatus("loading");
    try {
      await refetch();
      setRefreshStatus("success");
      setTimeout(() => setRefreshStatus("idle"), 3000);
    } catch {
      setRefreshStatus("idle");
    }
  };

  const handleProfClick = async (name: string) => {
    setSelectedProf(name);
    setIsLoadingProf(true);
    setProfData(null);
    setActiveProfTab("IP Detail");
    try {
      const [details, metadata] = await Promise.all([
        fetchProfessionalDetails(name),
        fetchProfessionalMetadata(name)
      ]);
      setProfData(details);
      setProfMetadata(metadata);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingProf(false);
    }
  };

  const documents = enriched?.documents ?? company.documents ?? [];
  const corporateProcesses = enriched?.corporateProcesses ?? company.corporateProcesses ?? {};

  const detailsSection = corporateProcesses.detailsAboutCd;
  const publicAnnouncementSection = corporateProcesses.publicAnnouncement;
  const claimsSection = corporateProcesses.claims;
  const resolutionPlanSection = corporateProcesses.invitationForResolutionPlan;
  const ordersSection = corporateProcesses.orders;
  const auctionNoticeSection = corporateProcesses.auctionNotice;

  const tabs = [
    { id: "Details About CD", label: "Details About CD" },
    { id: "Public Announcement", label: `Public Announcement${publicAnnouncementSection?.rows?.length ? ` (${publicAnnouncementSection.rows.length})` : ""}` },
    { id: "Claims", label: `Claims${claimsSection?.rows?.length ? ` (${claimsSection.rows.length})` : ""}` },
    { id: "Invitation for Resolution Plan", label: `Invitation For Resolution Plan${resolutionPlanSection?.rows?.length ? ` (${resolutionPlanSection.rows.length})` : ""}` },
    { id: "Orders", label: `Orders${ordersSection?.rows?.length ? ` (${ordersSection.rows.length})` : ""}` },
    { id: "Auction Notice", label: `Auction Notice${auctionNoticeSection?.rows?.length ? ` (${auctionNoticeSection.rows.length})` : ""}` },
    { id: "Directors", label: `Directors${enriched?.directors?.length ? ` (${enriched.directors.length})` : ""}` },
    { id: "Charges", label: `Charges${enriched?.charges?.length ? ` (${enriched.charges.length})` : ""}` },
    { id: "Related News", label: `Related News${enriched?.news?.length ? ` (${enriched.news.length})` : ""}` },
  ];

  // ── All eligible docs — filtered by type AND deduplicated by URL ──────────
  const allDocs = useMemo(() => {
    const seenUrls = new Set<string>();
    return documents.filter((d) => {
      const ft = d.fileType || "";
      const nameLower = d.fileName.toLowerCase();
      const urlLower = (d.url || "").toLowerCase();

      const isValidType =
        ft === "pdf" || nameLower.endsWith(".pdf") || urlLower.includes(".pdf") ||
        ft === "html" || nameLower.endsWith(".html") || urlLower.includes("ibbi.gov.in");

      if (!isValidType) return false;

      // Deduplicate by the actual download/view URL
      const urlKey = (d.downloadUrl || d.url || "").trim().toLowerCase();
      if (!urlKey || seenUrls.has(urlKey)) return false;
      seenUrls.add(urlKey);
      return true;
    });
  }, [documents]);

  // ── Extract unique categories for filter dropdown ──────────────────────────
  const categories = useMemo(() => {
    const cats = new Set<string>();
    allDocs.forEach((d) => cats.add(d.category || "General"));
    return ["All", ...Array.from(cats).sort()];
  }, [allDocs]);

  // ── Filter docs by selected category ──────────────────────────────────────
  const filteredDocs = useMemo(() => {
    if (selectedCategory === "All") return allDocs;
    return allDocs.filter((d) => (d.category || "General") === selectedCategory);
  }, [allDocs, selectedCategory]);


  return (
    <div className="w-full bg-white font-sans text-sm mb-12 border border-slate-200 rounded overflow-hidden shadow-sm">

      {/* ── Banner ── */}
      <div className="bg-[#81BC06] text-white px-6 py-5 relative overflow-hidden">
        <div className="absolute inset-0 opacity-15 pointer-events-none">
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <path d="M-50,80 Q150,10 400,60 T900,30" stroke="white" strokeWidth="1.5" fill="none" />
            <path d="M-50,120 Q200,60 450,100 T900,70" stroke="white" strokeWidth="1" fill="none" />
            <circle cx="200" cy="40" r="4" fill="white" opacity="0.6" />
            <circle cx="500" cy="80" r="6" fill="white" opacity="0.4" />
            <circle cx="750" cy="30" r="3" fill="white" opacity="0.5" />
          </svg>
        </div>
        <div className="relative z-10 flex flex-wrap justify-between items-start gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-white/70 mb-1">IBBI</p>
            <h2 className="text-xl font-black uppercase tracking-wide mb-2">CORPORATE PROCESSES</h2>
            <div className="flex flex-wrap items-center gap-1 text-xs text-white/85">
              <span className="hover:underline cursor-pointer">Home</span>
              <ChevronRight className="w-3 h-3" />
              <span className="hover:underline cursor-pointer">Corporate Processes</span>
              <ChevronRight className="w-3 h-3" />
              <span className="font-bold uppercase">{company.name}</span>
            </div>
          </div>

          {/* ── Right side: CIN + Refresh Button ── */}
          <div className="flex flex-col items-end gap-2">
            <div className="flex flex-wrap items-center justify-end gap-2">
              {company.authCap && (
                <span className="font-bold tracking-tight bg-white/10 px-3 py-1 rounded text-[10px] uppercase">
                  Auth Cap: <span className="text-white">{formatToCr(company.authCap)}</span>
                </span>
              )}
              {company.puc && (
                <span className="font-bold tracking-tight bg-white/10 px-3 py-1 rounded text-[10px] uppercase">
                  Paid Up: <span className="text-white">{formatToCr(company.puc)}</span>
                </span>
              )}
              {company.cin && company.cin !== "N/A" && (
                <span className="font-bold tracking-wider bg-white/20 px-3 py-1 rounded text-xs">
                  CIN No: {company.cin}
                </span>
              )}
            </div>

            {/* Refresh Button */}
            <button
              id="ibbi-refresh-btn"
              onClick={handleRefresh}
              disabled={refreshStatus === "loading"}
              className={`
                inline-flex items-center gap-2 px-4 py-2 rounded text-xs font-bold uppercase tracking-wide
                transition-all duration-200 shadow-md active:scale-95
                ${refreshStatus === "loading"
                  ? "bg-white/20 text-white/60 cursor-not-allowed"
                  : refreshStatus === "success"
                    ? "bg-emerald-500 text-white hover:bg-emerald-600"
                    : "bg-white text-[#81BC06] hover:bg-white/90 hover:shadow-lg"
                }
              `}
            >
              {refreshStatus === "loading" ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Refreshing…
                </>
              ) : refreshStatus === "success" ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Updated!
                </>
              ) : (
                <>
                  <RefreshCw className="w-3.5 h-3.5" />
                  Refresh Data
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ── Horizontal Tabs ── */}
      <div className="bg-white border-b border-slate-200 overflow-x-auto">
        <div className="flex flex-nowrap min-w-max">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-5 py-3 text-[11px] font-bold uppercase tracking-wide whitespace-nowrap border-b-2 transition-all ${activeTab === tab.id
                ? "border-[#81BC06] text-[#81BC06] bg-[#81BC06]/10"
                : "border-transparent text-slate-400 hover:text-[#81BC06] hover:bg-[#81BC06]/5"
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>


      {/* ── Tab Content ── */}
      <div className="p-6">

        {/* ── TAB: Details About CD ── */}
        {activeTab === "Details About CD" && (
          <div className="space-y-8">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <h3 className="text-base font-bold text-slate-900">For CIRP/Liquidation Assignment</h3>

              {enriched?.enrichmentInProgress && (
                <div className="flex items-center gap-2 px-3 py-1 bg-amber-50 border border-amber-200 rounded-full animate-pulse shadow-sm">
                  <Loader2 className="w-3 h-3 text-amber-600 animate-spin" />
                  <span className="text-[10px] font-bold text-amber-700 uppercase tracking-tighter">
                    Syncing Latest Detailed Records...
                  </span>
                </div>
              )}
            </div>

            <div>
              {isLoading ? (
                <TabLoader />
              ) : detailsSection?.rows?.length ? (
                <div className="border border-slate-300 rounded overflow-hidden">
                  <table className="w-full text-left text-sm table-fixed">
                    <tbody>
                      {detailsSection.rows.map((row, i) => (
                        <tr key={row.id} className={i < detailsSection.rows.length - 1 ? "border-b border-slate-200" : ""}>
                          <td className="p-3 bg-slate-50 text-slate-600 font-medium w-60">{row.label || "-"}</td>
                          <td className="p-3 border-l border-slate-200 text-slate-800">
                            {row.label?.toLowerCase().includes("capital") && !isNaN(Number(row.value))
                              ? formatToCr(Number(row.value))
                              : (row.value || "-")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="border border-slate-300 rounded overflow-hidden">
                  <table className="w-full text-left text-sm table-fixed">
                    <tbody>
                      {[
                        { label: "CIN No", value: company.cin },
                        { label: "Name of the Corporate Debtor", value: company.name },
                        { label: "Process Initiated", value: company.status },
                        { label: "Name of the Applicant", value: company.applicant_name },
                        { label: "Sector of business of CD", value: company.industry },
                      ].map(({ label, value }, i, arr) => (
                        <tr key={label} className={i < arr.length - 1 ? "border-b border-slate-200" : ""}>
                          <td className="p-3 bg-slate-50 text-slate-600 font-medium w-60">{label}</td>
                          <td className="p-3 border-l border-slate-200 text-slate-800">{value || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Professionals Associated */}
            <div>
              <h3 className="text-base font-bold text-slate-900 mb-3">Professionals Associated</h3>
              <div className="border border-slate-300 rounded overflow-hidden">
                <div className="bg-[#002D62] text-white p-2.5 text-center text-[12px] tracking-wide font-medium">
                  Process with ICD:&nbsp;{company.announcementDate || "-"}
                </div>
                <div className="overflow-x-auto">
                  {selectedProf ? (
                    <div className="bg-white border-t border-slate-200">
                      {/* Prof Header */}
                      <div className="p-4 bg-slate-50 flex items-center justify-between border-b border-slate-200">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => setSelectedProf(null)}
                            className="p-1.5 hover:bg-slate-200 rounded-full transition-colors text-slate-600"
                          >
                            <ChevronLeft className="w-5 h-5" />
                          </button>
                          <div>
                            <h4 className="font-bold text-slate-900 leading-tight">{selectedProf}</h4>
                            <div className="flex items-center gap-2">
                              <p className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">Professional Profile</p>
                            </div>
                          </div>
                        </div>
                        {profData?.profile_url && (
                          <a
                            href={profData.profile_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[10px] font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1 uppercase tracking-tight"
                          >
                            View on IBBI <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>

                      {isLoadingProf ? (
                        <div className="py-20 flex flex-col items-center justify-center gap-3">
                          <Loader2 className="w-8 h-8 text-[#81BC06] animate-spin" />
                          <p className="text-sm text-slate-500 font-medium">Fetching professional details from IBBI...</p>
                        </div>
                      ) : !profData?.found ? (
                        <div className="py-20 text-center px-10">
                          <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto mb-3" />
                          <p className="text-slate-600 font-medium">{profData?.message || "Professional details not found."}</p>
                          <button
                            onClick={() => setSelectedProf(null)}
                            className="mt-4 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg text-xs font-bold hover:bg-slate-200 transition-colors"
                          >
                            Back to List
                          </button>
                        </div>
                      ) : (
                        <div>
                          {/* Sub Tabs */}
                          <div className="flex border-b border-slate-200 bg-white overflow-x-auto scrollbar-hide">
                            {[...Object.keys(profData.sections).filter(k => k !== "_scraped_at"), "Required"].map((tab) => (
                              <button
                                key={tab}
                                onClick={() => setActiveProfTab(tab)}
                                className={`px-5 py-3 text-[11px] font-bold uppercase tracking-wider whitespace-nowrap transition-all border-b-2 ${activeProfTab === tab
                                  ? "border-[#81BC06] text-[#81BC06] bg-[#81BC06]/5"
                                  : "border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50"
                                  }`}
                              >
                                {tab}
                              </button>
                            ))}
                          </div>

                          {/* Tab Content */}
                          <div className="p-5 min-h-[400px]">
                            {(() => {
                              // ── Required Section (Custom) ──────────────────
                              if (activeProfTab === "Required") {
                                return <RequiredLinksView
                                  metadata={profMetadata}
                                  onAdd={async (label, url) => {
                                    const newMetadata = { ...profMetadata, links: [...profMetadata.links, { label, url, id: Date.now() }] };
                                    setProfMetadata(newMetadata);
                                    await updateProfessionalMetadata(selectedProf!, newMetadata);
                                  }}
                                  onDelete={async (id) => {
                                    const newMetadata = { ...profMetadata, links: profMetadata.links.filter((l: any) => l.id !== id) };
                                    setProfMetadata(newMetadata);
                                    await updateProfessionalMetadata(selectedProf!, newMetadata);
                                  }}
                                />;
                              }

                              const sections = profData.sections?.[activeProfTab];
                              if (!sections || (Array.isArray(sections) && sections.length === 0)) {
                                return (
                                  <div className="py-10 text-center text-slate-400 italic text-xs">
                                    No records found for this section.
                                  </div>
                                );
                              }

                              return (
                                <div className="space-y-8">
                                  {/* Overall Insight & View Switcher for Assignment Analytics */}
                                  {activeProfTab === "Assignment Analytics" && sections[0]?.type === "horizontal" && (
                                    <>
                                      <AssignmentAnalyticsSummary data={sections[0].data} />
                                      <div className="flex items-center justify-between mb-4">
                                        <div className="flex items-center gap-2 text-slate-500 text-[10px] font-bold uppercase">
                                          <Info className="w-3.5 h-3.5" />
                                          <span>Assignment trends and role distribution</span>
                                        </div>
                                        <div className="flex bg-slate-100 p-0.5 rounded-lg border border-slate-200 shadow-sm">
                                          <button
                                            onClick={() => setAnalyticsViewMode("table")}
                                            className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 text-[10px] font-black transition-all ${analyticsViewMode === "table" ? "bg-white text-blue-600 shadow-sm" : "hover:bg-white/50 text-slate-400"}`}
                                          >
                                            <TableIcon className="w-3.5 h-3.5" /> TABLE
                                          </button>
                                          <button
                                            onClick={() => setAnalyticsViewMode("graph")}
                                            className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 text-[10px] font-black transition-all ${analyticsViewMode === "graph" ? "bg-white text-[#81BC06] shadow-sm" : "hover:bg-white/50 text-slate-400"}`}
                                          >
                                            <BarChart2 className="w-3.5 h-3.5" /> GRAPH
                                          </button>
                                        </div>
                                      </div>
                                    </>
                                  )}

                                  {activeProfTab === "Assignment Analytics" && analyticsViewMode === "graph" ? (
                                    <AssignmentAnalyticsGraph data={sections[0].data} />
                                  ) : (
                                    sections.map((section: any, sIdx: number) => {
                                      if (section.type === "error") {
                                        return (
                                          <div key={sIdx} className="py-10 text-center text-red-500 text-xs bg-red-50 border border-red-100 rounded-lg">
                                            Error loading section: {section.message}
                                          </div>
                                        );
                                      }

                                      if (section.type === "vertical") {
                                        return (
                                          <div key={sIdx} className="border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                                            <table className="w-full text-left text-sm">
                                              <tbody>
                                                {section.data.map((row: any, i: number) => (
                                                  <tr key={i} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/30 transition-colors">
                                                    <td className="p-3 bg-slate-50/50 text-slate-500 font-bold w-52 border-r border-slate-100 text-[11px] uppercase tracking-tight">{row.label}</td>
                                                    <td className="p-3 text-slate-800 font-medium">{row.value || "-"}</td>
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          </div>
                                        );
                                      }

                                      if (section.type === "horizontal") {
                                        const isAFAHistory = activeProfTab === "AFA Detail" && sIdx > 0;
                                        return (
                                          <div key={sIdx} className="border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                                            <div className="overflow-x-auto">
                                              <table className="w-full text-left text-[11px]">
                                                <thead className={`${isAFAHistory ? 'bg-[#F5B841] text-black' : 'bg-[#002D62] text-white'} uppercase font-bold border-b border-slate-200`}>
                                                  <tr>
                                                    {section.headers.map((h: string) => (
                                                      <th key={h} className={`p-3 font-bold tracking-tight border-r ${isAFAHistory ? 'border-yellow-600/30' : 'border-blue-800/50'} last:border-r-0 whitespace-nowrap`}>{h}</th>
                                                    ))}
                                                  </tr>
                                                </thead>
                                                <tbody>
                                                  {section.data.map((row: any, i: number) => (
                                                    <tr key={i} className={`border-b border-slate-100 last:border-0 hover:bg-blue-50/30 transition-colors ${i % 2 === 0 ? 'bg-white' : (isAFAHistory ? 'bg-yellow-50/30' : 'bg-slate-50/30')}`}>
                                                      {section.headers.map((h: string) => (
                                                        <td key={h} className="p-3 text-slate-700 border-r border-slate-100 last:border-r-0">{row[h] || "-"}</td>
                                                      ))}
                                                    </tr>
                                                  ))}
                                                </tbody>
                                              </table>
                                            </div>
                                          </div>
                                        );
                                      }
                                      return null;
                                    })
                                  )}
                                </div>
                              );
                            })()}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <table className="w-full text-left text-sm">
                      <thead className="bg-[#F5B841] text-slate-900 border-b border-amber-200">
                        <tr>
                          <th className="p-2.5 font-bold border-r border-amber-200">Name</th>
                          <th className="p-2.5 font-bold border-r border-amber-200">Registration No.</th>
                          <th className="p-2.5 font-bold">Appointed As</th>
                        </tr>
                      </thead>
                      <tbody>
                        {company.insolvencyProfessionals && company.insolvencyProfessionals.length > 0 ? (
                          company.insolvencyProfessionals.map((ip, idx) => (
                            <tr key={idx} className="border-b border-slate-200 last:border-0 hover:bg-slate-50 group">
                              <td className="p-2.5 border-r border-slate-200">
                                <button
                                  onClick={() => handleProfClick(ip)}
                                  className="text-blue-600 font-bold hover:text-blue-800 hover:underline flex items-center gap-1.5 transition-all text-left"
                                >
                                  {ip}
                                  <ArrowRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                                </button>
                              </td>
                              <td className="p-2.5 border-r border-slate-200 text-slate-400 text-xs italic">Not available</td>
                              <td className="p-2.5 text-slate-700">
                                {company.status?.toLowerCase().includes("liquid") ? "Liquidator" : "Resolution Professional"}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={3} className="p-5 text-center text-slate-400 text-sm">
                              No professionals found for this company.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>

            {/* Documents – Category Filter + Table */}
            {(isLoading || allDocs.length > 0) && (
              <div>
                {/* Section Header */}
                <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <FileText className="w-5 h-5 text-red-600" />
                    Corporate Data &amp; Public Documents
                    {!isLoading && (
                      <span className="text-xs font-normal text-slate-400 ml-1">
                        ({filteredDocs.length}{selectedCategory !== "All" ? ` of ${allDocs.length}` : ""})
                      </span>
                    )}
                  </h3>

                  {/* ── Category Filter Dropdown ── */}
                  {!isLoading && categories.length > 2 && (
                    <div className="flex items-center gap-2">
                      <Filter className="w-3.5 h-3.5 text-slate-400" />
                      <label htmlFor="doc-category-filter" className="text-xs text-slate-500 font-medium whitespace-nowrap">
                        Filter by Category:
                      </label>
                      <select
                        id="doc-category-filter"
                        value={selectedCategory}
                        onChange={(e) => setSelectedCategory(e.target.value)}
                        className="text-xs border border-slate-300 rounded px-2.5 py-1.5 bg-white text-slate-700 font-medium
                          focus:outline-none focus:ring-2 focus:ring-[#81BC06] focus:border-[#81BC06]
                          hover:border-slate-400 transition-colors cursor-pointer min-w-[180px]"
                      >
                        {categories.map((cat) => (
                          <option key={cat} value={cat}>
                            {cat === "All"
                              ? `All Categories (${allDocs.length})`
                              : `${cat} (${allDocs.filter((d) => (d.category || "General") === cat).length})`}
                          </option>
                        ))}
                      </select>
                      {selectedCategory !== "All" && (
                        <button
                          onClick={() => setSelectedCategory("All")}
                          className="text-xs text-[#81BC06] hover:text-green-700 font-medium underline"
                        >
                          Clear
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {isLoading ? (
                  <TabLoader />
                ) : filteredDocs.length === 0 ? (
                  <div className="py-10 text-center border border-dashed border-slate-200 rounded bg-slate-50 text-slate-400 text-sm">
                    No documents found for category{" "}
                    <strong className="text-slate-600">"{selectedCategory}"</strong>.{" "}
                    <button
                      onClick={() => setSelectedCategory("All")}
                      className="text-[#81BC06] underline hover:text-green-700"
                    >
                      Show all
                    </button>
                  </div>
                ) : (
                  <div className="border border-slate-300 rounded overflow-x-auto">
                    <table className="w-full text-left text-sm min-w-[560px]">
                      <thead className="bg-slate-100 border-b border-slate-300">
                        <tr>
                          <th className="p-2.5 font-bold border-r border-slate-300 text-slate-600">Category</th>
                          <th className="p-2.5 font-bold border-r border-slate-300 text-slate-600 w-[44%]">File Name</th>
                          <th className="p-2.5 font-bold border-r border-slate-300 text-slate-600">Source</th>
                          <th className="p-2.5 font-bold border-r border-slate-300 text-slate-600">Date</th>
                          <th className="p-2.5 font-bold text-slate-600 text-center w-28">Download</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredDocs.map((doc, idx) => {
                          const href = resolveDocUrl(doc.downloadUrl || doc.url);
                          const { label, color, icon } = getFileInfo(doc);
                          const isPdf = label === "PDF";
                          const readableName = prettifyFileName(doc.fileName);
                          return (
                            <tr
                              key={idx}
                              className="border-b border-slate-200 last:border-0 hover:bg-[#81BC06]/5 transition-colors"
                            >
                              {/* Category — pill badge */}
                              <td className="p-2.5 border-r border-slate-200 text-xs">
                                <span className="inline-flex items-center px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full text-[10px] font-medium">
                                  {doc.category || "General"}
                                </span>
                              </td>

                              {/* File Name — readable, not raw slug */}
                              <td className="p-2.5 border-r border-slate-200">
                                <a
                                  href={href}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-blue-600 hover:text-blue-800 underline text-xs"
                                  title={doc.fileName}
                                >
                                  {readableName.length > 60
                                    ? readableName.substring(0, 60) + "…"
                                    : readableName}
                                </a>
                              </td>

                              {/* Source */}
                              <td className="p-2.5 border-r border-slate-200 text-slate-400 text-xs">
                                {doc.source || "-"}
                              </td>

                              {/* Date */}
                              <td className="p-2.5 border-r border-slate-200 text-slate-400 text-xs">
                                {doc.dateOfFiling || "-"}
                              </td>

                              {/* Download — blob download for PDF, open for others */}
                              <td className="p-2.5 text-center">
                                {isPdf ? (
                                  <button
                                    onClick={() => downloadPdf(href, doc.fileName)}
                                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 ${color} text-white rounded text-xs font-bold transition-all shadow-sm active:scale-95 hover:opacity-90`}
                                  >
                                    <Download className="w-3 h-3" />
                                    {label}
                                  </button>
                                ) : (
                                  <a
                                    href={href}
                                    target="_blank"
                                    rel="noreferrer"
                                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 ${color} text-white rounded text-xs font-bold transition-all shadow-sm active:scale-95`}
                                  >
                                    {icon}
                                    {label}
                                  </a>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

              </div>
            )}
          </div>
        )}

        {/* ── TAB: Public Announcement ── */}
        {activeTab === "Public Announcement" && (
          <div>
            <h3 className="text-base font-bold text-slate-900 mb-4">Announcement History</h3>
            {isLoading ? (
              <TabLoader />
            ) : error ? (
              <TabError message="Could not load announcement data. The section is unavailable right now." />
            ) : !publicAnnouncementSection?.rows?.length ? (
              <EmptyTab tab="Public Announcement" />
            ) : (
              <ProcessTable section={publicAnnouncementSection} />
            )}
          </div>
        )}

        {/* ── TAB: Claims ── */}
        {activeTab === "Claims" && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-base font-bold text-slate-900">Claims Information</h3>

              {/* ── Merge & View PDF Button ── */}
              {claimsSection?.rows?.length > 1 && (
                <button
                  onClick={async () => {
                    const btn = document.getElementById("merge-claims-btn");
                    if (btn) btn.innerText = "Merging Versions...";
                    try {
                      const data = await (await import("@/services/ibbiService")).fetchMergedClaims(detailLookupId);
                      if (data && data.length > 0) {
                        // Create a temporary printable window
                        const printWindow = window.open("", "_blank");
                        if (printWindow) {
                          const companyName = company.name;
                          const html = `
                            <html>
                              <head>
                                <title>Claims Consolidation Report - ${companyName}</title>
                                <style>
                                  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; color: #1e293b; line-height: 1.4; background: #fff; }
                                  .no-print { text-align: right; margin-bottom: 20px; }
                                  .btn-print { background: #81BC06; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-weight: bold; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                                  
                                  .header { border-bottom: 3px solid #81BC06; padding-bottom: 15px; margin-bottom: 25px; }
                                  .company-name { font-size: 26px; font-weight: 800; color: #002D62; margin: 0; text-transform: uppercase; }
                                  .report-meta { font-size: 12px; color: #64748b; margin-top: 5px; }
                                  
                                  .version-section { margin-bottom: 50px; break-inside: avoid; }
                                  .version-badge { display: inline-block; background: #002D62; color: white; padding: 4px 12px; border-radius: 4px; font-size: 14px; font-weight: bold; margin-bottom: 15px; }
                                  .version-info { font-size: 14px; color: #475569; margin-bottom: 10px; font-weight: 600; }
                                  
                                  /* IBBI Style Table */
                                  .summary-table { width: 100%; border-collapse: collapse; margin-top: 10px; border: 1px solid #cbd5e1; font-size: 12px; }
                                  .summary-table th { background: #002D62; color: white; border: 1px solid #1e293b; padding: 8px; text-align: center; }
                                  .summary-table .sub-header { background: #F5B841; color: #000; font-weight: bold; }
                                  .summary-table td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; }
                                  .summary-table .text-center { text-align: center; }
                                  .summary-table .text-right { text-align: right; }
                                  .summary-table .total-row { background: #f8fafc; font-weight: bold; border-top: 2px solid #002D62; }
                                  
                                  @media print {
                                    .no-print { display: none; }
                                    body { padding: 0; }
                                    .version-section { page-break-after: always; }
                                    .version-section:last-child { page-break-after: auto; }
                                  }
                                </style>
                              </head>
                              <body>
                                <div class="no-print">
                                  <button class="btn-print" onclick="window.print()">Download Combined Report (PDF)</button>
                                </div>
                                <div class="header">
                                  <h1 class="company-name">${companyName}</h1>
                                  <div class="report-meta">
                                    <strong>CIN:</strong> ${company.cin} | 
                                    <strong>Generated:</strong> ${new Date().toLocaleDateString()}
                                  </div>
                                </div>

                                ${data.map((v: any) => `
                                  <div class="version-section">
                                    <div class="version-badge">${v.version}</div>
                                    <div class="version-info">
                                      Date: ${v.date} | Liquidator: ${v.rp_name || "N/A"}
                                    </div>
                                    
                                    <table class="summary-table">
                                      <thead>
                                        <tr>
                                          <th rowspan="2" width="40">Sr. No.</th>
                                          <th rowspan="2">Category of stakeholders</th>
                                          <th colspan="2" class="sub-header">Summary of Claims Received</th>
                                          <th colspan="2" class="sub-header">Summary of Claims Admitted</th>
                                        </tr>
                                        <tr class="sub-header">
                                          <th width="80">No. of Claims</th>
                                          <th width="120">Amount (Rs.)</th>
                                          <th width="80">No. of Claims</th>
                                          <th width="120">Amount Admitted</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        ${v.summaryTable && v.summaryTable.length > 0
                              ? v.summaryTable.map((row: any) => `
                                            <tr class="${row.category.toLowerCase().includes('total') ? 'total-row' : ''}">
                                              <td class="text-center">${row.srNo}</td>
                                              <td>${row.category}</td>
                                              <td class="text-center">${row.receivedCount}</td>
                                              <td class="text-right">${row.receivedAmount}</td>
                                              <td class="text-center">${row.admittedCount}</td>
                                              <td class="text-right">${row.admittedAmount}</td>
                                            </tr>
                                          `).join("")
                              : `<tr><td colspan="6" class="text-center" style="padding: 20px; color: #94a3b8;">No summary table data found for this version.</td></tr>`
                            }
                                      </tbody>
                                    </table>
                                  </div>
                                `).join("")}
                              </body>
                            </html>
                          `;
                          printWindow.document.write(html);
                          printWindow.document.close();
                        }
                      }
                    } catch (err) {
                      console.error(err);
                      alert("Claims merge failed. Please try again.");
                    } finally {
                      if (btn) btn.innerText = "Merge & View Combined Claims (PDF)";
                    }
                  }}
                  id="merge-claims-btn"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-[#002D62] text-white rounded text-xs font-bold hover:bg-[#003d82] transition-colors shadow-sm"
                >
                  <FileText className="w-3.5 h-3.5" />
                  Merge & View Combined Claims (PDF)
                </button>
              )}
            </div>

            {isLoading ? (
              <TabLoader />
            ) : error ? (
              <TabError message="Could not load claims data. The section is unavailable right now." />
            ) : !claimsSection?.rows?.length ? (
              <EmptyTab tab="Claims" />
            ) : (
              <ProcessTable section={claimsSection} />
            )}
          </div>
        )}

        {/* ── TAB: Invitation for Resolution Plan ── */}
        {activeTab === "Invitation for Resolution Plan" && (
          <div>
            <h3 className="text-base font-bold text-slate-900 mb-4">Resolution Plan Invitation</h3>
            {isLoading ? (
              <TabLoader />
            ) : error ? (
              <TabError message="Could not load resolution plan data." />
            ) : !resolutionPlanSection?.rows?.length ? (
              <EmptyTab tab="Invitation for Resolution Plan" />
            ) : (
              <ProcessTable section={resolutionPlanSection} />
            )}
          </div>
        )}

        {/* ── TAB: Orders ── */}
        {activeTab === "Orders" && (
          <div>
            <h3 className="text-base font-bold text-slate-900 mb-4">Related Orders</h3>
            {isLoading ? (
              <TabLoader />
            ) : error ? (
              <TabError message="Could not load orders data." />
            ) : ordersSection?.rows?.length ? (
              <ProcessTable section={ordersSection} />
            ) : (
              <EmptyTab tab="Orders" />
            )}
          </div>
        )}

        {/* ── TAB: Auction Notice ── */}
        {activeTab === "Auction Notice" && (
          <div>
            <h3 className="text-base font-bold text-slate-900 mb-4">Auction Notices</h3>
            {isLoading ? (
              <TabLoader />
            ) : error ? (
              <TabError message="Could not load auction notice data." />
            ) : !auctionNoticeSection?.rows?.length ? (
              <EmptyTab tab="Auction Notice" />
            ) : (
              <ProcessTable section={auctionNoticeSection} />
            )}
          </div>
        )}

        {/* ── TAB: Directors ── */}
        {activeTab === "Directors" && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 className="text-xl font-black text-slate-900 tracking-tight uppercase">DIRECTORS</h2>
            </div>

            {isLoading ? (
              <TabLoader />
            ) : !enriched?.directors?.length ? (
              <EmptyTab tab="Directors" />
            ) : (
              <div>
                <div className="overflow-x-auto rounded-xl border border-slate-200 shadow-sm bg-white">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead className="bg-[#fcfdfe] text-slate-500 uppercase font-black text-[10px] tracking-widest border-b border-slate-200">
                      <tr>
                        <th className="px-5 py-4 w-12 text-center">#</th>
                        <th className="px-5 py-4">DIN</th>
                        <th className="px-5 py-4">NAME</th>
                        <th className="px-5 py-4">
                          <div className="flex items-center gap-2">
                            DESIGNATION
                            <select
                              value={selectedDesignation}
                              onChange={(e) => setSelectedDesignation(e.target.value)}
                              className="bg-white border border-slate-200 rounded px-2 py-1 normal-case font-medium text-slate-600 focus:outline-none focus:ring-1 focus:ring-[#81BC06]"
                            >
                              <option value="All">All</option>
                              {Array.from(new Set(enriched.directors.map(d => d.designation))).sort().map(d => (
                                <option key={d} value={d}>{d}</option>
                              ))}
                            </select>
                          </div>
                        </th>
                        <th className="px-5 py-4">START DATE</th>
                        <th className="px-5 py-4">STATUS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {enriched.directors
                        .filter(d => selectedDesignation === "All" || d.designation === selectedDesignation)
                        .map((director, idx) => (
                          <tr
                            key={director.id || director.din}
                            className={`group border-b border-slate-100 last:border-0 hover:bg-[#81BC06]/5 transition-colors ${idx % 2 === 0 ? 'bg-white' : 'bg-[#fafbfc]/50'}`}
                          >
                            <td className="px-5 py-4 text-center font-bold text-slate-800">{idx + 1}</td>
                            <td className="px-5 py-4 text-slate-500 font-mono text-[11px]">
                              {director.din || "N/A"}
                            </td>
                            <td className="px-5 py-4 text-[#002D62] group-hover:text-blue-800 font-black tracking-wide uppercase transition-colors">
                              {director.name}
                            </td>
                            <td className="px-5 py-4 font-black text-slate-700 text-[11px] tracking-wider uppercase">
                              {director.designation}
                            </td>
                            <td className="px-5 py-4 text-slate-600 font-bold tabular-nums">
                              {director.date_of_appointment || "-"}
                            </td>
                            <td className="px-5 py-4">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-tighter ${director.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                                {director.is_active ? 'Active' : 'N/A'}
                              </span>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── TAB: Charges ── */}
        {activeTab === "Charges" && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 className="text-xl font-black text-slate-900 tracking-tight uppercase">COMPANY CHARGES</h2>
              <div className="flex items-center gap-2 px-3 py-1 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700 font-medium">
                <Landmark className="w-3.5 h-3.5" />
                Sourced from Secured Financial Creditor Claims
              </div>
            </div>

            {isLoading ? (
              <TabLoader />
            ) : !enriched?.charges?.length ? (
              <EmptyTab tab="Charges" />
            ) : (
              <div className="grid gap-4">
                <div className="overflow-x-auto rounded-xl border border-slate-200 shadow-sm bg-white">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead className="bg-slate-50 text-slate-500 uppercase font-black text-[10px] tracking-widest border-b border-slate-200">
                      <tr>
                        <th className="px-5 py-4">ID</th>
                        <th className="px-5 py-4">Stakeholder / Bank</th>
                        <th className="px-5 py-4 text-right">Amount (Claimed)</th>
                        <th className="px-5 py-4">Status</th>
                        <th className="px-5 py-4">Information</th>
                      </tr>
                    </thead>
                    <tbody>
                      {enriched.charges.map((charge, idx) => (
                        <tr key={charge.chargeId} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                          <td className="px-5 py-4 font-mono text-[10px] text-slate-400">{charge.chargeId}</td>
                          <td className="px-5 py-4 font-bold text-[#002D62]">{charge.bankName}</td>
                          <td className="px-5 py-4 text-right font-black text-slate-800">
                            {charge.amount > 0 ? formatToCr(charge.amount) : "See Details"}
                          </td>
                          <td className="px-5 py-4">
                            <span className="inline-flex items-center px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-[10px] font-bold uppercase tracking-tighter">
                              {charge.status}
                            </span>
                          </td>
                          <td className="px-5 py-4 text-xs text-slate-500 italic max-w-xs">{charge.details || "N/A"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── TAB: Related News ── */}
        {activeTab === "Related News" && (
          <div className="space-y-6">
            <h2 className="text-xl font-black text-slate-900 tracking-tight uppercase">RELATED NEWS</h2>
            {isLoading ? (
              <TabLoader />
            ) : !enriched?.news?.length ? (
              <EmptyTab tab="Related News" />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {enriched.news.map((item) => (
                  <a
                    key={item.id}
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className={`p-4 rounded-xl border transition-all flex flex-col gap-3 group bg-white hover:shadow-md ${item.isRelated ? 'border-emerald-200 hover:border-emerald-400' : 'border-slate-200 hover:border-slate-400'}`}
                  >
                    <div className="flex justify-between items-start gap-2">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{item.date}</span>
                      {item.isRelated && (
                        <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded text-[9px] font-black uppercase tracking-tighter">
                          Directly Related
                        </span>
                      )}
                    </div>
                    <h4 className="text-sm font-bold text-slate-900 leading-tight group-hover:text-[#81BC06] transition-colors line-clamp-2">
                      {item.title}
                    </h4>
                    <div className="flex items-center gap-1.5 mt-auto">
                      <div className="w-5 h-5 rounded-full bg-slate-100 flex items-center justify-center">
                        <Globe className="w-3 h-3 text-slate-500" />
                      </div>
                      <span className="text-xs text-slate-500 font-medium">{item.source}</span>
                      <ExternalLink className="w-3 h-3 text-slate-300 ml-auto" />
                    </div>
                  </a>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default IBBICorporateProcess;
