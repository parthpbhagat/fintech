import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  Calendar,
  ChevronDown,
  FileSpreadsheet,
  Landmark,
  SlidersHorizontal,
  Search,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  fetchIBBIFeaturedCompanies,
  fetchIBBIStats,
  IbbiApiError,
  searchIBBICompanies,
} from "@/services/ibbiService";
import { StatusBadge } from "@/components/Navbar";
import type { Company } from "@/data/types";

const numberFormatter = new Intl.NumberFormat("en-IN");
const searchModes = [
  {
    id: "company",
    label: "Company / CIN",
    shortLabel: "Company",
    placeholder: "Search for a company",
  },
  {
    id: "applicant",
    label: "Applicant Name",
    shortLabel: "Applicant",
    placeholder: "Search by applicant name",
  },
  {
    id: "ip",
    label: "IP / Liquidator",
    shortLabel: "IP / Liquidator",
    placeholder: "Search by insolvency professional",
  },
] as const;

const filterOptions = {
  status: ["All", "Active", "Inactive", "Under CIRP", "Liquidation"],
  type: ["All", "Private", "Public", "LLP", "OPC"],
  source: ["All", "master", "master+ibbi", "ibbi", "claims"],
} as const;

const Index = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [selectedSearchMode, setSelectedSearchMode] = useState(searchModes[0]);
  const [showSearchModeMenu, setShowSearchModeMenu] = useState(false);
  const [suggestions, setSuggestions] = useState<Company[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isSuggestionsLoading, setIsSuggestionsLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("All");
  const [typeFilter, setTypeFilter] = useState("All");
  const [sourceFilter, setSourceFilter] = useState("All");
  const searchBoxRef = useRef<HTMLDivElement>(null);

  const {
    data: featuredCompanies = [],
    error: featuredCompaniesError,
  } = useQuery({
    queryKey: ["ibbi-featured-companies"],
    queryFn: () => fetchIBBIFeaturedCompanies(10),
    retry: false,
  });

  const {
    data: stats,
    error: statsError,
  } = useQuery({
    queryKey: ["ibbi-dashboard-stats"],
    queryFn: fetchIBBIStats,
    retry: false,
  });

  const quickSearches = featuredCompanies.slice(0, 10);
  const normalizedQuery = query.trim();
  const normalizedFilters = useMemo(
    () => ({
      status: statusFilter === "All" ? undefined : statusFilter,
      type: typeFilter === "All" ? undefined : typeFilter,
      source: sourceFilter === "All" ? undefined : sourceFilter,
    }),
    [sourceFilter, statusFilter, typeFilter],
  );

  const matchesLocalFilter = (company: Company) => {
    if (normalizedFilters.status && company.status !== normalizedFilters.status) return false;
    if (normalizedFilters.type && company.type !== normalizedFilters.type) return false;
    if (normalizedFilters.source && company.sourceSection !== normalizedFilters.source) return false;
    return true;
  };

  const filteredFeaturedCompanies = featuredCompanies.filter(matchesLocalFilter);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchBoxRef.current && !searchBoxRef.current.contains(event.target as Node)) {
        setShowSearchModeMenu(false);
        setShowSuggestions(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (normalizedQuery.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      setIsSuggestionsLoading(false);
      return;
    }

    let isActive = true;
    const timeoutId = window.setTimeout(async () => {
      setIsSuggestionsLoading(true);

      try {
        const results = await searchIBBICompanies(normalizedQuery, 8, normalizedFilters);
        if (!isActive) return;
        setSuggestions(results);
        setShowSuggestions(true);
      } catch (error) {
        if (!isActive) return;
        setSuggestions([]);
        setShowSuggestions(false);
        console.error(error);
      } finally {
        if (isActive) {
          setIsSuggestionsLoading(false);
        }
      }
    }, 220);

    return () => {
      isActive = false;
      window.clearTimeout(timeoutId);
    };
  }, [normalizedFilters, normalizedQuery]);

  const runSearch = async (rawValue?: string) => {
    const nextQuery = (rawValue ?? query).trim();
    if (nextQuery.length < 2) return;

    setQuery(nextQuery);
    setIsLoading(true);
    setHasSearched(true);
    setSearchError("");
    setShowSuggestions(false);

    try {
      const results = await searchIBBICompanies(nextQuery, 12, normalizedFilters);
      setCompanies(results);
    } catch (error) {
      setCompanies([]);
      if (error instanceof IbbiApiError) {
        setSearchError(error.message);
      } else {
        setSearchError("Company search ma unexpected error aavyo.");
      }
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const selectSuggestion = (company: Company) => {
    setQuery(company.name);
    setSuggestions([]);
    setShowSuggestions(false);
    setShowSearchModeMenu(false);
    navigate(`/company/${company.id}`);
  };

  const pageError =
    featuredCompaniesError instanceof Error
      ? featuredCompaniesError.message
      : statsError instanceof Error
        ? statsError.message
        : "";

  const statsCards = [
    {
      icon: <FileSpreadsheet className="w-5 h-5 opacity-80" />,
      label: "Public Announcements",
      value: stats ? `${numberFormatter.format(stats.totalAnnouncements)}+` : "Live",
    },
    {
      icon: <Building2 className="w-5 h-5 opacity-80" />,
      label: "Corporate Debtors",
      value: stats ? `${numberFormatter.format(stats.totalCompanies)}+` : "IBBI",
    },
    {
      icon: <UserRound className="w-5 h-5 opacity-80" />,
      label: "IPs On Record",
      value: stats ? `${numberFormatter.format(stats.totalProfessionals)}+` : "Direct",
    },
  ];

  return (
    <div className="min-h-screen bg-white font-sans">
      <nav className="border-b border-slate-100 py-3 px-6 flex items-center justify-between text-[13px] font-medium text-slate-600">
        <div className="flex items-center gap-8">
          <button
            onClick={() => navigate("/")}
            className="text-[32px] font-black tracking-tight text-slate-800 leading-none"
          >
            fin<span className="text-[#81BC06]">tech</span>
          </button>
          <div className="hidden md:flex items-center gap-6 uppercase tracking-wider">
            <NavItem label="Public Announcements" />
            <NavItem label="Corporate Debtors" />
            <NavItem label="Insolvency Professionals" />
            <NavItem label="Source: IBBI" />
          </div>
        </div>
          <div className="hidden md:flex items-center gap-4">
            <span className="text-xs font-bold uppercase text-slate-400">Live registry mirror</span>
            <Button
              variant="outline"
              onClick={() => navigate("/compare")}
              className="rounded-md border-slate-200 px-5 text-sm font-bold uppercase text-slate-700"
            >
              Compare
            </Button>
            <Button className="bg-[#81BC06] hover:bg-[#6ea105] text-white rounded-md px-5 text-sm font-bold uppercase">
              Search Now
            </Button>
        </div>
      </nav>

      <section className="py-20 flex flex-col items-center justify-center bg-[linear-gradient(180deg,#f7f9fd_0%,#ffffff_68%)] px-4">
        <div className="mb-10 text-center">
          <p className="text-sm font-bold uppercase tracking-[0.35em] text-[#81BC06]">Fintech Data Hub</p>
          <h1 className="mt-3 text-5xl md:text-6xl font-black tracking-tight text-slate-900">
            Search insolvency records
          </h1>
          <p className="mt-4 max-w-2xl text-base text-slate-500">
            Finanvo-style experience, but powered fully by the live IBBI public announcement registry.
          </p>
        </div>

        <div ref={searchBoxRef} className="w-full max-w-4xl relative">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              runSearch();
            }}
            className="flex flex-col md:flex-row items-stretch md:items-center shadow-xl rounded-lg border border-slate-200 bg-white"
          >
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowSearchModeMenu((value) => !value)}
                className="bg-[#F8F9FA] w-full md:w-[170px] px-6 py-4 border-b md:border-b-0 md:border-r border-slate-200 text-slate-500 flex items-center justify-between gap-2 font-bold text-sm uppercase"
              >
                {selectedSearchMode.shortLabel}
                <ChevronDown className={`w-4 h-4 transition-transform ${showSearchModeMenu ? "rotate-180" : ""}`} />
              </button>

              {showSearchModeMenu && (
                <div className="absolute left-0 top-full z-30 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl">
                  {searchModes.map((mode) => (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => {
                        setSelectedSearchMode(mode);
                        setShowSearchModeMenu(false);
                      }}
                      className={`flex w-full items-center px-4 py-3 text-left text-sm font-semibold uppercase tracking-wide transition-colors ${
                        selectedSearchMode.id === mode.id
                          ? "bg-[#1f8bff] text-white"
                          : "text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      {mode.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="relative flex-1">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onFocus={() => {
                  if (normalizedQuery.length >= 2) {
                    setShowSuggestions(true);
                  }
                }}
                placeholder={selectedSearchMode.placeholder}
                className="border-none h-14 text-base md:text-lg focus-visible:ring-0 px-6 font-medium"
              />

              {showSuggestions && normalizedQuery.length >= 2 && (
                <div className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl">
                  <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-[11px] font-bold uppercase tracking-[0.22em] text-slate-400">
                    Related Companies
                  </div>

                  {isSuggestionsLoading && (
                    <div className="px-4 py-4 text-sm text-slate-500">Searching live suggestions...</div>
                  )}

                  {!isSuggestionsLoading && suggestions.length === 0 && (
                    <div className="px-4 py-4 text-sm text-slate-500">No related companies found.</div>
                  )}

                  {!isSuggestionsLoading &&
                    suggestions.map((company) => (
                      <button
                        key={`${company.id}-suggestion`}
                        type="button"
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => selectSuggestion(company)}
                        className="flex w-full items-start gap-3 border-b border-slate-100 px-4 py-3 text-left last:border-b-0 hover:bg-[#1f8bff] hover:text-white group"
                      >
                        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-black text-slate-500 group-hover:bg-white/20 group-hover:text-white">
                          {company.name[0]}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-black uppercase tracking-wide">{company.name}</p>
                          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] font-medium text-slate-500 group-hover:text-white/90">
                            <span>CIN: {company.cin || "N/A"}</span>
                            <span>Status: {company.status}</span>
                          </div>
                        </div>
                      </button>
                    ))}
                </div>
              )}
            </div>

            <button
              type="submit"
              className="bg-[#81BC06] text-white px-8 py-4 font-bold uppercase text-sm hover:bg-[#6ea105] transition-colors"
            >
              {isLoading ? "Searching..." : "Search"}
            </button>
            <button
              type="button"
              onClick={() => runSearch()}
              className="bg-[#2D333F] text-white px-6 py-4 font-bold uppercase text-xs flex items-center justify-center gap-1.5 min-w-max rounded-b-lg md:rounded-b-none md:rounded-r-lg"
            >
              <Search className="w-3.5 h-3.5" /> Live IBBI
            </button>
          </form>
        </div>

        <div className="mt-6 flex flex-wrap justify-center gap-2 max-w-5xl">
          <span className="text-sm font-bold text-slate-800 uppercase mt-1 mr-2">Try recent:</span>
          {quickSearches.map((company) => (
            <button
              key={company.id}
              onClick={() => runSearch(company.name)}
              className="px-3 py-1 bg-white border border-slate-200 rounded-full text-[11px] text-slate-500 font-medium hover:border-[#81BC06] transition-colors"
            >
              {company.name}
            </button>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">
            <SlidersHorizontal className="w-3.5 h-3.5 text-[#81BC06]" />
            Filters
          </div>
          <FilterPill
            label="Status"
            value={statusFilter}
            options={filterOptions.status}
            onChange={setStatusFilter}
          />
          <FilterPill
            label="Type"
            value={typeFilter}
            options={filterOptions.type}
            onChange={setTypeFilter}
          />
          <FilterPill
            label="Source"
            value={sourceFilter}
            options={filterOptions.source}
            onChange={setSourceFilter}
          />
          <Button
            variant="outline"
            onClick={() => navigate("/compare")}
            className="rounded-full border-slate-200 px-5 text-xs font-bold uppercase"
          >
            Compare Two Companies
          </Button>
        </div>
      </section>

      <div className="bg-[#81BC06] py-3 text-white">
        <div className="container mx-auto flex flex-wrap justify-center gap-12 md:gap-24 text-[15px] font-medium uppercase tracking-wide">
          {statsCards.map((item) => (
            <div key={item.label} className="flex items-center gap-3">
              {item.icon}
              <span>
                {item.value} {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      <section className="bg-[#F8F9FA] py-12 border-b border-slate-100">
        <div className="container mx-auto px-4 grid grid-cols-2 md:grid-cols-4 gap-8">
          <ActionItem icon={<Building2 className="w-10 h-10 text-slate-500" />} label="Check Corporate Debtor" />
          <ActionItem icon={<Landmark className="w-10 h-10 text-slate-500" />} label="Track Applicant" />
          <ActionItem icon={<UserRound className="w-10 h-10 text-slate-500" />} label="Review IP Details" />
          <ActionItem icon={<ShieldCheck className="w-10 h-10 text-slate-500" />} label="Follow Insolvency Timeline" />
        </div>
      </section>

      <section className="container mx-auto px-4 py-12">
        {pageError && (
          <div className="max-w-5xl mx-auto mb-6 rounded-2xl border border-red-200 bg-red-50 px-6 py-4 text-red-700">
            <p className="font-bold">Backend connection issue</p>
            <p className="text-sm mt-1">{pageError}</p>
          </div>
        )}

        {isLoading && (
          <div className="flex flex-col items-center justify-center space-y-4">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[#81BC06]"></div>
            <p className="text-slate-500 italic">Searching live on the IBBI registry...</p>
          </div>
        )}

        {!isLoading && searchError && (
          <div className="max-w-3xl mx-auto rounded-2xl border border-red-200 bg-red-50 px-8 py-10 text-center">
            <h2 className="text-2xl font-black text-red-800">Search error aavyo chhe</h2>
            <p className="mt-3 text-red-700">{searchError}</p>
          </div>
        )}

        {!isLoading && !searchError && companies.length > 0 && (
          <div className="max-w-5xl mx-auto">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
              <h2 className="text-xl font-bold text-slate-800 border-l-4 border-[#81BC06] pl-4">Search Results</h2>
              <p className="text-sm text-slate-500">
                {companies.length} live match{companies.length === 1 ? "" : "es"} from current filters
              </p>
            </div>
            <div className="grid gap-4">
              {companies.map((company) => (
                <CompanyCard key={company.id} company={company} onClick={() => navigate(`/company/${company.id}`)} />
              ))}
            </div>
          </div>
        )}

        {!isLoading && !searchError && hasSearched && companies.length === 0 && (
          <div className="max-w-3xl mx-auto rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-8 py-16 text-center">
            <h2 className="text-2xl font-black text-slate-800">No live matches found</h2>
            <p className="mt-3 text-slate-500">
              Try a longer company name, exact CIN, applicant name, or insolvency professional from the IBBI listing.
            </p>
          </div>
        )}

        {!hasSearched && !isLoading && !pageError && filteredFeaturedCompanies.length > 0 && (
          <div className="max-w-5xl mx-auto">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
              <h2 className="text-xl font-bold text-slate-800 border-l-4 border-[#81BC06] pl-4">Latest Registry Activity</h2>
              <p className="text-sm text-slate-500">Fresh companies from the current filtered dataset</p>
            </div>
            <div className="grid gap-4">
              {filteredFeaturedCompanies.slice(0, 6).map((company) => (
                <CompanyCard key={company.id} company={company} onClick={() => navigate(`/company/${company.id}`)} />
              ))}
            </div>
          </div>
        )}
      </section>

      <footer className="bg-white pt-16 pb-3 border-t border-slate-100">
        <div className="container mx-auto px-6">
          <div className="flex flex-col md:flex-row justify-between gap-12">
            <div className="max-w-md text-slate-500 text-sm leading-relaxed">
              <p className="text-2xl font-black tracking-tight text-slate-900">
                fin<span className="text-[#81BC06]">tech</span>
              </p>
              <p className="font-bold mb-1 mt-5">Explore live IBBI insolvency announcements</p>
              <p className="mb-6">
                This dashboard mirrors corporate debtor activity from the official IBBI public announcement export.
              </p>
              <div className="flex gap-4 text-xs font-bold text-slate-400">
                <span>Source: IBBI</span>
                <span>Live Search</span>
                <span>Registry Snapshot</span>
              </div>
            </div>

            <div className="text-right text-xs text-slate-500">
              <p className="font-bold text-slate-800 mb-1">Data Coverage</p>
              <p>Announcement type, dates, CIN, applicant, IP name and IP address</p>
              <p className="mt-2">Last synced: {stats?.lastSyncedAt ? new Date(stats.lastSyncedAt).toLocaleString() : "Pending"}</p>
            </div>
          </div>
        </div>
        <div className="mt-12 bg-[#81BC06]/10 text-slate-600 py-3 px-6 flex flex-col md:flex-row justify-between gap-3 text-xs font-medium">
          <p>Powered by the official IBBI public announcement export</p>
          <p className="font-bold text-slate-800">Search, inspect, and review insolvency timelines faster</p>
        </div>
      </footer>
    </div>
  );
};

const NavItem = ({ label }: { label: string }) => (
  <button className="flex items-center gap-1 hover:text-[#81BC06] transition-colors uppercase font-bold">
    {label}
  </button>
);

const FilterPill = ({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
}) => (
  <label className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600">
    <span className="uppercase text-[10px] tracking-[0.18em] text-slate-400">{label}</span>
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="bg-transparent font-bold text-slate-700 outline-none"
    >
      {options.map((option) => (
        <option key={`${label}-${option}`} value={option}>
          {option}
        </option>
      ))}
    </select>
  </label>
);

const ActionItem = ({ icon, label }: { icon: React.ReactNode; label: string }) => (
  <button className="flex flex-col items-center text-center group">
    <div className="mb-4 transition-transform group-hover:scale-110">{icon}</div>
    <p className="text-[13px] font-bold text-slate-600 uppercase tracking-tight">{label}</p>
  </button>
);

const CompanyCard = ({ company, onClick }: { company: Company; onClick: () => void }) => (
  <button
    onClick={onClick}
    className="bg-white p-5 rounded-xl border border-slate-100 shadow-sm flex items-center gap-5 w-full text-left hover:border-[#81BC06] hover:shadow-md transition-all group"
  >
    <div className="w-14 h-14 rounded-full bg-slate-50 flex items-center justify-center text-xl font-bold text-slate-400 group-hover:bg-[#81BC06] group-hover:text-white transition-colors">
      {company.name[0]}
    </div>
    <div className="flex-1">
      <div className="flex flex-wrap items-center gap-3 mb-1">
        <h3 className="font-bold text-slate-800">{company.name}</h3>
        <StatusBadge status={company.status} />
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500 font-medium">
        <span className="flex items-center gap-1">
          <Calendar className="w-3.5 h-3.5" />
          Latest filing: {company.announcementDate || "N/A"}
        </span>
        <span>Applicant: {company.applicant_name || "N/A"}</span>
        <span>IP: {company.ip_name || "N/A"}</span>
      </div>
      <p className="mt-2 text-xs uppercase tracking-wide text-slate-400">{company.announcementType || company.category}</p>
    </div>
    <ArrowRight className="w-5 h-5 text-slate-300 group-hover:text-[#81BC06] transition-colors" />
  </button>
);

export default Index;
