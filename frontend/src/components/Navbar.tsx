import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import AuthDialog from "@/components/AuthDialog";
import { useState, useEffect } from "react";
import { triggerFullSync, fetchSyncStatus } from "@/services/ibbiService";
import { Loader2, RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";

const STATUS_CLASS_MAP: Record<string, string> = {
  Active: "status-active",
  "Under CIRP": "status-open",
  Liquidation: "status-cancelled",
  Dissolved: "status-closed",
  Inactive: "status-provisional",
};

export const StatusBadge = ({ status }: { status: string }) => {
  const className = STATUS_CLASS_MAP[status] || "status-provisional";
  return <span className={`${className} ml-auto shrink-0 uppercase text-[9px] font-black`}>{status}</span>;
};

const NavItem = ({ label, onClick }: { label: string; onClick: () => void }) => (
  <button onClick={onClick} className="flex items-center gap-1 hover:text-primary transition-colors uppercase font-bold text-[10px] tracking-widest">
    {label}
  </button>
);

const Navbar = () => {
  const navigate = useNavigate();
  const { authUser, logout, isAuthDialogOpen, setIsAuthDialogOpen, login } = useAuth();
  const [syncJob, setSyncJob] = useState<any>(null);

  useEffect(() => {
    const checkStatus = async () => {
      const status = await fetchSyncStatus();
      setSyncJob(status?.activeJob);
    };

    checkStatus();
    const interval = setInterval(() => {
      if (syncJob?.status === 'running' || !syncJob) {
        checkStatus();
      }
    }, 5000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [syncJob?.status]);

  const handleFullSync = async () => {
    const job = await triggerFullSync();
    if (job) setSyncJob(job);
  };

  return (
    <nav className="sticky top-0 z-40 border-b border-slate-100 bg-white/95 py-2 px-4 md:px-6 flex items-center justify-between backdrop-blur">
      <div className="flex items-center gap-8">
        <button
          onClick={() => navigate("/")}
          className="text-[26px] md:text-[30px] font-black tracking-tighter text-slate-900 leading-none"
        >
          fin<span className="text-primary">tech</span>
        </button>
        
        <div className="hidden md:flex items-center gap-6">
          <NavItem label="IBBI Mirror" onClick={() => window.open("https://ibbi.gov.in/en/public-announcement", "_blank", "noopener,noreferrer")} />
          
          {/* ── Sync Indicator ── */}
          <div className="flex items-center gap-2 pl-4 border-l border-slate-200">
            {syncJob?.status === 'running' ? (
              <div className="flex items-center gap-2 px-3 py-1 bg-primary/10 rounded-full border border-primary/20 animate-pulse">
                <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
                <span className="text-[10px] font-black text-primary uppercase tracking-tighter">
                  Syncing {syncJob.progress}/{syncJob.total}
                </span>
              </div>
            ) : (
              <button 
                onClick={handleFullSync}
                className="group flex items-center gap-2 hover:text-primary transition-all px-2 py-1 rounded"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${syncJob?.status === 'completed' ? 'text-primary' : 'text-slate-400'} group-hover:rotate-180 transition-transform duration-500`} />
                <span className="text-[10px] font-bold text-slate-500 group-hover:text-primary uppercase tracking-tight">
                  {syncJob?.status === 'completed' ? 'Refreshed' : 'Run Sync'}
                </span>
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-3 mr-4">
          <Button
            variant="ghost"
            onClick={() => navigate("/compare")}
            className="h-8 rounded-md px-3 text-[10px] font-bold uppercase tracking-widest text-slate-600 hover:text-primary"
          >
            Compare
          </Button>
        </div>

        {authUser ? (
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex flex-col items-end">
              <span className="text-[10px] font-black text-slate-900 uppercase">{authUser.name || authUser.email.split('@')[0]}</span>
              <span className="text-[8px] font-bold text-primary uppercase tracking-widest">Verified User</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={logout}
              className="h-8 rounded-md border-slate-200 px-4 text-[10px] font-black uppercase tracking-widest text-slate-800 hover:bg-slate-50 transition-all"
            >
              Logout
            </Button>
          </div>
        ) : (
          <Button
            variant="default"
            size="sm"
            onClick={() => setIsAuthDialogOpen(true)}
            className="h-8 rounded-md bg-primary hover:bg-primary/90 px-5 text-[10px] font-black uppercase tracking-widest text-white shadow-lg shadow-primary/20 transition-all active:scale-95"
          >
            Sign In
          </Button>
        )}
      </div>

      <AuthDialog
        open={isAuthDialogOpen}
        onOpenChange={setIsAuthDialogOpen}
        onAuthenticated={login}
      />
    </nav>
  );
};

export default Navbar;
