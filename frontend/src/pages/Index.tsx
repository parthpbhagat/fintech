import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
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
  Sparkles,
  UserRound,
  RefreshCw,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { fetchIBBIFeaturedCompanies, fetchIBBIStats, IbbiApiError, searchIBBICompanies, triggerGlobalRefresh } from "@/services/ibbiService";
import { StatusBadge } from "@/components/Navbar";
import { useAuth } from "@/contexts/AuthContext";
import type { Company } from "@/data/types";
import { ShowMoreContainer } from "@/components/ShowMoreContainer";
import AIChatAssistant from "@/components/AIChatAssistant";

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
type SearchModeId = (typeof searchModes)[number]["id"];

const normalizeSearchValue = (value: string | undefined) => value?.trim().toLowerCase() ?? "";

const filterCompaniesBySearchMode = (companies: Company[], mode: SearchModeId, query: string) => {
  const normalizedQuery = normalizeSearchValue(query);
  if (!normalizedQuery) return companies;

  return companies.filter((company) => {
    const companyName = normalizeSearchValue(company.name);
    const companyCin = normalizeSearchValue(company.cin);
    const applicantName = normalizeSearchValue(company.applicant_name);
    const ipName = normalizeSearchValue(company.ip_name);
    const applicants = company.applicants?.map((entry) => normalizeSearchValue(entry)) ?? [];
    const professionals = company.insolvencyProfessionals?.map((entry) => normalizeSearchValue(entry)) ?? [];

    if (mode === "applicant") {
      return applicantName.includes(normalizedQuery) || applicants.some((entry) => entry.includes(normalizedQuery));
    }

    if (mode === "ip") {
      return ipName.includes(normalizedQuery) || professionals.some((entry) => entry.includes(normalizedQuery));
    }

    return companyName.includes(normalizedQuery) || companyCin.includes(normalizedQuery);
  });
};

const filterOptions = {
  status: ["All", "Active", "Inactive", "Under CIRP", "Liquidation"],
  type: ["All", "Private", "Public", "LLP", "OPC"],
  source: ["All", "master", "master+ibbi", "ibbi", "claims"],
} as const;

