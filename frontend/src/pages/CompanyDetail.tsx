import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Bot,
  Building2,
  Calendar,
  ChevronRight,
  Download,
  FileText,
  Globe,
  Landmark,
  Mail,
  MapPin,
  MapPinned,
  Newspaper,
  Phone,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  User,
} from "lucide-react";
import { API_BASE_URL, fetchIBBICompanyDetails } from "@/services/ibbiService";
import DataInsightSheet, { type InsightContent } from "@/components/DataInsightSheet";
import { StatusBadge } from "@/components/Navbar";
import IBBICorporateProcess from "@/components/IBBICorporateProcess";
import AIChatAssistant from "@/components/AIChatAssistant";
import type { AnnouncementRecord, Charge, CompanyAddress, CompanyDataSource, CompanyDocument, NewsItem } from "@/data/types";

const currencyFormatter = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

const formatToCr = (amount?: number) => {
  if (amount === undefined || amount === null || amount === 0) return "0.00 Cr";
  const cr = amount / 10000000;
  return `₹ ${cr.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Cr`;
};


const renderOverview = (text?: string) => {
  if (!text) return null;
  return text.split('\n').map((line, i) => {
    if (line.includes('**[AI RISK INSIGHT]**')) {
      const remaining = line.replace('**[AI RISK INSIGHT]**', '');
      return (
        <span key={i} className="block mb-2">
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-purple-100 text-purple-700 font-black tracking-wide text-[10px] mb-1 shadow-sm border border-purple-200">
            <ShieldCheck className="w-3 h-3" /> AI RISK INSIGHT
          </span>
          <br/>
          <span className="font-medium text-slate-700">{remaining}</span>
        </span>
      );
    }
    return (
      <span key={i}>
        {line}
        <br />
      </span>
    );
  });
};

const CompanyDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("Overview");
  const [activeInsight, setActiveInsight] = useState<InsightContent | null>(null);

  const { data: company, isLoading, error } = useQuery({
    queryKey: ["company", id],
    queryFn: () => fetchIBBICompanyDetails(id || ""),
    enabled: !!id,
    staleTime: 1000 * 60 * 5,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#81BC06]"></div>
          <p className="text-slate-500 font-medium animate-pulse">Fetching company profile and scraped details...</p>
        </div>
      </div>
    );
  }

  if (error || !company) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white p-6">
        <div className="text-center">
          <h2 className="text-xl font-bold text-slate-800 mb-2">Company profile not found</h2>
          <p className="text-slate-500 mb-6">The company could not be loaded from the current datasets.</p>
          <button
            onClick={() => navigate("/")}
            className="bg-[#81BC06] text-white px-6 py-2 rounded-lg font-bold"
          >
            Go Back Home
          </button>
        </div>
      </div>
    );
  }

  const latestAnnouncement = company.announcementHistory?.[0];
  const addresses = company.addresses?.length
    ? company.addresses
    : company.registeredAddress && company.registeredAddress !== "N/A"
      ? [
          {
            type: "Registered Address",
            line1: company.registeredAddress,
            line2: "",
            line3: "",
            line4: "",
            locality: "",
            district: "",
            city: "",
            state: "",
            postalCode: "",
            country: "",
            raw: company.registeredAddress,
          },
        ]
      : [];

  const hasIBBIData =
    !!company.announcementType ||
    !!company.announcementDate ||
    !!company.applicant_name ||
    !!company.ip_name ||
    (company.announcementHistory && company.announcementHistory.length > 0);

  const tabs = ["Overview"];
  if (addresses.length > 0) tabs.push("Addresses");
  if (company.mapLocation || (company.registeredAddress && company.registeredAddress !== "N/A")) tabs.push("Map");
  if (company.charges && company.charges.length > 0) tabs.push("Charges");
  if (hasIBBIData) tabs.push("IBBI");
  tabs.push("Source");

  return (
    <div className="bg-[#F4F7F9] min-h-screen">
      <div className="container mx-auto px-4 py-8">
        <IBBICorporateProcess company={company} />
      </div>
      <AIChatAssistant company={company} />
    </div>
  );
};

