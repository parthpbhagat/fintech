import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowUpRight, BarChart3, Building2, MapPin, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import DataInsightSheet, { type InsightContent, type InsightSection } from "@/components/DataInsightSheet";
import { fetchCompanyDirectory, fetchIBBICompanyDetails, searchIBBICompanies } from "@/services/ibbiService";
import type { Charge, Company, CompanyAddress, CompanyDocument, Director, NewsItem } from "@/data/types";

const compareFilters = {
  status: [
    { label: "All Status", value: "all" },
    { label: "Active", value: "Active" },
    { label: "Inactive", value: "Inactive" },
    { label: "Under CIRP", value: "Under CIRP" },
    { label: "Liquidation", value: "Liquidation" },
  ],
  type: [
    { label: "All Types", value: "all" },
    { label: "Private", value: "Private" },
    { label: "Public", value: "Public" },
    { label: "LLP", value: "LLP" },
    { label: "OPC", value: "OPC" },
  ],
  source: [
    { label: "All Sources", value: "all" },
    { label: "Master", value: "master" },
    { label: "Master + IBBI", value: "master+ibbi" },
    { label: "IBBI", value: "ibbi" },
    { label: "Claims", value: "claims" },
  ],
} as const;

const currencyFormatter = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const moneyOrNa = (value: number) => (value ? `Rs ${currencyFormatter.format(value)}` : "N/A");

type CompareRowConfig = {
  label: string;
  getValue: (company: Company) => string;
  shouldShow?: (companies: Company[]) => boolean;
  description: string;
};

const hasMeaningfulText = (value: string) => {
  const normalized = value.trim().toUpperCase();
  return normalized !== "" && normalized !== "N/A" && normalized !== "NA" && normalized !== "0";
};

const compareRowConfigs: CompareRowConfig[] = [
  {
    label: "Status",
    getValue: (company) => company.status || "N/A",
    description: "Current operating or insolvency status from the latest enriched company profile.",
  },
  {
    label: "Type",
    getValue: (company) => company.type || "N/A",
    description: "Legal entity type such as Private, Public, LLP, or OPC.",
  },
  {
    label: "Category",
    getValue: (company) => company.category || "N/A",
    description: "Entity category or latest insolvency/registry classification.",
  },
  {
    label: "Incorporation",
    getValue: (company) => company.incorporationDate || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.incorporationDate || "")),
    description: "Date of incorporation aggregated from the best available public source.",
  },
  {
    label: "ROC",
    getValue: (company) => company.rocCode || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.rocCode || "")),
    description: "Registrar of Companies mapped from public registry mirrors.",
  },
  {
    label: "Industry",
    getValue: (company) => company.industry || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.industry || "")),
    description: "Industry or activity description collected from public company profiles.",
  },
  {
    label: "Authorised Capital",
    getValue: (company) => (company.authCap ? `Rs ${currencyFormatter.format(company.authCap)}` : "N/A"),
    shouldShow: (companies) => companies.some((company) => company.authCap > 0),
    description: "Authorised capital fetched from public company profile sources when available.",
  },
  {
    label: "Paid Up Capital",
    getValue: (company) => (company.puc ? `Rs ${currencyFormatter.format(company.puc)}` : "N/A"),
    shouldShow: (companies) => companies.some((company) => company.puc > 0),
    description: "Paid up capital fetched from public company profile sources when available.",
  },
  {
    label: "Last AGM",
    getValue: (company) => company.lastAGMDate || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.lastAGMDate || "")),
    description: "Latest AGM filing date currently available for the company.",
  },
  {
    label: "Last B/S",
    getValue: (company) => company.lastBSDate || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.lastBSDate || "")),
    description: "Latest balance sheet date currently available for the company.",
  },
  {
    label: "Directors",
    getValue: (company) => String(company.directors.length),
    shouldShow: (companies) => companies.some((company) => company.directors.length > 0),
    description: "Total active directors or designated partners mapped from public sources.",
  },
  {
    label: "Charges",
    getValue: (company) => String(company.charges.length),
    shouldShow: (companies) => companies.some((company) => company.charges.length > 0),
    description: "Total open or satisfied charge entries currently available.",
  },
  {
    label: "Address",
    getValue: (company) => company.registeredAddress || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.registeredAddress || "")),
    description: "Registered address from the strongest available public source.",
  },
  {
    label: "Documents",
    getValue: (company) => String(company.documents.length),
    shouldShow: (companies) => companies.some((company) => company.documents.length > 0),
    description: "Generated and source-linked documents currently available for download/open.",
  },
  {
    label: "Latest Updates",
    getValue: (company) => String(company.news.length),
    shouldShow: (companies) => companies.some((company) => company.news.length > 0),
    description: "Latest public news mentions and registry updates currently mapped.",
  },
  {
    label: "Source",
    getValue: (company) => company.sourceSection || "N/A",
    description: "Primary source family from which the company was discovered.",
  },
];

