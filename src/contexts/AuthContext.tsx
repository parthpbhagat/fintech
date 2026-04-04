import React, { createContext, useContext, useEffect, useState } from "react";
import { fetchMe, type AuthUser } from "@/services/authService";

interface AuthContextType {
  authToken: string;
  authUser: AuthUser | null;
  isAuthDialogOpen: boolean;
  setIsAuthDialogOpen: (open: boolean) => void;
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [authToken, setAuthToken] = useState<string>(() => localStorage.getItem("fintech_auth_token") || "");
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => {
    const raw = localStorage.getItem("fintech_auth_user");
    if (!raw) return null;
    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      return null;
    }
  });
  const [isAuthDialogOpen, setIsAuthDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!authToken) {
      setAuthUser(null);
      return;
    }

    const verifyToken = async () => {
      setIsLoading(true);
      try {
        const user = await fetchMe(authToken);
        setAuthUser(user);
        localStorage.setItem("fintech_auth_user", JSON.stringify(user));
      } catch (error) {
        console.error("Auth verification failed:", error);
        logout();
      } finally {
        setIsLoading(false);
      }
    };

    void verifyToken();
  }, [authToken]);

  const login = (token: string, user: AuthUser) => {
    setAuthToken(token);
    setAuthUser(user);
    localStorage.setItem("fintech_auth_token", token);
    localStorage.setItem("fintech_auth_user", JSON.stringify(user));
  };

  const logout = () => {
    setAuthToken("");
    setAuthUser(null);
    localStorage.removeItem("fintech_auth_token");
    localStorage.removeItem("fintech_auth_user");
  };

  return (
    <AuthContext.Provider
      value={{
        authToken,
        authUser,
        isAuthDialogOpen,
        setIsAuthDialogOpen,
        login,
        logout,
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