const openFieldInsight = (
  setInsight: (content: InsightContent) => void,
  title: string,
  value: string,
  description: string,
  extras: Array<{ label: string; value: string }> = [],
) => {
  setInsight({
    title,
    description,
    facts: [{ label: "Value", value }, ...extras],
  });
};

const SectionTitle = ({ title }: { title: string }) => (
  <h3 className="mb-3 text-xs font-black uppercase tracking-[0.18em] text-slate-800">{title}</h3>
);

const MetricCard = ({
  label,
  value,
  onClick,
}: {
  label: string;
  value: string;
  onClick?: () => void;
}) => {
  if (!value || value === "N/A") return null;
  return (
    <button type="button" onClick={onClick} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left transition hover:border-[#81BC06]">
      <p className="text-[9px] font-black uppercase tracking-[0.15em] text-slate-400">{label}</p>
      <p className="mt-1 text-sm font-black text-slate-900">{value}</p>
    </button>
  );
};

const InfoRow = ({
  label,
  value,
  onClick,
}: {
  label: string;
  value: string;
  onClick?: () => void;
}) => {
  if (!value || value === "N/A") return null;
  return (
    <button type="button" onClick={onClick} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-left transition hover:border-[#81BC06]">
      <p className="text-[9px] font-black uppercase tracking-[0.15em] text-slate-400">{label}</p>
      <p className="mt-1 text-xs font-bold text-slate-900 break-words">{value}</p>
    </button>
  );
};

const QuickRow = ({
  icon,
  label,
  value,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  onClick?: () => void;
}) => {
  if (!value || value === "N/A" || value === "0") return null;
  return (
    <button type="button" onClick={onClick} className="flex w-full items-start gap-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-left transition hover:border-[#81BC06]">
      <div className="mt-0.5 text-[#81BC06]">{icon}</div>
      <div>
        <p className="text-[9px] font-black uppercase tracking-[0.15em] text-slate-400">{label}</p>
        <p className="mt-1 text-xs font-bold text-slate-900 break-words">{value}</p>
      </div>
    </button>
  );
};

const AddressTable = ({ addresses, onInspect }: { addresses: CompanyAddress[]; onInspect?: (address: CompanyAddress) => void }) => {
  if (!addresses.length) {
    return <EmptyState text="No address data available." />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-100">
      <table className="w-full text-xs">
        <thead className="bg-slate-50">
          <tr className="text-left text-[10px] uppercase tracking-[0.15em] text-slate-400">
            <th className="px-3 py-2">Type</th>
            <th className="px-3 py-2">Address</th>
            <th className="px-3 py-2">City</th>
            <th className="px-3 py-2">State</th>
            <th className="px-3 py-2">Postal</th>
            <th className="px-3 py-2">Country</th>
          </tr>
        </thead>
        <tbody>
          {addresses.map((address, index) => (
            <tr key={`${address.type}-${index}`} className="border-t border-slate-100 cursor-pointer hover:bg-slate-50" onClick={() => onInspect?.(address)}>
              <td className="px-3 py-2 font-bold text-slate-700">{address.type}</td>
              <td className="px-3 py-2 text-slate-600">{address.raw || [address.line1, address.line2, address.line3, address.line4].filter(Boolean).join(", ")}</td>
              <td className="px-3 py-2 text-slate-600">{address.city && address.city !== "N/A" ? address.city : "-"}</td>
              <td className="px-3 py-2 text-slate-600">{address.state && address.state !== "N/A" ? address.state : "-"}</td>
              <td className="px-3 py-2 text-slate-600">{address.postalCode && address.postalCode !== "N/A" ? address.postalCode : "-"}</td>
              <td className="px-3 py-2 text-slate-600">{address.country && address.country !== "N/A" ? address.country : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};



const ChargesTable = ({ charges, onInspect }: { charges: Charge[]; onInspect?: (charge: Charge) => void }) => {
  if (!charges.length) {
    return <EmptyState text="No charge data available." />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-100">
      <table className="w-full text-xs">
        <thead className="bg-slate-50">
          <tr className="text-left text-[10px] uppercase tracking-[0.15em] text-slate-400">
            <th className="px-3 py-2">Charge ID</th>
            <th className="px-3 py-2">Holder</th>
            <th className="px-3 py-2">Amount</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Creation</th>
            <th className="px-3 py-2">Modified / Satisfied</th>
            <th className="px-3 py-2">Assets</th>
          </tr>
        </thead>
        <tbody>
          {charges.map((charge, index) => (
            <tr key={`${charge.chargeId}-${index}`} className="border-t border-slate-100 cursor-pointer hover:bg-slate-50" onClick={() => onInspect?.(charge)}>
              <td className="px-3 py-2 text-slate-700 font-bold">{charge.chargeId}</td>
              <td className="px-3 py-2 text-slate-700">{charge.bankName}</td>
              <td className="px-3 py-2 text-slate-600">{charge.amount && charge.amount > 0 ? formatToCr(charge.amount) : "-"}</td>
              <td className="px-3 py-2 text-slate-600">{charge.status ? charge.status : "-"}</td>
              <td className="px-3 py-2 text-slate-600">{charge.creationDate && charge.creationDate !== "N/A" ? charge.creationDate : "-"}</td>
              <td className="px-3 py-2 text-slate-600">{charge.modificationDate && charge.modificationDate !== "N/A" ? charge.modificationDate : "-"}</td>
              <td className="px-3 py-2 text-slate-600">{charge.assetsSecured && charge.assetsSecured !== "N/A" ? charge.assetsSecured : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const EmptyState = ({ text }: { text: string }) => (
  <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center text-xs text-slate-500">
    {text}
  </div>
);

const DataBox = ({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) => {
  if (!value || value === "N/A") return null;
  return (
    <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
      <div className="flex items-center gap-2 mb-1 text-[#81BC06]">
        {icon}
        <span className="text-[9px] uppercase font-black tracking-widest text-slate-400">{label}</span>
      </div>
      <p className="text-slate-800 font-black text-sm break-words">{value}</p>
    </div>
  );
};

const SourceMeta = ({ label, value }: { label: string; value: string }) => {
  if (!value || value === "N/A") return null;
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-bold text-slate-900 text-right">{value}</span>
    </div>
  );
};

const SourceCard = ({ source }: { source: CompanyDataSource }) => (
  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-xs font-bold text-slate-800">{source.name}</p>
      <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-600">{source.status}</span>
    </div>
    <p className="mt-1 text-[11px] text-slate-500">{source.portalType} | {source.mode}</p>
    {source.note && <p className="mt-1 text-[11px] text-slate-600">{source.note}</p>}
    {source.url && (
      <a href={source.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[11px] font-bold text-[#81BC06] hover:underline">
        Open source
        <ArrowUpRight className="h-3.5 w-3.5" />
      </a>
    )}
  </div>
);

const NewsList = ({ news, onInspect }: { news: NewsItem[]; onInspect?: (item: NewsItem) => void }) => {
  if (!news.length) {
    return <EmptyState text="No latest public news or registry updates are available right now." />;
  }

  return (
    <div className="space-y-2.5">
      {news.map((item) => (
        <div
          key={item.id}
          role="button"
          tabIndex={0}
          onClick={() => onInspect?.(item)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              onInspect?.(item);
            }
          }}
          className="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-[#81BC06]"
        >
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-[#81BC06]">
              <Newspaper className="w-4 h-4" />
              <span className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-500">{item.source}</span>
            </div>
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">{item.date}</span>
          </div>
          <h3 className="mt-2 text-sm font-black text-slate-900">{item.title}</h3>
          <p className="mt-1 text-xs leading-5 text-slate-600">{item.summary}</p>
          {item.url && (
            <a
              href={item.url}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex items-center gap-2 text-xs font-bold text-[#81BC06] hover:underline"
            >
              Open update
              <ArrowUpRight className="w-4 h-4" />
            </a>
          )}
        </div>
      ))}
    </div>
  );
};

const resolveDocumentUrl = (url?: string) => {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${API_BASE_URL}${url}`;
};

const DocumentsList = ({ documents, onInspect }: { documents: CompanyDocument[]; onInspect?: (document: CompanyDocument) => void }) => {
  if (!documents.length) {
    return <EmptyState text="No public or generated documents are available right now." />;
  }

  return (
    <div className="grid gap-2.5 md:grid-cols-2">
      {documents.map((document) => (
        <div
          key={`${document.formId}-${document.fileName}`}
          role="button"
          tabIndex={0}
          onClick={() => onInspect?.(document)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              onInspect?.(document);
            }
          }}
          className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-[#81BC06]"
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[9px] font-black uppercase tracking-[0.15em] text-slate-400">{document.category}</p>
              <h3 className="mt-1 text-xs font-black text-slate-900 break-words">{document.fileName}</h3>
            </div>
            <Download className="w-5 h-5 text-[#81BC06]" />
          </div>
          <div className="mt-3 space-y-1 text-xs text-slate-600">
            <SourceMeta label="Source" value={document.source || "N/A"} />
            <SourceMeta label="Date" value={document.dateOfFiling || "N/A"} />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {document.url && (
              <a
                href={resolveDocumentUrl(document.url)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:border-[#81BC06]"
              >
                Open
                <ArrowUpRight className="w-4 h-4" />
              </a>
            )}
            {document.downloadUrl && (
              <a
                href={resolveDocumentUrl(document.downloadUrl)}
                target="_blank"
                rel="noreferrer"
                download
                className="inline-flex items-center gap-2 rounded-lg bg-[#81BC06] px-3 py-1.5 text-xs font-bold text-white"
              >
                Download
                <Download className="w-4 h-4" />
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

const MapSection = ({
  companyName,
  mapLocation,
  fallbackAddress,
}: {
  companyName: string;
  mapLocation?: {
    latitude?: number;
    longitude?: number;
    formattedAddress: string;
    embedUrl: string;
    mapUrl: string;
  };
  fallbackAddress: string;
}) => {
  if (!mapLocation) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-sm text-slate-500">
        <div className="flex items-start gap-3">
          <MapPinned className="w-5 h-5 text-[#81BC06] mt-0.5" />
          <div>
            <p className="font-bold text-slate-800">Exact map location not available yet</p>
            <p className="mt-2">Address found: {fallbackAddress || "N/A"}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="grid lg:grid-cols-[1.2fr_0.8fr] gap-6">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
        <iframe
          title={`${companyName} map`}
          src={mapLocation.embedUrl}
          className="h-[360px] w-full border-0"
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
        />
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-6">
        <div className="flex items-center gap-2 text-[#81BC06]">
          <MapPinned className="w-5 h-5" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Geo Location</span>
        </div>
        <p className="mt-4 text-sm leading-7 text-slate-700">{mapLocation.formattedAddress}</p>
        {(mapLocation.latitude !== undefined || mapLocation.longitude !== undefined) && (
          <div className="mt-5 space-y-3">
            <SourceMeta label="Latitude" value={mapLocation.latitude !== undefined ? String(mapLocation.latitude) : "N/A"} />
            <SourceMeta label="Longitude" value={mapLocation.longitude !== undefined ? String(mapLocation.longitude) : "N/A"} />
          </div>
        )}
        <a
          href={mapLocation.mapUrl}
          target="_blank"
          rel="noreferrer"
          className="mt-5 inline-flex items-center gap-2 text-sm font-bold text-[#81BC06] hover:underline"
        >
          Open full map
          <ArrowUpRight className="w-4 h-4" />
        </a>
      </div>
    </div>
  );
};

const AnnouncementCard = ({ announcement, onInspect }: { announcement: AnnouncementRecord; onInspect?: () => void }) => (
  <button type="button" onClick={onInspect} className="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-[#81BC06]">
    <div className="flex flex-wrap items-center gap-3">
      <StatusBadge status={announcement.status} />
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">{announcement.announcementDate}</p>
    </div>
    <h3 className="mt-2 text-sm font-black text-slate-900">{announcement.announcementType}</h3>
    <div className="mt-3 grid md:grid-cols-2 gap-2 text-xs">
      <SourceMeta label="Applicant" value={announcement.applicantName} />
      <SourceMeta label="IP" value={announcement.insolvencyProfessional} />
      <SourceMeta label="Submission deadline" value={announcement.lastDateOfSubmission} />
      <SourceMeta label="CIN" value={announcement.cin} />
    </div>
    <p className="mt-3 text-xs leading-5 text-slate-600">{announcement.insolvencyProfessionalAddress}</p>
  </button>
);

export default CompanyDetail;
