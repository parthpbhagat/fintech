import { useState } from "react";
import {
  Download,
  ChevronRight,
  FileText,
  FileJson,
  Globe,
  ExternalLink,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import type { AnnouncementRecord, Company } from "@/data/types";
import { API_BASE_URL, fetchIBBICompanyDetails } from "@/services/ibbiService";

interface IBBICorporateProcessProps {
  company: Company;
}

// ── Resolve relative backend doc URLs ──────────────────────────────────────
const resolveDocUrl = (url?: string): string => {
  if (!url) return "#";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${API_BASE_URL}${url}`;
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

// ── Main Component ──────────────────────────────────────────────────────────
const IBBICorporateProcess = ({ company }: IBBICorporateProcessProps) => {
  const [activeTab, setActiveTab] = useState("Details About CD");

  const tabs = [
    "Details About CD",
    "Public Announcement",
    "Claims",
    "Invitation for Resolution Plan",
    "Orders",
    "Auction Notice",
  ];

  // Fetch enriched company profile (which includes full announcement history + documents)
  const {
    data: enriched,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["ibbi-corporate-process", company.id],
    queryFn: () => fetchIBBICompanyDetails(company.id),
    staleTime: 1000 * 60 * 5,
    retry: 1,
  });

  const announcementHistory: AnnouncementRecord[] = enriched?.announcementHistory ?? company.announcementHistory ?? [];
  const documents = enriched?.documents ?? company.documents ?? [];
  const pdfDocs = documents.filter((d) => {
    const ft = d.fileType || "";
    const nameLower = d.fileName.toLowerCase();
    const urlLower = (d.url || "").toLowerCase();
    return ft === "pdf" || nameLower.endsWith(".pdf") || urlLower.includes(".pdf");
  });
  const allDocs = documents.filter((d) => {
    const ft = d.fileType || "";
    const nameLower = d.fileName.toLowerCase();
    const urlLower = (d.url || "").toLowerCase();
    // Only show PDFs and external IBBI registry HTML links
    return ft === "pdf" || nameLower.endsWith(".pdf") || urlLower.includes(".pdf") || ft === "html" || nameLower.endsWith(".html") || urlLower.includes("ibbi.gov.in");
  });

  // Categorize live data for Corporate Process Tabs
  const publicAnnouncements = announcementHistory.filter(a => 
    a.announcementType.toLowerCase().includes("public announcement") || 
    a.announcementType.toLowerCase().includes("form a") ||
    a.announcementType.toLowerCase().includes("cirp")
  );

  const resolutionPlans = announcementHistory.filter(a => 
    a.announcementType.toLowerCase().includes("resolution plan") || 
    a.announcementType.toLowerCase().includes("form g")
  );

  const auctionNotices = announcementHistory.filter(a => 
    a.announcementType.toLowerCase().includes("auction") || 
    a.announcementType.toLowerCase().includes("sale") ||
    a.announcementType.toLowerCase().includes("liquidation")
  );

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
        <div className="relative z-10">
          <p className="text-[10px] font-bold uppercase tracking-widest text-white/70 mb-1">IBBI</p>
          <h2 className="text-xl font-black uppercase tracking-wide mb-2">CORPORATE PROCESSES</h2>
          <div className="flex flex-wrap justify-between items-center text-xs gap-2">
            <div className="flex flex-wrap items-center gap-1 text-white/85">
              <span className="hover:underline cursor-pointer">Home</span>
              <ChevronRight className="w-3 h-3" />
              <span className="hover:underline cursor-pointer">Corporate Processes</span>
              <ChevronRight className="w-3 h-3" />
              <span className="font-bold uppercase">{company.name}</span>
            </div>
            {company.cin && company.cin !== "N/A" && (
              <span className="font-bold tracking-wider bg-white/20 px-3 py-1 rounded text-xs">
                CIN No: {company.cin}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Horizontal Tabs ── */}
      <div className="bg-white border-b border-slate-200 overflow-x-auto">
        <div className="flex min-w-max">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-5 py-3 text-[11px] font-bold uppercase tracking-wide whitespace-nowrap border-b-2 transition-all ${
                activeTab === tab
                  ? "border-[#81BC06] text-[#81BC06] bg-[#81BC06]/10"
                  : "border-transparent text-slate-400 hover:text-[#81BC06] hover:bg-[#81BC06]/5"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab Content ── */}
      <div className="p-6">

        {/* ── TAB: Details About CD ── */}
        {activeTab === "Details About CD" && (
          <div className="space-y-8">
            {/* CIRP Assignment Table */}
            <div>
              <h3 className="text-base font-bold text-slate-900 mb-3">For CIRP/Liquidation Assignment</h3>
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
            </div>

            {/* Professionals Associated */}
            <div>
              <h3 className="text-base font-bold text-slate-900 mb-3">Professionals Associated</h3>
              <div className="border border-slate-300 rounded overflow-hidden">
                <div className="bg-[#002D62] text-white p-2.5 text-center text-[12px] tracking-wide font-medium">
                  Process with ICD:&nbsp;{company.announcementDate || "-"}
                </div>
                <div className="overflow-x-auto">
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
                          <tr key={idx} className="border-b border-slate-200 last:border-0 hover:bg-slate-50">
                            <td className="p-2.5 border-r border-slate-200 text-blue-600 font-medium">{ip}</td>
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
                </div>
              </div>
            </div>

            {/* Documents – PDF only download, proper labelling */}
            {(isLoading || allDocs.length > 0) && (
              <div>
                <h3 className="text-base font-bold text-slate-900 mb-3 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-red-600" />
                  Corporate Data &amp; Public Documents
                </h3>
                {isLoading ? (
                  <TabLoader />
                ) : (
                  <div className="border border-slate-300 rounded overflow-x-auto">
                    <table className="w-full text-left text-sm min-w-[640px]">
                      <thead className="bg-slate-100 border-b border-slate-300">
                        <tr>
                          <th className="p-2.5 font-bold border-r border-slate-300 text-slate-600">Type</th>
                          <th className="p-2.5 font-bold border-r border-slate-300 text-slate-600">Category</th>
                          <th className="p-2.5 font-bold border-r border-slate-300 text-slate-600 w-[38%]">File Name</th>
                          <th className="p-2.5 font-bold border-r border-slate-300 text-slate-600">Source</th>
                          <th className="p-2.5 font-bold border-r border-slate-300 text-slate-600">Date</th>
                          <th className="p-2.5 font-bold text-slate-600 text-center w-28">Download</th>
                        </tr>
                      </thead>
                      <tbody>
                        {allDocs.map((doc, idx) => {
                          const href = resolveDocUrl(doc.downloadUrl || doc.url);
                          const { label, color, icon } = getFileInfo(doc);
                          const isPdf = label === "PDF";
                          return (
                            <tr key={idx} className="border-b border-slate-200 last:border-0 hover:bg-slate-50">
                              <td className="p-2.5 border-r border-slate-200">
                                <span className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase px-2 py-0.5 rounded ${isPdf ? "bg-red-100 text-red-700" : label === "JSON" ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600"}`}>
                                  {icon} {label}
                                </span>
                              </td>
                              <td className="p-2.5 border-r border-slate-200 text-slate-700 text-xs">{doc.category || "General"}</td>
                              <td className="p-2.5 border-r border-slate-200">
                                <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 hover:text-blue-800 underline text-xs" title={doc.fileName}>
                                  {doc.fileName.length > 52 ? doc.fileName.substring(0, 52) + "…" : doc.fileName}
                                </a>
                              </td>
                              <td className="p-2.5 border-r border-slate-200 text-slate-400 text-xs">{doc.source || "-"}</td>
                              <td className="p-2.5 border-r border-slate-200 text-slate-400 text-xs">{doc.dateOfFiling || "-"}</td>
                              <td className="p-2.5 text-center">
                                <a
                                  href={href}
                                  target="_blank"
                                  rel="noreferrer"
                                  download={isPdf ? doc.fileName : undefined}
                                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 ${color} text-white rounded text-xs font-bold transition-all shadow-sm active:scale-95`}
                                >
                                  <Download className="w-3 h-3" />
                                  {label}
                                </a>
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
            ) : announcementHistory.length === 0 ? (
              <EmptyTab tab="Public Announcement" />
            ) : (
              <div className="overflow-x-auto border border-slate-300 rounded">
                <table className="w-full text-left text-sm min-w-[700px]">
                  <thead className="bg-[#002D62] text-white">
                    <tr>
                      <th className="p-2.5 font-bold border-r border-blue-700">Announcement Type</th>
                      <th className="p-2.5 font-bold border-r border-blue-700">Date</th>
                      <th className="p-2.5 font-bold border-r border-blue-700">Applicant</th>
                      <th className="p-2.5 font-bold border-r border-blue-700">IP / Liquidator</th>
                      <th className="p-2.5 font-bold">Last Date of Submission</th>
                    </tr>
                  </thead>
                  <tbody>
                    {publicAnnouncements.length > 0 ? publicAnnouncements.map((ann, idx) => (
                      <tr key={`${ann.id}-${idx}`} className="border-b border-slate-200 last:border-0 hover:bg-slate-50">
                        <td className="p-2.5 border-r border-slate-200 text-slate-800 font-medium">{ann.announcementType || "-"}</td>
                        <td className="p-2.5 border-r border-slate-200 text-slate-600 text-xs">{ann.announcementDate || "-"}</td>
                        <td className="p-2.5 border-r border-slate-200 text-slate-600 text-xs">{ann.applicantName || "-"}</td>
                        <td className="p-2.5 border-r border-slate-200 text-blue-600 text-xs">{ann.insolvencyProfessional || "-"}</td>
                        <td className="p-2.5 text-slate-600 text-xs">{ann.lastDateOfSubmission || "-"}</td>
                      </tr>
                    )) : (
                      <tr>
                        <td colSpan={5} className="p-5 text-center text-slate-400">No public announcements found in live data.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── TAB: Claims ── */}
        {activeTab === "Claims" && (
          <div>
            <h3 className="text-base font-bold text-slate-900 mb-4">Claims Information</h3>
            {isLoading ? (
              <TabLoader />
            ) : error ? (
              <TabError message="Could not load claims data. The section is unavailable right now." />
            ) : !enriched?.announcementType ? (
              <EmptyTab tab="Claims" />
            ) : (
              <div className="grid md:grid-cols-2 gap-4">
                {[
                  { label: "Commencement Date", value: enriched.commencement_date },
                  { label: "Last Date for Claims", value: enriched.last_date_claims },
                  { label: "Announcement Type", value: enriched.announcementType },
                  { label: "Last Date of Submission", value: enriched.lastDateOfSubmission },
                  { label: "Process", value: enriched.status },
                  { label: "IP / Liquidator", value: enriched.ip_name },
                ].map(({ label, value }) =>
                  value && value !== "N/A" ? (
                    <div key={label} className="p-3 rounded border border-slate-200 bg-slate-50">
                      <p className="text-[10px] uppercase font-bold tracking-widest text-slate-400 mb-1">{label}</p>
                      <p className="text-slate-800 font-semibold">{value}</p>
                    </div>
                  ) : null
                )}
              </div>
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
            ) : resolutionPlans.length === 0 ? (
              <EmptyTab tab="Invitation for Resolution Plan" />
            ) : (
              <div className="overflow-x-auto border border-slate-300 rounded">
                <table className="w-full text-left text-sm min-w-[700px]">
                  <thead className="bg-[#002D62] text-white">
                    <tr>
                      <th className="p-2.5 font-bold border-r border-blue-700">Announcement Type</th>
                      <th className="p-2.5 font-bold border-r border-blue-700">Date</th>
                      <th className="p-2.5 font-bold">IP / Liquidator</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resolutionPlans.map((ann, idx) => (
                      <tr key={`${ann.id}-${idx}`} className="border-b border-slate-200 last:border-0 hover:bg-slate-50">
                        <td className="p-2.5 border-r border-slate-200 text-slate-800 font-medium">{ann.announcementType || "-"}</td>
                        <td className="p-2.5 border-r border-slate-200 text-slate-600 text-xs">{ann.announcementDate || "-"}</td>
                        <td className="p-2.5 text-blue-600 text-xs">{ann.insolvencyProfessional || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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
            ) : (enriched?.remarks && enriched.remarks !== "N/A" && enriched.remarks !== "No remarks published by IBBI.") ? (
              <div className="p-4 rounded border border-slate-200 bg-slate-50">
                <p className="text-[10px] uppercase tracking-widest font-bold text-slate-400 mb-2">IBBI Remarks / Orders</p>
                <p className="text-slate-800 text-sm leading-relaxed">{enriched.remarks}</p>
                {enriched.registryUrl && (
                  <a href={enriched.registryUrl} target="_blank" rel="noreferrer"
                    className="mt-3 inline-flex items-center gap-2 text-xs font-bold text-amber-700 hover:underline">
                    <ExternalLink className="w-3 h-3" /> View on IBBI Registry
                  </a>
                )}
              </div>
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
            ) : auctionNotices.length === 0 ? (
              <EmptyTab tab="Auction Notice" />
            ) : (
              <div className="overflow-x-auto border border-slate-300 rounded">
                <table className="w-full text-left text-sm min-w-[700px]">
                  <thead className="bg-[#002D62] text-white">
                    <tr>
                      <th className="p-2.5 font-bold border-r border-blue-700">Notice Type</th>
                      <th className="p-2.5 font-bold border-r border-blue-700">Date</th>
                      <th className="p-2.5 font-bold">Liquidator / IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auctionNotices.map((ann, idx) => (
                      <tr key={`${ann.id}-${idx}`} className="border-b border-slate-200 last:border-0 hover:bg-slate-50">
                        <td className="p-2.5 border-r border-slate-200 text-slate-800 font-medium">{ann.announcementType || "-"}</td>
                        <td className="p-2.5 border-r border-slate-200 text-slate-600 text-xs">{ann.announcementDate || "-"}</td>
                        <td className="p-2.5 text-blue-600 text-xs">{ann.insolvencyProfessional || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
};

export default IBBICorporateProcess;
