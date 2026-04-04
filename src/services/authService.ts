import { API_BASE_URL } from "@/services/ibbiService";

export type AuthOtpPurpose = "login" | "signup";

const postJson = async <T>(path: string, payload: Record<string, unknown>): Promise<T> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error("Auth backend sathe connection thai nathi. Pehla `python backend/pipeline.py` chalavo.");
  }

  let data: unknown = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    const detail = typeof data === "object" && data && "detail" in data ? String((data as { detail?: unknown }).detail ?? "") : "";
    throw new Error(detail || `Auth request failed (${response.status})`);
  }

  return data as T;
};

export type AuthUser = {
  id: number;
  email: string;
  name: string;
  provider: string;
  phone_number?: string;
  avatar_url?: string;
  is_verified: boolean;
};

export type VerifyOtpResponse = {
  token: string;
  user: AuthUser;
  message?: string;
};

export const signupWithPassword = async (email: string, password: string, name: string, phoneNumber: string) => {
  return postJson<{ status: string; email: string; message: string }>("/auth/signup", { email, password, name, phone_number: phoneNumber });
};

export const loginWithPassword = async (email: string, password: string) => {
  return postJson<{ status: string; email: string; message: string }>("/auth/login", { email, password });
};

export const verifyOtp = async (email: string, otp: string, purpose: AuthOtpPurpose) => {
  return postJson<VerifyOtpResponse>("/auth/verify-otp", { email, otp, purpose });
};

export const resendOtp = async (email: string, purpose: AuthOtpPurpose) => {
  return postJson<{ status: string; message: string }>("/auth/resend-otp", { email, purpose });
};

export const requestPasswordReset = async (email: string) => {
  return postJson<{ status: string; message: string }>("/auth/forgot-password/request", { email });
};

export const confirmPasswordReset = async (email: string, otp: string, newPassword: string) => {
  return postJson<{ status: string; message: string }>("/auth/forgot-password/confirm", {
    email,
    otp,
    new_password: newPassword,
  });
};

export const updatePhoneNumber = async (email: string, phoneNumber: string, token: string) => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/update-phone`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        email,
        phone_number: phoneNumber,
      }),
    });
  } catch {
    throw new Error("Auth backend sathe connection thai nathi. Pehla `python backend/pipeline.py` chalavo.");
  }

  let data: unknown = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    const detail = typeof data === "object" && data && "detail" in data ? String((data as { detail?: unknown }).detail ?? "") : "";
    throw new Error(detail || `Auth request failed (${response.status})`);
  }

  return data as { status: string; message: string };
};

export const fetchMe = async (token: string) => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error("Auth backend sathe connection thai nathi. Pehla `python backend/pipeline.py` chalavo.");
  }
  if (!response.ok) {
    throw new Error("Session expired. Please login again.");
  }
  return response.json() as Promise<{
    id: number;
    email: string;
    name: string;
    provider: string;
    phone_number?: string;
    avatar_url?: string;
    is_verified: boolean;
  }>;
};
