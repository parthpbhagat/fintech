import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
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
  User,
} from "lucide-react";
import { API_BASE_URL, fetchIBBICompanyDetails } from "@/services/ibbiService";
import DataInsightSheet, { type InsightContent } from "@/components/DataInsightSheet";
import { StatusBadge } from "@/components/Navbar";
import type { AnnouncementRecord, Charge, CompanyAddress, CompanyDataSource, CompanyDocument, Director, NewsItem } from "@/data/types";

const currencyFormatter = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

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
  if (company.directors && company.directors.length > 0) tabs.push("Directors");
  if (company.charges && company.charges.length > 0) tabs.push("Charges");
  if (company.documents && company.documents.length > 0) tabs.push("Documents");
  if (company.news && company.news.length > 0) tabs.push("News");
  if (hasIBBIData) tabs.push("IBBI");
  tabs.push("Source");

  return (
<div className="bg-[#F4F7F9] min-h-screen">
      <div className="container mx-auto px-4 py-4 md:py-6">
        <div className="space-y-4">
          <div className="bg-white p-4 md:p-5 rounded-xl shadow-sm border border-slate-100 flex flex-col xl:flex-row items-start xl:items-center justify-between gap-4">
            <div className="flex items-start gap-5">
              <div className="w-14 h-14 rounded-xl bg-[#81BC06]/10 flex items-center justify-center text-xl font-black text-[#81BC06]">
                {company.name[0]}
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-3 mb-2">
                  <h1 className="text-xl md:text-2xl font-black text-slate-900">{company.name}</h1>
                  <StatusBadge status={company.status} />
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-500 font-medium text-xs">
                  {company.cin && company.cin !== "N/A" && (
                    <span className="flex items-center gap-2">
                      <Building2 className="w-4 h-4" />
                      CIN/LLPIN: {company.cin}
                    </span>
                  )}
                  {company.incorporationDate && company.incorporationDate !== "N/A" && (
                    <span className="flex items-center gap-2">
                      <Calendar className="w-4 h-4" />
                      Incorporated: {company.incorporationDate}
                    </span>
                  )}
                  {company.rocCode && company.rocCode !== "N/A" && (
                    <span className="flex items-center gap-2">
                      <Landmark className="w-4 h-4" />
                      ROC: {company.rocCode}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-xs md:text-sm text-slate-500 max-w-4xl line-clamp-3">{company.overview}</p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-2 min-w-full xl:min-w-[360px] xl:max-w-[460px]">
              {company.authCap && company.authCap > 0 && (
                <MetricCard
                  label="Authorised Capital"
                  value={`Rs ${currencyFormatter.format(company.authCap)}`}
                  onClick={() =>
                    openFieldInsight(
                      setActiveInsight,
                      "Authorised Capital",
                      `Rs ${currencyFormatter.format(company.authCap)}`,
                      "Authorised capital scraped from public company profile sources.",
                    )
                  }
                />
              )}
              {company.puc && company.puc > 0 && (
                <MetricCard
                  label="Paid Up Capital"
                  value={`Rs ${currencyFormatter.format(company.puc)}`}
                  onClick={() =>
                    openFieldInsight(
                      setActiveInsight,
                      "Paid Up Capital",
                      `Rs ${currencyFormatter.format(company.puc)}`,
                      "Paid up capital scraped from public company profile sources.",
                    )
                  }
                />
              )}
              {company.lastAGMDate && company.lastAGMDate !== "N/A" && (
                <MetricCard
                  label="Last AGM"
                  value={company.lastAGMDate}
                  onClick={() => openFieldInsight(setActiveInsight, "Last AGM", company.lastAGMDate || "N/A", "Latest AGM date currently available for this company.")}
                />
              )}
              {company.lastBSDate && company.lastBSDate !== "N/A" && (
                <MetricCard
                  label="Last B/S"
                  value={company.lastBSDate}
                  onClick={() => openFieldInsight(setActiveInsight, "Last Balance Sheet", company.lastBSDate || "N/A", "Latest balance sheet date currently available for this company.")}
                />
              )}
            </div>

            <div className="flex gap-2 flex-wrap">
              {company.profileUrl && (
                <a
                  href={company.profileUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="px-4 py-2 bg-[#81BC06] text-white rounded-lg font-bold text-xs uppercase shadow-lg shadow-[#81BC06]/30 inline-flex items-center gap-2"
                >
                  Open Source
                  <ArrowUpRight className="w-4 h-4" />
                </a>
              )}
              <button onClick={() => navigate("/")} className="p-2 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200">
                <Search className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
            <div className="flex border-b border-slate-100 overflow-x-auto bg-slate-50/50">
              {tabs.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-3 text-[11px] font-bold uppercase tracking-wide transition-all min-w-max ${
                    activeTab === tab
                      ? "bg-white text-[#81BC06] border-b-2 border-[#81BC06]"
                      : "text-slate-400 hover:text-slate-600"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="p-4 md:p-5">
              {activeTab === "Overview" && (
                <div className="space-y-5">
                  <div className="grid lg:grid-cols-3 gap-5">
                    <div className="lg:col-span-2">
                      <SectionTitle title="Company Master" />
                      <div className="grid md:grid-cols-2 gap-2">
                        <InfoRow label="Registration Number" value={company.registrationNumber} onClick={() => openFieldInsight(setActiveInsight, "Registration Number", company.registrationNumber || "N/A", "Registry registration number for this company.")} />
                        <InfoRow label="Company Class" value={company.type} onClick={() => openFieldInsight(setActiveInsight, "Company Class", company.type || "N/A", "Legal structure of this company.")} />
                        <InfoRow label="Company Category" value={company.category} onClick={() => openFieldInsight(setActiveInsight, "Company Category", company.category || "N/A", "Entity category or insolvency classification.")} />
                        <InfoRow label="Company Subcategory" value={company.companySubcategory} onClick={() => openFieldInsight(setActiveInsight, "Company Subcategory", company.companySubcategory || "N/A", "Subcategory from public company profile sources.")} />
                        <InfoRow label="Company Status" value={company.status} onClick={() => openFieldInsight(setActiveInsight, "Company Status", company.status || "N/A", "Latest available company status.")} />
                        <InfoRow label="Listing Status" value={company.listingStatus} onClick={() => openFieldInsight(setActiveInsight, "Listing Status", company.listingStatus || "N/A", "Indicates whether the company is listed or unlisted.")} />
                        <InfoRow label="Email" value={company.email} onClick={() => openFieldInsight(setActiveInsight, "Email", company.email || "N/A", "Publicly visible email captured from available sources.")} />
                        <InfoRow label="Website" value={company.website} onClick={() => openFieldInsight(setActiveInsight, "Website", company.website || "N/A", "Public website captured from available sources.")} />
                        <InfoRow label="Industry" value={company.industry} onClick={() => openFieldInsight(setActiveInsight, "Industry", company.industry || "N/A", "Business activity or industry mapped from public sources.")} />
                        <InfoRow label="NIC Code" value={company.nicCode} onClick={() => openFieldInsight(setActiveInsight, "NIC Code", company.nicCode || "N/A", "NIC code when it is available from public company data.")} />
                        <InfoRow label="Filing Status" value={company.filingStatus} onClick={() => openFieldInsight(setActiveInsight, "Filing Status", company.filingStatus || "N/A", "Recent filing status seen in public company data.")} />
                        <InfoRow label="Active Compliance" value={company.activeCompliance} onClick={() => openFieldInsight(setActiveInsight, "Active Compliance", company.activeCompliance || "N/A", "Compliance flag from public company data.")} />
                      </div>
                    </div>
                    <div>
                      <SectionTitle title="Quick Snapshot" />
                      <div className="space-y-2">
                        <QuickRow icon={<Calendar className="w-4 h-4" />} label="Last Updated" value={company.lastUpdatedOn || "N/A"} onClick={() => openFieldInsight(setActiveInsight, "Last Updated", company.lastUpdatedOn || "N/A", "Latest profile refresh date from public sources.")} />
                        <QuickRow icon={<MapPin className="w-4 h-4" />} label="Registered Address" value={company.registeredAddress || "N/A"} onClick={() => openFieldInsight(setActiveInsight, "Registered Address", company.registeredAddress || "N/A", "Registered address currently mapped for this company.")} />
                        <QuickRow icon={<User className="w-4 h-4" />} label="Directors" value={`${company.directors.length}`} onClick={() => openFieldInsight(setActiveInsight, "Directors", `${company.directors.length}`, "Total directors or designated partners captured for this company.", company.directors.slice(0, 6).map((director) => ({ label: director.designation || "Director", value: director.name || "N/A" })))} />
                        <QuickRow icon={<FileText className="w-4 h-4" />} label="Charges" value={`${company.charges.length}`} onClick={() => openFieldInsight(setActiveInsight, "Charges", `${company.charges.length}`, "Total charge records captured for this company.", company.charges.slice(0, 6).map((charge) => ({ label: charge.status || "Charge", value: charge.bankName || "N/A" })))} />
                      </div>
                    </div>
                  </div>

                  {addresses.length > 0 && (
                    <div>
                      <SectionTitle title="Address Preview" />
                      <AddressTable
                        addresses={addresses}
                        onInspect={(address) =>
                          setActiveInsight({
                            title: `${address.type} - Address`,
                            description: "Structured address details captured for this company.",
                            facts: [
                              { label: "Full Address", value: address.raw || "N/A" },
                              { label: "District", value: address.district || "N/A" },
                              { label: "City", value: address.city || "N/A" },
                              { label: "State", value: address.state || "N/A" },
                              { label: "Postal Code", value: address.postalCode || "N/A" },
                            ],
                          })
                        }
                      />
                    </div>
                  )}

                  {(company.mapLocation || (company.registeredAddress && company.registeredAddress !== "N/A")) && (
                    <div>
                      <SectionTitle title="Location Map" />
                      <MapSection
                        companyName={company.name}
                        mapLocation={company.mapLocation}
                        fallbackAddress={company.registeredAddress || addresses[0]?.raw || "N/A"}
                      />
                    </div>
                  )}

                  {company.news && company.news.length > 0 && (
                    <div>
                      <SectionTitle title="Latest News & Updates" />
                      <NewsList
                        news={company.news}
                        onInspect={(item) =>
                          setActiveInsight({
                            title: item.title,
                            subtitle: item.source,
                            description: item.summary,
                            facts: [
                              { label: "Date", value: item.date },
                              { label: "Source", value: item.source },
                              { label: "Link", value: item.url || "N/A" },
                            ],
                          })
                        }
                      />
                    </div>
                  )}

                  {company.documents && company.documents.length > 0 && (
                    <div>
                      <SectionTitle title="Documents & Downloads" />
                      <DocumentsList
                        documents={company.documents}
                        onInspect={(document) =>
                          setActiveInsight({
                            title: document.fileName,
                            subtitle: document.category,
                            description: "Document or source link available for this company.",
                            facts: [
                              { label: "Source", value: document.source || "N/A" },
                              { label: "Date", value: document.dateOfFiling || "N/A" },
                              { label: "Open URL", value: document.url || "N/A" },
                              { label: "Download URL", value: document.downloadUrl || "N/A" },
                            ],
                          })
                        }
                      />
                    </div>
                  )}
                </div>
              )}

              {activeTab === "Addresses" && (
                <AddressTable
                  addresses={addresses}
                  onInspect={(address) =>
                    setActiveInsight({
                      title: `${address.type} - Address`,
                      description: "Structured address details captured for this company.",
                      facts: [
                        { label: "Full Address", value: address.raw || "N/A" },
                        { label: "District", value: address.district || "N/A" },
                        { label: "City", value: address.city || "N/A" },
                        { label: "State", value: address.state || "N/A" },
                        { label: "Postal Code", value: address.postalCode || "N/A" },
                      ],
                    })
                  }
                />
              )}

              {activeTab === "Map" && (
                <div>
                  <SectionTitle title="Company Location" />
                  <MapSection
                    companyName={company.name}
                    mapLocation={company.mapLocation}
                    fallbackAddress={company.registeredAddress || addresses[0]?.raw || "N/A"}
                  />
                </div>
              )}

              {activeTab === "Directors" && (
                <div>
                  <SectionTitle title="Directors" />
                  <DirectorsTable
                    directors={company.directors}
                    onInspect={(director) =>
                      setActiveInsight({
                        title: director.name,
                        subtitle: director.designation,
                        description: "Director or designated partner details from public company sources.",
                        facts: [
                          { label: "DIN", value: director.din || "N/A" },
                          { label: "Appointment", value: director.appointmentDate || "N/A" },
                          { label: "Status", value: director.status || "N/A" },
                          { label: "Directorships", value: director.totalDirectorships || "N/A" },
                        ],
                      })
                    }
                  />
                </div>
              )}

              {activeTab === "Charges" && (
                <div>
                  <SectionTitle title="Charges" />
                  <ChargesTable
                    charges={company.charges}
                    onInspect={(charge) =>
                      setActiveInsight({
                        title: charge.bankName || "Charge Detail",
                        subtitle: charge.status,
                        description: "Charge information captured from public company sources.",
                        facts: [
                          { label: "Charge ID", value: charge.chargeId || "N/A" },
                          { label: "Amount", value: charge.amount ? `Rs ${currencyFormatter.format(charge.amount)}` : "N/A" },
                          { label: "Creation Date", value: charge.creationDate || "N/A" },
                          { label: "Modified Date", value: charge.modificationDate || "N/A" },
                          { label: "Assets", value: charge.assetsSecured || "N/A" },
                        ],
                      })
                    }
                  />
                </div>
              )}

              {activeTab === "Documents" && (
                <div>
                  <SectionTitle title="Documents & Downloads" />
                  <DocumentsList
                    documents={company.documents || []}
                    onInspect={(document) =>
                      setActiveInsight({
                        title: document.fileName,
                        subtitle: document.category,
                        description: "Document or source link available for this company.",
                        facts: [
                          { label: "Source", value: document.source || "N/A" },
                          { label: "Date", value: document.dateOfFiling || "N/A" },
                          { label: "Open URL", value: document.url || "N/A" },
                          { label: "Download URL", value: document.downloadUrl || "N/A" },
                        ],
                      })
                    }
                  />
                </div>
              )}

              {activeTab === "News" && (
                <div>
                  <SectionTitle title="Latest News & Updates" />
                  <NewsList
                    news={company.news || []}
                    onInspect={(item) =>
                      setActiveInsight({
                        title: item.title,
                        subtitle: item.source,
                        description: item.summary,
                        facts: [
                          { label: "Date", value: item.date },
                          { label: "Source", value: item.source },
                          { label: "Link", value: item.url || "N/A" },
                        ],
                      })
                    }
                  />
                </div>
              )}

              {activeTab === "IBBI" && (
                <div className="space-y-8">
                  <div className="bg-[#FFF4E5] p-6 rounded-xl border border-orange-200 flex items-center gap-4">
                    <ShieldCheck className="w-10 h-10 text-orange-500" />
                    <div>
                      <h3 className="font-bold text-orange-900 uppercase text-sm">IBBI enrichment</h3>
                      <p className="text-orange-700 text-xs">
                        This block shows insolvency and claims details only when they are available from IBBI.
                      </p>
                    </div>
                  </div>
                  {(company.announcementType || company.announcementDate || company.applicant_name || company.ip_name) && (
                    <div className="grid md:grid-cols-2 gap-6">
                      <DataBox label="Announcement type" value={company.announcementType || "N/A"} icon={<FileText className="w-5 h-5" />} />
                      <DataBox label="Latest announcement" value={company.announcementDate || "N/A"} icon={<Calendar className="w-5 h-5" />} />
                      <DataBox label="Applicant" value={company.applicant_name || "N/A"} icon={<Landmark className="w-5 h-5" />} />
                      <DataBox label="Insolvency professional" value={company.ip_name || "N/A"} icon={<User className="w-5 h-5" />} />
                    </div>
                  )}
                  <div className="space-y-4">
                    {(company.announcementHistory || []).length > 0 ? (
                      (company.announcementHistory || []).map((announcement) => (
                        <AnnouncementCard
                          key={`${announcement.id}-${announcement.announcementDate}`}
                          announcement={announcement}
                          onInspect={() =>
                            setActiveInsight({
                              title: announcement.announcementType,
                              subtitle: announcement.announcementDate,
                              description: announcement.remarks,
                              facts: [
                                { label: "Applicant", value: announcement.applicantName },
                                { label: "IP", value: announcement.insolvencyProfessional },
                                { label: "Deadline", value: announcement.lastDateOfSubmission },
                                { label: "CIN", value: announcement.cin },
                              ],
                            })
                          }
                        />
                      ))
                    ) : (
                      <EmptyState text="No IBBI announcement history is linked to this company right now." />
                    )}
                  </div>
                </div>
              )}

              {activeTab === "Source" && (
                <div className="grid lg:grid-cols-[1.2fr_0.8fr] gap-5">
                  <div className="space-y-4">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <h3 className="text-xs font-black uppercase tracking-[0.2em] text-slate-800">Data Provenance</h3>
                      <p className="mt-2 text-xs leading-6 text-slate-600">
                        Multi-source pipeline: IBBI announcements + IBBI claims + company master + assisted links for MCA/GST/Udyam.
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white p-4">
                      <h3 className="text-xs font-black uppercase tracking-[0.2em] text-slate-800">Source Section</h3>
                      <p className="mt-2 text-xs leading-6 text-slate-600">{company.sourceSection || "N/A"}</p>
                      {company.profileUrl && (
                        <a
                          href={company.profileUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-3 inline-flex items-center gap-2 text-xs font-bold text-[#81BC06] hover:underline"
                        >
                          Launch public company profile
                          <ArrowUpRight className="w-4 h-4" />
                        </a>
                      )}
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white p-4">
                      <h3 className="text-xs font-black uppercase tracking-[0.2em] text-slate-800">Connected Sources</h3>
                      {(company.dataSources || []).length === 0 ? (
                        <p className="mt-2 text-xs text-slate-500">No source metadata available.</p>
                      ) : (
                        <div className="mt-3 space-y-2">
                          {(company.dataSources || []).map((source) => (
                            <SourceCard key={source.id} source={source} />
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <h3 className="text-xs font-black uppercase tracking-[0.2em] text-slate-800">Latest Summary</h3>
                    <p className="mt-3 text-xs leading-6 text-slate-600">{company.overview}</p>
                    {(company.sourceUrls && Object.keys(company.sourceUrls).length > 0) && (
                      <div className="mt-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">Source Links</p>
                        <div className="mt-2 space-y-1.5">
                          {Object.entries(company.sourceUrls).map(([key, url]) => (
                            <a
                              key={key}
                              href={url}
                              target="_blank"
                              rel="noreferrer"
                              className="block rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-700 hover:border-[#81BC06] hover:text-[#81BC06]"
                            >
                              {key}: {url}
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                    {latestAnnouncement && (
                      <div className="mt-4 space-y-2">
                        <SourceMeta label="Type" value={latestAnnouncement.announcementType} />
                        <SourceMeta label="Date" value={latestAnnouncement.announcementDate} />
                        <SourceMeta label="Deadline" value={latestAnnouncement.lastDateOfSubmission} />
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <footer className="mt-8 py-6 bg-white border-t border-slate-100 flex flex-col items-center gap-2">
        <p className="text-xl font-black tracking-tight text-slate-900">
          fin<span className="text-[#81BC06]">tech</span>
        </p>
        <p className="text-slate-400 text-xs text-center px-4">
          Company detail page with master-data search, public-profile scraping, and IBBI enrichment.
        </p>
      </footer>

      <DataInsightSheet open={!!activeInsight} onOpenChange={(open) => !open && setActiveInsight(null)} content={activeInsight} />
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

const DirectorsTable = ({ directors, onInspect }: { directors: Director[]; onInspect?: (director: Director) => void }) => {
  if (!directors.length) {
    return <EmptyState text="No director data available." />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-100">
      <table className="w-full text-xs">
        <thead className="bg-slate-50">
          <tr className="text-left text-[10px] uppercase tracking-[0.15em] text-slate-400">
            <th className="px-3 py-2">DIN</th>
            <th className="px-3 py-2">Name</th>
            <th className="px-3 py-2">Designation</th>
            <th className="px-3 py-2">Appointment</th>
            <th className="px-3 py-2">Directorships</th>
            <th className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {directors.map((director, index) => (
            <tr key={`${director.din}-${index}`} className="border-t border-slate-100 cursor-pointer hover:bg-slate-50" onClick={() => onInspect?.(director)}>
              <td className="px-3 py-2 text-slate-700 font-bold">{director.din}</td>
              <td className="px-3 py-2 text-slate-700">{director.name}</td>
              <td className="px-3 py-2 text-slate-600">{director.designation}</td>
              <td className="px-3 py-2 text-slate-600">{director.appointmentDate && director.appointmentDate !== "N/A" ? director.appointmentDate : "-"}</td>
              <td className="px-3 py-2 text-slate-600">{director.totalDirectorships && String(director.totalDirectorships) !== "N/A" ? director.totalDirectorships : "-"}</td>
              <td className="px-3 py-2 text-slate-600">{director.status ? director.status : "-"}</td>
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
              <td className="px-3 py-2 text-slate-600">{charge.amount && charge.amount > 0 ? `${charge.amount}` : "-"}</td>
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
