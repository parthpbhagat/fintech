import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { API_BASE_URL } from "@/services/ibbiService";
import {
  confirmPasswordReset,
  loginWithPassword,
  requestPasswordReset,
  resendOtp,
  signupWithPassword,
  verifyOtp,
  type AuthOtpPurpose,
} from "@/services/authService";

type AuthMode = "login" | "signup" | "forgot";

export type AuthUser = {
  id: number;
  email: string;
  name: string;
  provider: string;
  phone_number?: string;
  avatar_url?: string;
  is_verified: boolean;
};

type AuthPrefill = {
  mode?: AuthMode;
  email?: string;
  otpStep?: boolean;
  message?: string;
  error?: string;
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAuthenticated: (token: string, user: AuthUser) => void;
  prefill?: AuthPrefill | null;
};

const AuthDialog = ({ open, onOpenChange, onAuthenticated, prefill }: Props) => {
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [name, setName] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [otpStep, setOtpStep] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const lastPrefillKeyRef = useRef("");

  const dialogTitle = useMemo(() => {
    if (otpStep) return "Verify OTP";
    if (mode === "signup") return "Create Account";
    if (mode === "forgot") return "Forgot Password";
    return "Login";
  }, [mode, otpStep]);

  const resetLocalState = () => {
    setName("");
    setEmail("");
    setPassword("");
    setPhoneNumber("");
    setOtp("");
    setNewPassword("");
    setOtpStep(false);
    setMessage("");
    setError("");
  };

  const setModeAndClearState = (nextMode: AuthMode) => {
    setMode(nextMode);
    setName("");
    setPassword("");
    setPhoneNumber("");
    setOtp("");
    setNewPassword("");
    setOtpStep(false);
    setMessage("");
    setError("");
  };

  useEffect(() => {
    if (!open) {
      lastPrefillKeyRef.current = "";
      return;
    }
    if (!open || !prefill) return;

    const prefillKey = JSON.stringify(prefill);
    if (lastPrefillKeyRef.current === prefillKey) return;
    lastPrefillKeyRef.current = prefillKey;

    setMode(prefill.mode ?? "login");
    setEmail(prefill.email ?? "");
    setName("");
    setPassword("");
    setPhoneNumber("");
    setOtp("");
    setNewPassword("");
    setOtpStep(Boolean(prefill.otpStep));
    setMessage(prefill.message ?? "");
    setError(prefill.error ?? "");
  }, [open, prefill]);

  const runPrimaryAction = async () => {
    setError("");
    setMessage("");
    setIsSubmitting(true);
    try {
      if (!otpStep) {
        if (!email.trim()) {
          throw new Error("Email is required.");
        }
        if (mode !== "forgot" && !password.trim()) {
          throw new Error("Email and password are required.");
        }
        if (mode === "signup" && password.trim().length < 8) {
          throw new Error("Password must be at least 8 characters.");
        }
        if (mode === "signup" && !phoneNumber.trim()) {
          throw new Error("Mobile number is required for signup.");
        }
        if (mode === "signup") {
          const result = await signupWithPassword(email.trim(), password.trim(), name.trim(), phoneNumber.trim());
          setMessage(result.message || "OTP sent to your mobile.");
        } else if (mode === "login") {
          const result = await loginWithPassword(email.trim(), password.trim());
          setMessage(result.message || "OTP sent to your mobile.");
        } else {
          const result = await requestPasswordReset(email.trim());
          setMessage(result.message || "Password reset OTP sent to your mobile.");
        }
        setOtpStep(true);
        return;
      }

      if (!otp.trim() || otp.trim().length < 6) {
        throw new Error("Please enter 6 digit OTP.");
      }
      if (mode === "forgot") {
        if (!newPassword.trim() || newPassword.trim().length < 8) {
          throw new Error("New password must be at least 8 characters.");
        }
        const result = await confirmPasswordReset(email.trim(), otp.trim(), newPassword.trim());
        setMessage(result.message || "Password reset successful.");
        setOtpStep(false);
        setMode("login");
        setPassword("");
        setOtp("");
        setNewPassword("");
      } else {
        const result = await verifyOtp(email.trim(), otp.trim(), mode);
        onAuthenticated(result.token, result.user);
        resetLocalState();
        onOpenChange(false);
      }
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : "Authentication failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResend = async () => {
    if (!email.trim()) {
      setError("Enter email first.");
      return;
    }
    setError("");
    setIsSubmitting(true);
    try {
      const result = await resendOtp(email.trim(), mode as AuthOtpPurpose);
      setMessage(result.message || "OTP resent.");
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : "OTP resend failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) resetLocalState();
        onOpenChange(nextOpen);
      }}
    >
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
          <DialogDescription>
            {otpStep
              ? mode === "forgot"
                ? "Mobile par aavelo OTP ane navo password enter karo."
                : "Mobile par aavelo OTP enter karo."
              : mode === "login"
                ? "Login kari ne account access karo."
                : mode === "signup"
                  ? "Navo account banavi ne OTP thi verify karo."
                  : "Registered email thi password reset karo."}
          </DialogDescription>
        </DialogHeader>

        {!otpStep && (
          <div className="space-y-3">
            <div className="flex gap-2">
              <Button
                type="button"
                variant={mode === "login" ? "default" : "outline"}
                className="flex-1"
                onClick={() => {
                  setModeAndClearState("login");
                }}
              >
                Login
              </Button>
              <Button
                type="button"
                variant={mode === "signup" ? "default" : "outline"}
                className="flex-1"
                onClick={() => {
                  setModeAndClearState("signup");
                }}
              >
                Signup
              </Button>
            </div>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={() => {
                window.location.href = `${API_BASE_URL}/auth/google`;
              }}
            >
              Continue With Google
            </Button>
            {mode === "signup" && (
              <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Full name" />
            )}
            <Input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" type="email" />
            {mode === "signup" && (
              <Input value={phoneNumber} onChange={(event) => setPhoneNumber(event.target.value)} placeholder="Mobile (+91XXXXXXXXXX)" />
            )}
            {mode !== "forgot" && (
              <Input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" type="password" />
            )}
            {mode === "login" && (
              <Button
                type="button"
                variant="ghost"
                className="justify-start px-0 text-xs"
                onClick={() => {
                  setModeAndClearState("forgot");
                }}
              >
                Forgot password?
              </Button>
            )}
          </div>
        )}

        {otpStep && (
          <div className="space-y-3">
            <Input value={email} readOnly className="bg-slate-50" />
            <Input value={otp} onChange={(event) => setOtp(event.target.value)} placeholder="Enter 6 digit OTP" maxLength={6} />
            {mode === "forgot" && (
              <Input
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="New password"
                type="password"
              />
            )}
            <div className="flex items-center justify-between">
              <Button
                type="button"
                variant="ghost"
                className="px-0 text-xs"
                onClick={handleResend}
                disabled={isSubmitting || mode === "forgot"}
              >
                Resend OTP
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="px-0 text-xs"
                onClick={() => {
                  setOtpStep(false);
                  setOtp("");
                  setError("");
                }}
              >
                Back
              </Button>
            </div>
          </div>
        )}

        {message && <p className="text-xs text-emerald-600">{message}</p>}
        {error && <p className="text-xs text-red-600">{error}</p>}

        <Button type="button" onClick={runPrimaryAction} disabled={isSubmitting} className="w-full">
          {isSubmitting
            ? "Please wait..."
            : otpStep
              ? mode === "forgot"
                ? "Reset Password"
                : "Verify OTP"
              : mode === "login"
                ? "Login"
                : mode === "signup"
                  ? "Create Account"
                  : "Send OTP"}
        </Button>
      </DialogContent>
    </Dialog>
  );
};

export default AuthDialog;