const buildCompanyInsight = (company: Company): InsightContent => ({
  title: company.name,
  subtitle: company.cin || "N/A",
  description: company.overview,
  facts: [
    { label: "Status", value: company.status || "N/A" },
    { label: "Type", value: company.type || "N/A" },
    { label: "ROC", value: company.rocCode || "N/A" },
    { label: "Industry", value: company.industry || "N/A" },
    { label: "Address", value: company.registeredAddress || "N/A" },
    { label: "Directors", value: String(company.directors.length) },
    { label: "Charges", value: String(company.charges.length) },
    { label: "Documents", value: String(company.documents.length) },
    { label: "Latest Updates", value: String(company.news.length) },
  ],
});

const buildDirectorSections = (directors: Director[]): InsightSection[] =>
  directors.map((director, index) => ({
    title: `${index + 1}. ${director.name || "Director"}`,
    facts: [
      { label: "DIN", value: director.din || "N/A" },
      { label: "Designation", value: director.designation || "N/A" },
      { label: "Appointment Date", value: director.appointmentDate || "N/A" },
      { label: "Status", value: director.status || "N/A" },
      { label: "Directorships", value: director.totalDirectorships || "N/A" },
      { label: "Disqualified 164", value: director.disqualified164 || "N/A" },
      { label: "DIN Deactivated", value: director.dinDeactivated || "N/A" },
      { label: "Profile Link", value: director.profileUrl || "N/A" },
    ],
  }));

const buildChargeSections = (charges: Charge[]): InsightSection[] =>
  charges.map((charge, index) => ({
    title: `${index + 1}. ${charge.bankName || "Charge Holder"}`,
    facts: [
      { label: "Charge ID", value: charge.chargeId || "N/A" },
      { label: "Amount", value: moneyOrNa(charge.amount) },
      { label: "Status", value: charge.status || "N/A" },
      { label: "Creation Date", value: charge.creationDate || "N/A" },
      { label: "Modified Date", value: charge.modificationDate || "N/A" },
      { label: "Outstanding Years", value: charge.outstandingYears || "N/A" },
      { label: "Assets", value: charge.assetsSecured || "N/A" },
    ],
  }));

const buildDocumentSections = (documents: CompanyDocument[]): InsightSection[] =>
  documents.map((document, index) => ({
    title: `${index + 1}. ${document.fileName || "Document"}`,
    facts: [
      { label: "Category", value: document.category || "N/A" },
      { label: "Source", value: document.source || "N/A" },
      { label: "Year", value: document.year ? String(document.year) : "N/A" },
      { label: "Date", value: document.dateOfFiling || "N/A" },
      { label: "Open URL", value: document.url || "N/A" },
      { label: "Download URL", value: document.downloadUrl || "N/A" },
    ],
  }));

const buildNewsSections = (items: NewsItem[]): InsightSection[] =>
  items.map((item, index) => ({
    title: `${index + 1}. ${item.title || "Update"}`,
    facts: [
      { label: "Source", value: item.source || "N/A" },
      { label: "Date", value: item.date || "N/A" },
      { label: "Summary", value: item.summary || "N/A" },
      { label: "Link", value: item.url || "N/A" },
    ],
  }));

