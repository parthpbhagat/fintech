import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowUpRight, BarChart3, Building2, MapPin, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ShowMoreContainer } from "@/components/ShowMoreContainer";
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

const moneyOrNa = (value?: number) => {
  if (value === undefined || value === null || value === 0) return "N/A";
  const cr = value / 10000000;
  return `₹ ${cr.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Cr`;
};

type CompareRowConfig = {
  label: string;
  getValue: (company: Company) => string;
  shouldShow?: (companies: Company[]) => boolean;
  description: string;
};

const hasMeaningfulText = (value: string) => {
  const normalized = (value || "").trim().toUpperCase();
  return normalized !== "" && normalized !== "N/A" && normalized !== "NA" && normalized !== "0";
};

const formatCount = (value?: number) => String(value || 0);

const buildJoinedAddress = (company: Company) =>
  [company.registeredAddress, company.businessAddress].filter((value, index, items) => hasMeaningfulText(value || "") && items.indexOf(value) === index).join(" | ") || "N/A";

const compareRowConfigs: CompareRowConfig[] = [
  {
    label: "CIN / LLPIN",
    getValue: (company) => company.cin || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.cin || "")),
    description: "Primary company identifier from registry and enriched source profiles.",
  },
  {
    label: "PAN",
    getValue: (company) => company.pan || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.pan || "")),
    description: "Permanent Account Number when it is available in the public company profile data.",
  },
  {
    label: "Registration Number",
    getValue: (company) => company.registrationNumber || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.registrationNumber || "")),
    description: "Registration number captured from public registry mirrors.",
  },
  {
    label: "Status",
    getValue: (company) => company.status || "",
    shouldShow: (companies) => companies.some((c) => hasMeaningfulText(c.status || "")),
    description: "Current operating or insolvency status from the latest enriched company profile.",
  },
  {
    label: "Type",
    getValue: (company) => company.type || "",
    shouldShow: (companies) => companies.some((c) => hasMeaningfulText(c.status || "")),
    description: "Legal entity type such as Private, Public, LLP, or OPC.",
  },
  {
    label: "Category",
    getValue: (company) => company.category || "",
    shouldShow: (companies) => companies.some((c) => hasMeaningfulText(c.category || "")),
    description: "Entity category or latest insolvency/registry classification.",
  },
  {
    label: "Subcategory",
    getValue: (company) => company.companySubcategory || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.companySubcategory || "")),
    description: "Company subcategory carried from the enriched public profile.",
  },
  {
    label: "Listing Status",
    getValue: (company) => company.listingStatus || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.listingStatus || "")),
    description: "Listed or unlisted status when available in the source data.",
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
    label: "NIC Code",
    getValue: (company) => company.nicCode || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.nicCode || "")),
    description: "NIC code fetched from the enriched company profile, when available.",
  },
  {
    label: "Authorised Capital",
    getValue: (company) => moneyOrNa(company.authCap),
    shouldShow: (companies) => companies.some((company) => (company.authCap || 0) > 0),
    description: "Authorised share capital captured from registry mirrors.",
  },
  {
    label: "Paid Up Capital",
    getValue: (company) => moneyOrNa(company.puc),
    shouldShow: (companies) => companies.some((company) => (company.puc || 0) > 0),
    description: "Paid up share capital captured from registry mirrors.",
  },
  {
    label: "Last AGM",
    getValue: (company) => company.lastAGMDate || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.lastAGMDate || "")),
    description: "Latest annual general meeting date currently available.",
  },
  {
    label: "Last B/S",
    getValue: (company) => company.lastBSDate || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.lastBSDate || "")),
    description: "Latest balance sheet date currently available for the company.",
  },
  {
    label: "Directors",
    getValue: (company) => formatCount(company.directors?.length),
    shouldShow: (companies) => companies.some((company) => (company.directors?.length || 0) > 0),
    description: "Total active directors or designated partners mapped from public sources.",
  },
  {
    label: "Charges",
    getValue: (company) => formatCount(company.charges?.length),
    shouldShow: (companies) => companies.some((company) => (company.charges?.length || 0) > 0),
    description: "Total open or satisfied charge entries currently available.",
  },
  {
    label: "Email",
    getValue: (company) => company.email || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.email || "")),
    description: "Public email captured from the enriched company profile.",
  },
  {
    label: "Phone",
    getValue: (company) => company.phone || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.phone || "")),
    description: "Public phone number captured from the enriched company profile.",
  },
  {
    label: "Website",
    getValue: (company) => company.website || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.website || "")),
    description: "Official company website when available.",
  },
  {
    label: "GSTIN",
    getValue: (company) => company.gstin || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.gstin || "")),
    description: "GSTIN from the enriched company profile, when available.",
  },
  {
    label: "Address",
    getValue: (company) => buildJoinedAddress(company),
    shouldShow: (companies) =>
      companies.some((company) => hasMeaningfulText(company.registeredAddress || "") || hasMeaningfulText(company.businessAddress || "")),
    description: "Registered and business address details from the strongest available public source.",
  },
  {
    label: "Filing Status",
    getValue: (company) => company.filingStatus || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.filingStatus || "")),
    description: "Recent filing status mapped from public company profile sources.",
  },
  {
    label: "Active Compliance",
    getValue: (company) => company.activeCompliance || "N/A",
    shouldShow: (companies) => companies.some((company) => hasMeaningfulText(company.activeCompliance || "")),
    description: "Compliance flag captured from public profile data.",
  },
  {
    label: "Documents",
    getValue: (company) => formatCount(company.documents?.length),
    shouldShow: (companies) => companies.some((company) => (company.documents?.length || 0) > 0),
    description: "Generated and source-linked documents currently available for download/open.",
  },
  {
    label: "Latest Updates",
    getValue: (company) => formatCount(company.news?.length),
    shouldShow: (companies) => companies.some((company) => (company.news?.length || 0) > 0),
    description: "Latest public news mentions and registry updates currently mapped.",
  },
  {
    label: "Source",
    getValue: (company) => company.sourceSection || "",
    shouldShow: (companies) => companies.some((c) => hasMeaningfulText(c.sourceSection || "")),
    description: "Primary source family from which the company was discovered.",
  },
];

