// UPGRADE_PLAN.md H.2 primitive: shared token-based table shell. A native <table>
// has its own accessibility semantics already (no Radix primitive needed) -- this
// standardizes the styling so every data table in the app looks and behaves the same.
import { ReactNode, TableHTMLAttributes, ThHTMLAttributes, TdHTMLAttributes, HTMLAttributes } from "react";

export function Table({ children, ...rest }: TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs" {...rest}>
        {children}
      </table>
    </div>
  );
}

export function TableHead({ children }: { children: ReactNode }) {
  return <thead className="sticky top-0 border-b border-border bg-surface-2 text-2xs uppercase tracking-wider text-muted">{children}</thead>;
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-border/60">{children}</tbody>;
}

export function Th({ children, ...rest }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className="px-5 py-3 font-medium" {...rest}>
      {children}
    </th>
  );
}

export function Td({ children, ...rest }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className="px-5 py-4 text-muted" {...rest}>
      {children}
    </td>
  );
}

export function Tr({ children, ...rest }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className="transition-colors hover:bg-accent/5" {...rest}>
      {children}
    </tr>
  );
}
