export interface Company {
  id: string;
  name: string;
  cin: string;
  pan: string;
  incorporationDate: string;
  status: "Active" | "Inactive" | "Under CIRP" | "Liquidation" | "Dissolved";
  type: "Public" | "Private" | "OPC" | "LLP";
  category: string;
  origin: string;
  registeredAddress: string;
  businessAddress: string;
  phone: string;
  email: string;
  website: string;
  listingStatus: "Listed" | "Unlisted";
  lastAGMDate: string;
  lastBSDate: string;
  gstin: string;
  lei: string;
  epfo: string;
  iec: string;
  authCap: number;
  puc: number;
  soc: number;
  revenue: FinancialMetric[];
  pat: FinancialMetric[];
  netWorth: FinancialMetric[];
  promoterHolding: FinancialMetric[];
  receivable: string;
  payable: string;
  overview: string;
  charges: Charge[];
  financials: FinancialYear[];
  ownership: OwnershipData[];
  compliance: ComplianceRecord[];
  documents: CompanyDocument[];
  directors: Director[];
  news: NewsItem[];
  trendData: number[];
  ip_name?: string;
  applicant_name?: string;
  commencement_date?: string;
  last_date_claims?: string;
  announcementType?: string;
  announcementDate?: string;
  announcementDateIso?: string;
  lastDateOfSubmission?: string;
  lastDateOfSubmissionIso?: string;
  insolvencyProfessionalAddress?: string;
  remarks?: string;
  registryUrl?: string;
  announcementCount?: number;
  applicants?: string[];
  insolvencyProfessionals?: string[];
  announcementHistory?: AnnouncementRecord[];
  sourceSection?: string;
  profileUrl?: string;
  lastUpdatedOn?: string;
  rocCode?: string;
  registrationNumber?: string;
  companySubcategory?: string;
  nicCode?: string;
  industry?: string;
  filingStatus?: string;
  activeCompliance?: string;
  statusUnderCirp?: string;
  addresses?: CompanyAddress[];
  mapLocation?: CompanyMapLocation;
  snapshotSyncedAt?: string;
  profileCachedAt?: string;
  profileCacheTtlSeconds?: number;
}

export interface AnnouncementRecord {
  id: string;
  announcementType: string;
  announcementDate: string;
  announcementDateIso?: string;
  lastDateOfSubmission: string;
  lastDateOfSubmissionIso?: string;
  debtorName: string;
  cin: string;
  applicantName: string;
  insolvencyProfessional: string;
  insolvencyProfessionalAddress: string;
  remarks: string;
  status: Company["status"];
  registryUrl: string;
}

export interface FinancialMetric {
  year: string;
  value: number;
}

export interface Charge {
  chargeId: string;
  bankName: string;
  amount: number;
  status: "Open" | "Closed" | "Partially Satisfied";
  creationDate: string;
  modificationDate: string;
  assetsSecured?: string;
  outstandingYears?: string;
}

export interface FinancialYear {
  year: string;
  totalRevenue: number;
  otherIncome: number;
  totalExpenses: number;
  profit: number;
  foreignExchange: number;
}

export interface OwnershipData {
  category: string;
  years: Record<string, { shares: number; percentage: number }>;
  subcategories?: OwnershipData[];
}

export interface ComplianceRecord {
  gstin: string;
  state: string;
  regDate: string;
  status: "Active" | "Inactive" | "Provisional" | "Cancelled" | "Cancelled suo-moto";
  constitution: string;
  taxType: string;
  cancelDate: string;
}

export interface CompanyDocument {
  formId: string;
  fileName: string;
  year: number;
  dateOfFiling: string;
  category: string;
  source?: string;
  url?: string;
  downloadUrl?: string;
}

export interface Director {
  din: string;
  name: string;
  designation: string;
  appointmentDate: string;
  status: "Active" | "Resigned" | "Disqualified";
  totalDirectorships?: string;
  disqualified164?: string;
  dinDeactivated?: string;
  profileUrl?: string;
  contactEmail?: string;
  contactPhone?: string;
  contactWebsite?: string;
  contactAddress?: string;
  contactSource?: string;
  contactNote?: string;
  nationality?: string;
  occupation?: string;
}

export interface CompanyAddress {
  type: string;
  line1: string;
  line2: string;
  line3: string;
  line4: string;
  locality: string;
  district: string;
  city: string;
  state: string;
  postalCode: string;
  country: string;
  raw: string;
  latitude?: number;
  longitude?: number;
}

export interface CompanyMapLocation {
  latitude?: number;
  longitude?: number;
  formattedAddress: string;
  embedUrl: string;
  mapUrl: string;
}

export interface NewsItem {
  id: string;
  title: string;
  source: string;
  date: string;
  summary: string;
  url: string;
  companyId: string;
}

export interface DashboardStats {
  totalAnnouncements: number;
  totalCompanies: number;
  masterCompanies?: number;
  masterFilesLoaded?: number;
  totalProfessionals: number;
  ibbiStatus?: string;
  ibbiError?: string;
  lastSyncedAt: string;
}

export interface CompanyFilters {
  q?: string;
  status?: string;
  type?: string;
  source?: string;
  limit?: number;
  fresh?: number | boolean;
}