const buildCompanyInsight = (company: Company): InsightContent => ({
  title: company.name,
  subtitle: company.cin || "N/A",
  description: company.overview,
  facts: [
    { label: "PAN", value: company.pan || "N/A" },
    { label: "Status", value: company.status || "N/A" },
    { label: "Type", value: company.type || "N/A" },
    { label: "Category", value: company.category || "N/A" },
    { label: "Subcategory", value: company.companySubcategory || "N/A" },
    { label: "Registration No.", value: company.registrationNumber || "N/A" },
    { label: "ROC", value: company.rocCode || "N/A" },
    { label: "Industry", value: company.industry || "N/A" },
    { label: "Email", value: company.email || "N/A" },
    { label: "Phone", value: company.phone || "N/A" },
    { label: "Website", value: company.website || "N/A" },
    { label: "GSTIN", value: company.gstin || "N/A" },
    { label: "Registered Address", value: company.registeredAddress || "N/A" },
    { label: "Business Address", value: company.businessAddress || "N/A" },
    { label: "Directors", value: formatCount(company.directors?.length) },
    { label: "Charges", value: formatCount(company.charges?.length) },
    { label: "Documents", value: formatCount(company.documents?.length) },
    { label: "Latest Updates", value: formatCount(company.news?.length) },
  ],
  sections: [
    {
      title: "Master Detail",
      facts: [
        { label: "CIN / LLPIN", value: company.cin || "N/A" },
        { label: "PAN", value: company.pan || "N/A" },
        { label: "Registration Number", value: company.registrationNumber || "N/A" },
        { label: "Incorporation Date", value: company.incorporationDate || "N/A" },
        { label: "Listing Status", value: company.listingStatus || "N/A" },
        { label: "NIC Code", value: company.nicCode || "N/A" },
        { label: "Filing Status", value: company.filingStatus || "N/A" },
        { label: "Active Compliance", value: company.activeCompliance || "N/A" },
      ],
    },
    {
      title: "Contact Detail",
      facts: [
        { label: "Email", value: company.email || "N/A" },
        { label: "Phone", value: company.phone || "N/A" },
        { label: "Website", value: company.website || "N/A" },
        { label: "Registered Address", value: company.registeredAddress || "N/A" },
        { label: "Business Address", value: company.businessAddress || "N/A" },
      ],
    },
    ...(company.directors?.length ? buildDirectorSections(company.directors) : []),
    ...(company.addresses?.length ? buildAddressSections(company.addresses) : []),
    ...(company.charges?.length ? buildChargeSections(company.charges) : []),
    ...(company.documents?.length ? buildDocumentSections(company.documents) : []),
    ...(company.news?.length ? buildNewsSections(company.news) : []),
  ],
});