const Index = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [query, setQuery] = useState("");
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [selectedSearchMode, setSelectedSearchMode] = useState<(typeof searchModes)[number]>(searchModes[0]);
  const [showSearchModeMenu, setShowSearchModeMenu] = useState(false);
  const [suggestions, setSuggestions] = useState<Company[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isSuggestionsLoading, setIsSuggestionsLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("All");
  const [typeFilter, setTypeFilter] = useState("All");
  const [sourceFilter, setSourceFilter] = useState("All");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { authUser, setIsAuthDialogOpen } = useAuth();
  const [authPrefill, setAuthPrefill] = useState<{
    mode?: "login" | "signup" | "forgot";
    email?: string;
    otpStep?: boolean;
    message?: string;
    error?: string;
  } | null>(null);
  const searchBoxRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

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

  const handleRefreshData = async () => {
    setIsRefreshing(true);
    try {
      await triggerGlobalRefresh();
      // Reload the page to fetch latest stats and companies
      window.location.reload();
    } catch (error) {
      console.error("Refresh failed", error);
    } finally {
      setIsRefreshing(false);
    }
  };

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
    const params = new URLSearchParams(location.search);
    const email = params.get("email")?.trim() || "";
    const provider = params.get("provider")?.trim() || "";
    const otpSent = params.get("otp_sent") === "1";
    const authError = params.get("auth_error")?.trim() || "";

    if (!email && !otpSent && !authError && !provider) return;

    if (otpSent && provider === "google" && email) {
      setAuthPrefill({
        mode: "login",
        email,
        otpStep: true,
        message: "Google login successful. Mobile par moklel OTP enter karo.",
      });
      setIsAuthDialogOpen(true);
    } else if (authError === "mobile_required" && email) {
      setAuthPrefill({
        mode: "login",
        email,
        error: "Aa Google account mate mobile number missing chhe. Pehla manual signup/login thi account setup karo.",
      });
      setIsAuthDialogOpen(true);
    } else if (authError) {
      const authErrorMessages: Record<string, string> = {
        google_cancelled: "Google login cancel thayu. Please fari try karo.",
        google_no_email: "Google account mathi email mali nathi.",
        google_failed: "Google login complete thai nathi. Please fari try karo.",
      };
      setAuthPrefill({
        mode: "login",
        error: authErrorMessages[authError] || "Authentication flow ma problem aavi.",
      });
      setIsAuthDialogOpen(true);
    }

    navigate({ pathname: location.pathname }, { replace: true });
  }, [location.pathname, location.search, navigate, setAuthPrefill, setIsAuthDialogOpen]);

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
        const filteredResults = filterCompaniesBySearchMode(results, selectedSearchMode.id, normalizedQuery);
        setSuggestions(filteredResults);
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
  }, [normalizedFilters, normalizedQuery, selectedSearchMode.id]);

  const runSearch = async (rawValue?: string, modeOverride?: SearchModeId) => {
    const nextQuery = (rawValue ?? query).trim();
    const activeMode = modeOverride ?? selectedSearchMode.id;
    if (modeOverride) {
      const overrideMode = searchModes.find((mode) => mode.id === modeOverride);
      if (overrideMode) {
        setSelectedSearchMode(overrideMode);
      }
    }
    if (nextQuery.length < 2) {
      setHasSearched(true);
      setCompanies([]);
      setSearchError("Please enter at least 2 characters to search.");
      return;
    }

    setQuery(nextQuery);
    setIsLoading(true);
    setHasSearched(true);
    setSearchError("");
    setShowSuggestions(false);

    try {
      const results = await searchIBBICompanies(nextQuery, 12, normalizedFilters);
      setCompanies(filterCompaniesBySearchMode(results, activeMode, nextQuery));
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

  const focusSearchInput = () => {
    searchInputRef.current?.focus();
    searchInputRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  const runLiveSearch = () => {
    if (query.trim().length >= 2) {
      void runSearch();
    }
  };

  const openSearchMode = (modeId: SearchModeId) => {
    const mode = searchModes.find((item) => item.id === modeId);
    if (mode) {
      setSelectedSearchMode(mode);
    }
    focusSearchInput();
  };


  const pageError =
    featuredCompaniesError instanceof Error
      ? featuredCompaniesError.message
      : statsError instanceof Error
        ? statsError.message
        : "";
  const registryWarning = stats?.ibbiStatus === "degraded" ? stats.ibbiError || "Live IBBI feed temporarily unavailable." : "";

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
    <div className="bg-white font-sans">

      <section className="relative py-16 md:py-24 flex flex-col items-center justify-center bg-[#F8FAFC] overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(circle_at_30%_20%,#81BC0615_0%,transparent_40%),radial-gradient(circle_at_70%_60%,#1f8bff10_0%,transparent_40%)]" />

        <div className="mb-8 text-center relative z-10 px-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-[#81BC06]/10 px-4 py-1.5 text-[10px] font-black uppercase tracking-[0.2em] text-[#81BC06] mb-6">
            <Sparkles className="h-3 w-3" />
            Empowering Modern Fintech Analysis
          </div>
          <h1 className="mt-2 text-4xl md:text-5xl font-black tracking-tight text-slate-900 leading-[1.1]">
            Intelligent Corporate <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#81BC06] to-[#A3D93F]">Insights & Analytics</span>
          </h1>
          <p className="mt-6 max-w-2xl text-base md:text-lg text-slate-500 font-medium">
            Live IBBI registry analysis and risk assessment tools for smarter business decisions.
          </p>
        </div>

        <div ref={searchBoxRef} className="w-full max-w-4xl relative">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              runSearch();
            }}
            className="flex flex-col md:flex-row items-stretch md:items-center shadow-lg rounded-lg border border-slate-200 bg-white"
          >
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowSearchModeMenu((value) => !value)}
                className="bg-[#F8F9FA] w-full md:w-[170px] px-5 py-3 border-b md:border-b-0 md:border-r border-slate-200 text-slate-500 flex items-center justify-between gap-2 font-bold text-xs uppercase"
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
                      className={`flex w-full items-center px-4 py-3 text-left text-sm font-semibold uppercase tracking-wide transition-colors ${selectedSearchMode.id === mode.id
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
                ref={searchInputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onFocus={() => {
                  if (normalizedQuery.length >= 2) {
                    setShowSuggestions(true);
                  }
                }}
                placeholder={selectedSearchMode.placeholder}
                className="border-none h-12 text-sm md:text-base focus-visible:ring-0 px-4 md:px-5 font-medium"
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
              className="bg-[#81BC06] text-white px-6 py-3 font-bold uppercase text-xs hover:bg-[#6ea105] transition-colors"
            >
              {isLoading ? "Searching..." : "Search"}
            </button>
            <button
              type="button"
              onClick={runLiveSearch}
              className="bg-[#2D333F] text-white px-5 py-3 font-bold uppercase text-[11px] flex items-center justify-center gap-1.5 min-w-max rounded-b-lg md:rounded-b-none md:rounded-r-lg"
            >
              <Search className="w-3.5 h-3.5" /> Live IBBI
            </button>
          </form>
        </div>

        <div className="mt-4 flex flex-wrap justify-center gap-2 max-w-5xl relative z-10">
          <span className="text-xs font-bold text-slate-800 uppercase mt-1 mr-2">Try recent:</span>
          {quickSearches.map((company) => (
            <Link
              key={company.id}
              to={`/company/${company.id}`}
              className="px-3 py-1 bg-white border border-slate-200 rounded-full text-[10px] text-blue-600 font-medium hover:underline hover:text-blue-800 hover:border-blue-300 cursor-pointer transition-colors shadow-sm"
            >
              {company.name}
            </Link>
          ))}
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-2 relative z-10">
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
            className="rounded-full border-slate-200 px-4 text-[11px] font-bold uppercase"
          >
            Compare Two Companies
          </Button>
          <Button
            onClick={handleRefreshData}
            disabled={isRefreshing}
            className="rounded-full bg-[#81BC06] text-white px-4 text-[11px] font-bold uppercase hover:bg-[#6ea105] shadow-md border-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-2 ${isRefreshing ? "animate-spin" : ""}`} />
            {isRefreshing ? "Refreshing..." : "Refresh Data"}
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

      <section className="bg-[#F8F9FA] py-6 border-b border-slate-100">
        <div className="container mx-auto px-4 grid grid-cols-2 md:grid-cols-4 gap-5">
          <ActionItem icon={<Building2 className="w-10 h-10 text-slate-500" />} label="Check Corporate Debtor" onClick={() => openSearchMode("company")} />
          <ActionItem icon={<Landmark className="w-10 h-10 text-slate-500" />} label="Track Applicant" onClick={() => openSearchMode("applicant")} />
          <ActionItem icon={<UserRound className="w-10 h-10 text-slate-500" />} label="Review IP Details" onClick={() => openSearchMode("ip")} />
          <ActionItem icon={<ShieldCheck className="w-10 h-10 text-slate-500" />} label="Quick Search" onClick={() => focusSearchInput()} />
        </div>
      </section>

      <section className="container mx-auto px-4 py-8">
        {registryWarning && !pageError && (
          <div className="max-w-5xl mx-auto mb-6 rounded-2xl border border-amber-200 bg-amber-50 px-6 py-4 text-amber-800">
            <p className="font-bold">Live IBBI feed temporarily degraded</p>
            <p className="text-sm mt-1">{registryWarning}</p>
          </div>
        )}

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
            <ShowMoreContainer
              items={companies}
              label="Matches"
              renderItems={(visibleItems) => (
                <div className="grid gap-3 lg:grid-cols-2">
                  {visibleItems.map((company) => (
                    <CompanyCard key={company.id} company={company} onClick={() => navigate(`/company/${company.id}`)} />
                  ))}
                </div>
              )}
            />
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
            <ShowMoreContainer
              items={filteredFeaturedCompanies}
              label="Records"
              renderItems={(visibleItems) => (
                <div className="grid gap-3 lg:grid-cols-2">
                  {visibleItems.map((company) => (
                    <CompanyCard key={company.id} company={company} onClick={() => navigate(`/company/${company.id}`)} />
                  ))}
                </div>
              )}
            />
          </div>
        )}
      </section>

      <footer className="bg-white pt-10 pb-3 border-t border-slate-100">
        <div className="container mx-auto px-6">
          <div className="flex flex-col md:flex-row justify-between gap-8">
            <div className="max-w-md text-slate-500 text-sm leading-relaxed">
              {/* Logo Section */}
              <p className="text-2xl font-black tracking-tight text-slate-900">
                fin<span className="text-[#81BC06]">tech</span>
              </p>

              {/* Address Section - Replace the text below with your actual address */}
              <div className="mt-4 text-slate-600 text-xs md:text-sm">
                <p className="font-bold text-slate-800">Our Address:</p>
                <p>Fintech Soluction Pvt Ltd, Office No 1815,</p>
                <p>Ambali Bopal Road, Ahemdabad, gujrat - 380058</p>
                <p className="mt-2">Email: fintechpvtltd@gmail.com </p>
              </div>

              <div className="flex gap-4 mt-4 text-[11px] font-bold text-slate-400">
                <span>Source: IBBI</span>
                <span>Live Search</span>
                <span>Registry Snapshot</span>
              </div>
            </div>

            <div className="text-right text-[11px] md:text-xs text-slate-500">
              <p className="font-bold text-slate-800 mb-1">Data Coverage</p>
              <p>Announcement type, dates, CIN, applicant, IP name and IP address</p>
              <p className="mt-2">
                Last synced: {stats?.lastSyncedAt ? new Date(stats.lastSyncedAt).toLocaleString() : "Pending"}
              </p>
            </div>
          </div>
        </div>

        <div className="mt-8 bg-[#81BC06]/10 text-slate-600 py-2.5 px-6 flex flex-col md:flex-row justify-between gap-2 text-[11px] font-medium">
          <p>Powered by the official IBBI public announcement export</p>
          <p className="font-bold text-slate-800">Search, inspect, and review insolvency timelines faster</p>
        </div>
      </footer>
      <AIChatAssistant />
    </div>
  );
};

