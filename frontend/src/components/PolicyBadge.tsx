interface PolicyBadgeProps {
  toolName: string;
  status: "approved" | "confirmation" | "denied";
  reason?: string;
}

export function PolicyBadge({ toolName, status, reason }: PolicyBadgeProps) {
  const icons = {
    approved: "✓",
    confirmation: "⚠",
    denied: "✕",
  };

  const labels = {
    approved: "approved",
    confirmation: "requires confirmation",
    denied: "denied",
  };

  return (
    <div className={`policy-badge policy-${status}`} title={reason}>
      <span className="policy-icon">{icons[status]}</span>
      <span className="policy-tool">{toolName}</span>
      <span className="policy-label">{labels[status]}</span>
    </div>
  );
}
