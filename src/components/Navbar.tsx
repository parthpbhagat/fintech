import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import AuthDialog from "@/components/AuthDialog";

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
  <button onClick={onClick} className="flex items-center gap-1 hover:text-[#81BC06] transition-colors uppercase font-bold text-[10px] tracking-widest">
    {label}
  </button>
);

const Navbar = () => {
  const navigate = useNavigate();
  const { authUser, logout, isAuthDialogOpen, setIsAuthDialogOpen, login } = useAuth();

  return (
    <nav className="sticky top-0 z-40 border-b border-slate-100 bg-white/95 py-2 px-4 md:px-6 flex items-center justify-between backdrop-blur">
      <div className="flex items-center gap-8">
        <button
          onClick={() => navigate("/")}
          className="text-[26px] md:text-[30px] font-black tracking-tighter text-slate-900 leading-none"
        >
          fin<span className="text-[#81BC06]">tech</span>
        </button>
        
        <div className="hidden md:flex items-center gap-6">
          <NavItem label="Announcements" onClick={() => navigate("/news")} />
          <NavItem label="Mirror" onClick={() => window.open("https://ibbi.gov.in/en/public-announcement", "_blank", "noopener,noreferrer")} />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-3 mr-4">
          <Button
            variant="ghost"
            onClick={() => navigate("/compare")}
            className="h-8 rounded-md px-3 text-[10px] font-bold uppercase tracking-widest text-slate-600 hover:text-[#81BC06]"
          >
            Compare
          </Button>
        </div>

        {authUser ? (
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex flex-col items-end">
              <span className="text-[10px] font-black text-slate-900 uppercase">{authUser.name || authUser.email.split('@')[0]}</span>
              <span className="text-[8px] font-bold text-[#81BC06] uppercase tracking-widest">Verified User</span>
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
            className="h-8 rounded-md bg-[#81BC06] hover:bg-[#6ea105] px-5 text-[10px] font-black uppercase tracking-widest text-white shadow-lg shadow-[#81BC06]/20 transition-all active:scale-95"
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