export default Index;

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
  <label className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600">
    <span className="uppercase text-[9px] tracking-[0.16em] text-slate-400">{label}</span>
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

const ActionItem = ({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) => (
  <button onClick={onClick} className="flex flex-col items-center text-center group">
    <div className="mb-2 transition-transform group-hover:scale-110">{icon}</div>
    <p className="text-[11px] font-bold text-slate-600 uppercase tracking-tight">{label}</p>
  </button>
);

const CompanyCard = ({ company, onClick }: { company: Company; onClick: () => void }) => (
  <button
    onClick={onClick}
    className="bg-white p-3 rounded-xl border border-slate-100 shadow-sm flex items-start gap-3 w-full text-left hover:border-[#81BC06] hover:shadow-md transition-all group"
  >
    <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-sm font-bold text-slate-400 group-hover:bg-[#81BC06] group-hover:text-white transition-colors">
      {company.name[0]}
    </div>
    <div className="flex-1">
      <div className="flex flex-wrap items-center gap-2 mb-0.5">
        <h3 className="font-bold text-[13px] text-slate-800 leading-tight">{company.name}</h3>
        <StatusBadge status={company.status} />
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-500 font-medium">
        <span className="flex items-center gap-1">
          <Calendar className="w-3 h-3" />
          Latest filing: {company.announcementDate || "N/A"}
        </span>
        <span>Applicant: {company.applicant_name || "N/A"}</span>
        <span>IP: {company.ip_name || "N/A"}</span>
      </div>
      <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">{company.announcementType || company.category}</p>
    </div>
    <ArrowRight className="mt-2 w-4 h-4 text-slate-300 group-hover:text-[#81BC06] transition-colors" />
  </button>
);