const buildAddressSections = (addresses: CompanyAddress[]): InsightSection[] =>
  addresses.map((address, index) => ({
    title: `${index + 1}. ${address.type || "Address"}`,
    facts: [
      { label: "Full Address", value: address.raw || "N/A" },
      { label: "Line 1", value: address.line1 || "N/A" },
      { label: "Line 2", value: address.line2 || "N/A" },
      { label: "Line 3", value: address.line3 || "N/A" },
      { label: "Line 4", value: address.line4 || "N/A" },
      { label: "District", value: address.district || "N/A" },
      { label: "City", value: address.city || "N/A" },
      { label: "State", value: address.state || "N/A" },
      { label: "Postal Code", value: address.postalCode || "N/A" },
      { label: "Country", value: address.country || "N/A" },
    ],
  }));

const buildRowInsight = (rowLabel: string, description: string, value: string, company: Company): InsightContent => {
  const baseFacts = [
    { label: "Selected Value", value },
    { label: "Company", value: company.name || "N/A" },
    { label: "CIN/LLPIN", value: company.cin || "N/A" },
    { label: "Status", value: company.status || "N/A" },
    { label: "Source", value: company.sourceSection || "N/A" },
  ];

  switch (rowLabel) {
    case "Directors":
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: `${company.directors.length} record(s)`,
        description,
        facts: baseFacts,
        sections: buildDirectorSections(company.directors),
      };
    case "Charges":
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: `${company.charges.length} record(s)`,
        description,
        facts: baseFacts,
        sections: buildChargeSections(company.charges),
      };
    case "Documents":
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: `${company.documents.length} record(s)`,
        description,
        facts: baseFacts,
        sections: buildDocumentSections(company.documents),
      };
    case "Latest Updates":
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: `${company.news.length} record(s)`,
        description,
        facts: baseFacts,
        sections: buildNewsSections(company.news),
      };
    case "Address":
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: company.registeredAddress || "N/A",
        description,
        facts: baseFacts,
        sections: buildAddressSections(company.addresses || []),
      };
    case "Authorised Capital":
    case "Paid Up Capital":
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: value,
        description,
        facts: [
          ...baseFacts,
          { label: "Last AGM", value: company.lastAGMDate || "N/A" },
          { label: "Last B/S", value: company.lastBSDate || "N/A" },
          { label: "Category", value: company.category || "N/A" },
        ],
      };
    default:
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: company.cin || "N/A",
        description,
        facts: [
          ...baseFacts,
          { label: rowLabel, value },
          { label: "Type", value: company.type || "N/A" },
          { label: "ROC", value: company.rocCode || "N/A" },
          { label: "Industry", value: company.industry || "N/A" },
          { label: "Registered Address", value: company.registeredAddress || "N/A" },
        ],
      };
  }
};

