// UPGRADE_PLAN.md H.2 primitive: Radix Tabs styled against tokens.
"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import { ReactNode } from "react";

export const Tabs = RadixTabs.Root;

export function TabsList({ children }: { children: ReactNode }) {
  return (
    <RadixTabs.List className="flex gap-1 border-b border-border">
      {children}
    </RadixTabs.List>
  );
}

export function TabsTrigger({ value, children }: { value: string; children: ReactNode }) {
  return (
    <RadixTabs.Trigger
      value={value}
      className="border-b-2 border-transparent px-3 py-2 text-xs font-medium text-muted transition-colors hover:text-ink data-[state=active]:border-accent data-[state=active]:text-ink"
    >
      {children}
    </RadixTabs.Trigger>
  );
}

export function TabsContent({ value, children }: { value: string; children: ReactNode }) {
  return (
    <RadixTabs.Content value={value} className="pt-4">
      {children}
    </RadixTabs.Content>
  );
}