const buildDirectorSections = (directors: Director[]): InsightSection[] =>
  directors.map((director, index) => ({
    title: `${index + 1}. ${director.name || "Director"}`,
    facts: [
      { label: "DIN", value: director.din || "N/A" },
      { label: "Designation", value: director.designation || "N/A" },
      { label: "Appointment Date", value: director.date_of_appointment || "N/A" },
      { label: "Status", value: director.is_active ? "Active" : "Inactive" },
      { label: "Nationality", value: director.din_details?.nationality || "N/A" },
      { label: "Address", value: director.din_details?.address || "N/A" },
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
        subtitle: `${company.directors?.length || 0} record(s)`,
        description,
        facts: baseFacts,
        sections: company.directors ? buildDirectorSections(company.directors) : [],
      };
    case "Charges":
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: `${company.charges?.length || 0} record(s)`,
        description,
        facts: baseFacts,
        sections: company.charges ? buildChargeSections(company.charges) : [],
      };
    case "Documents":
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: `${company.documents?.length || 0} record(s)`,
        description,
        facts: baseFacts,
        sections: company.documents ? buildDocumentSections(company.documents) : [],
      };
    case "Latest Updates":
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: `${company.news?.length || 0} record(s)`,
        description,
        facts: baseFacts,
        sections: company.news ? buildNewsSections(company.news) : [],
      };
    case "Address":
      return {
        title: `${rowLabel} - ${company.name}`,
        subtitle: buildJoinedAddress(company),
        description,
        facts: [
          ...baseFacts,
          { label: "Registered Address", value: company.registeredAddress || "N/A" },
          { label: "Business Address", value: company.businessAddress || "N/A" },
        ],
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

  const { data: browseCompanies = [], error: browseCompaniesError } = useQuery({
    queryKey: ["compare-browse-companies", normalizedFilters],
    queryFn: () =>
      fetchCompanyDirectory({
        ...normalizedFilters,
        limit: 20,
      }),
    staleTime: 1000 * 60 * 5,
    retry: false,
  });

  useEffect(() => {
    const loadSuggestions = async (query: string, setter: (companies: Company[]) => void) => {
      if (query.trim().length < 2) {
        setter([]);
        return;
      }
      try {
        const results = await searchIBBICompanies(query, 8, normalizedFilters);
        setter(results);
      } catch (error) {
        console.error("Compare suggestions could not be loaded.", error);
        setter([]);
      }
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
      <div className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#81BC06]/10 text-[#81BC06]">
            <BarChart3 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-black text-slate-900">Compare Companies</h1>
            <p className="text-xs text-slate-500">Live enriched comparison with meaningful rows only.</p>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl space-y-4 px-4 py-4">
        {browseCompaniesError instanceof Error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-3 text-sm text-red-700">
            Compare list load na thai. {browseCompaniesError.message}
          </div>
        )}

        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-3">
          <FilterSelect label="Status Filter" value={statusFilter} onChange={setStatusFilter} options={compareFilters.status} />
          <FilterSelect label="Type Filter" value={typeFilter} onChange={setTypeFilter} options={compareFilters.type} />
          <FilterSelect label="Source Filter" value={sourceFilter} onChange={setSourceFilter} options={compareFilters.source} />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
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

        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-4 py-3">
            <h2 className="text-xs font-black uppercase tracking-[0.2em] text-slate-700">Comparison Table</h2>
          </div>
          {comparedCompanies.length < 2 ? (
            <div className="px-6 py-10 text-center text-sm text-slate-500">Compare karva mate be companies select karo.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] text-xs">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-3 text-left text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Parameter</th>
                    {comparedCompanies.map((company) => (
                      <th key={company.id} className="px-3 py-3 text-left text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">
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
                      <td className="px-3 py-2.5 font-bold text-slate-700 whitespace-nowrap">{row.label}</td>
                      {row.values.map((value, index) => {
                        const company = comparedCompanies[index];
                        return (
                          <td key={`${row.label}-${company.id}`} className="px-3 py-2">
                            <button
                              type="button"
                              onClick={() =>
                                setActiveInsight(buildRowInsight(row.label, row.description, value, company))
                              }
                              className="w-full rounded-lg px-2.5 py-1.5 text-left text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
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
    <p className="mb-1.5 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">{label}</p>
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-9 rounded-lg border-slate-200 text-xs">
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
  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-center justify-between gap-3">
      <div>
        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">{title}</p>
        <h2 className="mt-1 text-base font-black text-slate-900">{selectedCompany?.name || "Select company"}</h2>
      </div>
      {selectedCompany && (
        <Button variant="outline" onClick={onClear} className="h-8 rounded-lg border-slate-200 px-3 text-xs">
          Clear
        </Button>
      )}
    </div>

    <div className="relative mt-3">
      <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
      <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search company name or CIN" className="h-10 rounded-lg border-slate-200 pl-9 text-sm" />
    </div>

    <div className="mt-3 space-y-1.5">
      <ShowMoreContainer
        items={suggestions.length > 0 ? suggestions : browseCompanies}
        label="Companies"
        renderItems={(visibleItems) => (
          <div className="space-y-1.5">
            {visibleItems.map((company) => (
              <button
                key={`${title}-${company.id}`}
                type="button"
                onClick={() => onSelectCompany(company)}
                className="flex w-full items-start gap-2.5 rounded-lg border border-slate-100 px-3 py-2 text-left hover:border-[#81BC06] hover:bg-[#81BC06]/5"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#81BC06]/10 text-xs font-black text-[#81BC06]">
                  {company.name[0]}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-black uppercase tracking-wide text-slate-900">{company.name}</p>
                  <div className="mt-1 flex flex-wrap gap-x-2 gap-y-1 text-[10px] font-medium text-slate-500">
                    <span className="inline-flex items-center gap-1">
                      <Building2 className="h-2.5 w-2.5" />
                      {company.cin || "N/A"}
                    </span>
                    <span>{company.status}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      />
    </div>

    {selectedCompany && (
      <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50 p-3 text-xs">
        <button type="button" onClick={() => onOpenInsight(selectedCompany)} className="w-full text-left">
          <div className="flex items-center gap-2 text-slate-700">
            <MapPin className="h-3.5 w-3.5 text-[#81BC06]" />
            <span className="font-semibold">{selectedCompany.registeredAddress || "N/A"}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-500">
            <span>Type: {selectedCompany.type || "N/A"}</span>
            <span>Source: {selectedCompany.sourceSection || "N/A"}</span>
            <span>Industry: {selectedCompany.industry || "N/A"}</span>
          </div>
        </button>
        <button
          type="button"
          onClick={() => window.open(`/company/${selectedCompany.id}`, "_blank", "noopener,noreferrer")}
          className="mt-3 inline-flex items-center gap-2 text-xs font-bold text-[#81BC06] hover:underline"
        >
          Open full profile
          <ArrowUpRight className="h-4 w-4" />
        </button>
      </div>
    )}
  </div>
);

export default ComparePage;
