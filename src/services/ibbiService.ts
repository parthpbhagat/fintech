import type { Company, CompanyFilters, DashboardStats, NewsItem } from "@/data/types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8005";

export class IbbiApiError extends Error {
  status?: number;
  isNetworkError: boolean;

  constructor(message: string, options?: { status?: number; isNetworkError?: boolean }) {
    super(message);
    this.name = "IbbiApiError";
    this.status = options?.status;
    this.isNetworkError = options?.isNetworkError ?? false;
  }
}

const fetchJson = async <T>(path: string, init?: RequestInit): Promise<T> => {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    throw new IbbiApiError(
      `IBBI backend sathe connection thai nathi. Pehla backend start karo: python backend/pipeline.py`,
      { isNetworkError: true },
    );
  }

  if (!response.ok) {
    throw new IbbiApiError(
      `IBBI API request failed with ${response.status} on ${path}. Jo old backend run thato hoy to ene stop kari ne fari thi chalaavo: python backend/pipeline.py`,
      { status: response.status },
    );
  }

  return response.json() as Promise<T>;
};

const ensureArray = <T>(value: unknown, path: string): T[] => {
  if (!Array.isArray(value)) {
    throw new IbbiApiError(
      `Backend response ${path} mate valid list format ma nathi. Aa mostly old backend run thato hoy tyare aave chhe. Restart karo: python backend/pipeline.py`,
    );
  }
  return value as T[];
};

const buildQueryString = (params: Record<string, string | number | undefined>) => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined) return;
    const stringValue = String(value).trim();
    if (!stringValue) return;
    searchParams.set(key, stringValue);
  });
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
};

export const fetchIBBICompanyDetails = async (
  idOrCin: string,
  options?: { fresh?: boolean },
): Promise<Company | null> => {
  try {
    return await fetchJson<Company>(
      `/company/${encodeURIComponent(idOrCin)}${buildQueryString({ fresh: options?.fresh ? 1 : undefined })}`,
      options?.fresh ? { cache: "no-store" } : undefined,
    );
  } catch (error) {
    console.error("Failed to load company profile from IBBI API.", error);
    return null;
  }
};

export const searchIBBICompanies = async (
  query: string,
  limit = 12,
  filters?: Omit<CompanyFilters, "q" | "limit">,
): Promise<Company[]> => {
  const q = query.trim();
  if (!q) return [];

  const data = await fetchJson<unknown>(
    `/search${buildQueryString({
      q,
      limit,
      status: filters?.status,
      type: filters?.type,
      source: filters?.source,
      fresh: filters?.fresh,
    })}`,
  );
  return ensureArray<Company>(data, "/search");
};

export const fetchCompanyDirectory = async (filters?: CompanyFilters): Promise<Company[]> => {
  const data = await fetchJson<unknown>(
    `/companies${buildQueryString({
      q: filters?.q,
      status: filters?.status,
      type: filters?.type,
      source: filters?.source,
      limit: filters?.limit ?? 40,
      fresh: filters?.fresh,
    })}`,
  );
  return ensureArray<Company>(data, "/companies");
};

export const fetchIBBIFeaturedCompanies = async (limit = 10): Promise<Company[]> => {
  try {
    const data = await fetchJson<unknown>(`/featured?limit=${limit}`);
    return ensureArray<Company>(data, "/featured");
  } catch (error) {
    if (error instanceof IbbiApiError && error.status === 404) {
      return [];
    }
    throw error;
  }
};

export const fetchIBBIStats = async (): Promise<DashboardStats> => {
  try {
    return await fetchJson<DashboardStats>("/stats");
  } catch (error) {
    if (error instanceof IbbiApiError && error.status === 404) {
      return {
        totalAnnouncements: 0,
        totalCompanies: 0,
        totalProfessionals: 0,
        lastSyncedAt: "",
      };
    }
    throw error;
  }
};

export const fetchIBBIRecentAnnouncements = async (limit = 18): Promise<NewsItem[]> => {
  const data = await fetchJson<unknown>(`/recent-announcements?limit=${limit}`);
  return ensureArray<NewsItem>(data, "/recent-announcements");
};
