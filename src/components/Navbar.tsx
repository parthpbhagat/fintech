const STATUS_CLASS_MAP: Record<string, string> = {
  Active: "status-active",
  "Under CIRP": "status-open",
  Liquidation: "status-cancelled",
  Dissolved: "status-closed",
  Inactive: "status-provisional",
};

export const StatusBadge = ({ status }: { status: string }) => {
  const className = STATUS_CLASS_MAP[status] || "status-provisional";
  return <span className={`${className} ml-auto shrink-0`}>{status}</span>;
};

const Navbar = () => null;

export default Navbar;