const ComparePage = () => {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [leftQuery, setLeftQuery] = useState("");
  const [rightQuery, setRightQuery] = useState("");
  const [leftSuggestions, setLeftSuggestions] = useState<Company[]>([]);
  const [rightSuggestions, setRightSuggestions] = useState<Company[]>([]);
  const [leftCompany, setLeftCompany] = useState<Company | null>(null);
  const [rightCompany, setRightCompany] = useState<Company | null>(null);
  const [activeInsight, setActiveInsight] = useState<InsightContent | null>(null);

  const normalizedFilters = useMemo(
    () => ({
      status: statusFilter === "all" ? undefined : statusFilter,
      type: typeFilter === "all" ? undefined : typeFilter,
      source: sourceFilter === "all" ? undefined : sourceFilter,
    }),
    [sourceFilter, statusFilter, typeFilter],
  );

  const { data: browseCompanies = [] } = useQuery({
    queryKey: ["compare-browse-companies", normalizedFilters],
    queryFn: () =>
      fetchCompanyDirectory({
        ...normalizedFilters,
        limit: 20,
      }),
    staleTime: 1000 * 60 * 5,
  });

  useEffect(() => {
    const loadSuggestions = async (query: string, setter: (companies: Company[]) => void) => {
      if (query.trim().length < 2) {
        setter([]);
        return;
      }
      const results = await searchIBBICompanies(query, 8, normalizedFilters);
      setter(results);
    };

    const leftTimeout = window.setTimeout(() => {
      void loadSuggestions(leftQuery, setLeftSuggestions);
    }, 220);
    const rightTimeout = window.setTimeout(() => {
      void loadSuggestions(rightQuery, setRightSuggestions);
    }, 220);

    return () => {
      window.clearTimeout(leftTimeout);
      window.clearTimeout(rightTimeout);
    };
  }, [leftQuery, normalizedFilters, rightQuery]);

  const detailQueries = useQueries({
    queries: [leftCompany?.id, rightCompany?.id].map((companyId, index) => ({
      queryKey: ["compare-company-detail", companyId, index],
      queryFn: () => fetchIBBICompanyDetails(companyId || ""),
      enabled: !!companyId,
      staleTime: 1000 * 60 * 5,
    })),
  });

  const comparedCompanies = useMemo(() => {
    const companies: Company[] = [];
    const candidates = [leftCompany, rightCompany];
    detailQueries.forEach((query, index) => {
      const baseCompany = candidates[index];
      if (!baseCompany) return;
      companies.push((query.data as Company | null) || baseCompany);
    });
    return companies;
  }, [detailQueries, leftCompany, rightCompany]);

  const comparisonRows = useMemo(
    () =>
      compareRowConfigs
        .filter((row) => (row.shouldShow ? row.shouldShow(comparedCompanies) : true))
        .map((row) => ({
          label: row.label,
          description: row.description,
          values: comparedCompanies.map((company) => row.getValue(company)),
        })),
    [comparedCompanies],
  );

  return (
    <div className="min-h-screen bg-[#EEF3F8]">
      <div className="border-b border-slate-200 bg-white/90 px-4 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#81BC06]/10 text-[#81BC06]">
            <BarChart3 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-900">Compare Companies</h1>
            <p className="text-sm text-slate-500">Live enriched comparison with only meaningful rows shown.</p>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl space-y-6 px-4 py-8">
        <div className="grid gap-4 rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-3">
          <FilterSelect label="Status Filter" value={statusFilter} onChange={setStatusFilter} options={compareFilters.status} />
          <FilterSelect label="Type Filter" value={typeFilter} onChange={setTypeFilter} options={compareFilters.type} />
          <FilterSelect label="Source Filter" value={sourceFilter} onChange={setSourceFilter} options={compareFilters.source} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <CompanySelectorCard
            title="Company A"
            query={leftQuery}
            setQuery={setLeftQuery}
            selectedCompany={comparedCompanies[0] || leftCompany}
            onSelectCompany={(company) => {
              setLeftCompany(company);
              setLeftQuery(company.name);
              setLeftSuggestions([]);
            }}
            suggestions={leftSuggestions}
            browseCompanies={browseCompanies}
            onClear={() => {
              setLeftCompany(null);
              setLeftQuery("");
              setLeftSuggestions([]);
            }}
            onOpenInsight={(company) => setActiveInsight(buildCompanyInsight(company))}
          />
          <CompanySelectorCard
            title="Company B"
            query={rightQuery}
            setQuery={setRightQuery}
            selectedCompany={comparedCompanies[1] || rightCompany}
            onSelectCompany={(company) => {
              setRightCompany(company);
              setRightQuery(company.name);
              setRightSuggestions([]);
            }}
            suggestions={rightSuggestions}
            browseCompanies={browseCompanies}
            onClear={() => {
              setRightCompany(null);
              setRightQuery("");
              setRightSuggestions([]);
            }}
            onOpenInsight={(company) => setActiveInsight(buildCompanyInsight(company))}
          />
        </div>

        <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-6 py-5">
            <h2 className="text-sm font-black uppercase tracking-[0.22em] text-slate-700">Comparison Table</h2>
          </div>
          {comparedCompanies.length < 2 ? (
            <div className="px-6 py-16 text-center text-sm text-slate-500">Compare karva mate be companies select karo.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-4 text-left text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">Parameter</th>
                    {comparedCompanies.map((company) => (
                      <th key={company.id} className="px-4 py-4 text-left text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">
                        <button
                          type="button"
                          onClick={() => setActiveInsight(buildCompanyInsight(company))}
                          className="text-left hover:text-[#81BC06]"
                        >
                          {company.name}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {comparisonRows.map((row) => (
                    <tr key={row.label} className="border-t border-slate-100">
                      <td className="px-4 py-4 font-bold text-slate-700">{row.label}</td>
                      {row.values.map((value, index) => {
                        const company = comparedCompanies[index];
                        return (
                          <td key={`${row.label}-${company.id}`} className="px-4 py-4">
                            <button
                              type="button"
                              onClick={() =>
                                setActiveInsight(buildRowInsight(row.label, row.description, value, company))
                              }
                              className="w-full rounded-xl px-3 py-2 text-left text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
                            >
                              {value}
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <DataInsightSheet open={!!activeInsight} onOpenChange={(open) => !open && setActiveInsight(null)} content={activeInsight} />
    </div>
  );
};

const FilterSelect = ({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly { label: string; value: string }[];
}) => (
  <div>
    <p className="mb-2 text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">{label}</p>
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-11 rounded-xl border-slate-200">
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  </div>
);

const CompanySelectorCard = ({
  title,
  query,
  setQuery,
  selectedCompany,
  onSelectCompany,
  suggestions,
  browseCompanies,
  onClear,
  onOpenInsight,
}: {
  title: string;
  query: string;
  setQuery: (value: string) => void;
  selectedCompany: Company | null;
  onSelectCompany: (company: Company) => void;
  suggestions: Company[];
  browseCompanies: Company[];
  onClear: () => void;
  onOpenInsight: (company: Company) => void;
}) => (
  <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-center justify-between gap-3">
      <div>
        <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">{title}</p>
        <h2 className="mt-1 text-lg font-black text-slate-900">{selectedCompany?.name || "Select company"}</h2>
      </div>
      {selectedCompany && (
        <Button variant="outline" onClick={onClear} className="rounded-xl border-slate-200">
          Clear
        </Button>
      )}
    </div>

    <div className="relative mt-4">
      <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search company name or CIN" className="h-12 rounded-xl border-slate-200 pl-11" />
    </div>

    <div className="mt-4 space-y-2">
      {(suggestions.length > 0 ? suggestions : browseCompanies.slice(0, 6)).map((company) => (
        <button
          key={`${title}-${company.id}`}
          type="button"
          onClick={() => onSelectCompany(company)}
          className="flex w-full items-start gap-3 rounded-xl border border-slate-100 px-4 py-3 text-left hover:border-[#81BC06] hover:bg-[#81BC06]/5"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#81BC06]/10 font-black text-[#81BC06]">
            {company.name[0]}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-black uppercase tracking-wide text-slate-900">{company.name}</p>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] font-medium text-slate-500">
              <span className="inline-flex items-center gap-1">
                <Building2 className="h-3 w-3" />
                {company.cin || "N/A"}
              </span>
              <span>{company.status}</span>
            </div>
          </div>
        </button>
      ))}
    </div>

    {selectedCompany && (
      <div className="mt-5 rounded-2xl border border-slate-100 bg-slate-50 p-4 text-sm">
        <button type="button" onClick={() => onOpenInsight(selectedCompany)} className="w-full text-left">
          <div className="flex items-center gap-2 text-slate-700">
            <MapPin className="h-4 w-4 text-[#81BC06]" />
            <span className="font-semibold">{selectedCompany.registeredAddress || "N/A"}</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500">
            <span>Type: {selectedCompany.type || "N/A"}</span>
            <span>Source: {selectedCompany.sourceSection || "N/A"}</span>
            <span>Industry: {selectedCompany.industry || "N/A"}</span>
          </div>
        </button>
        <button
          type="button"
          onClick={() => window.open(`/company/${selectedCompany.id}`, "_blank", "noopener,noreferrer")}
          className="mt-4 inline-flex items-center gap-2 text-sm font-bold text-[#81BC06] hover:underline"
        >
          Open full profile
          <ArrowUpRight className="h-4 w-4" />
        </button>
      </div>
    )}
  </div>
);

export default ComparePage;
