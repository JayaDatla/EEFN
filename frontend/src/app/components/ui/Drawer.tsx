// UPGRADE_PLAN.md H.2 primitive: Radix Dialog used as a slide-in side panel.
// Blur/shadow are used here deliberately -- this is a true floating overlay,
// the one case H.1 allows it.
"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { ReactNode } from "react";
import { X } from "lucide-react";

export function Drawer({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-border bg-surface p-5 shadow-2xl">
          <div className="mb-4 flex items-center justify-between">
            <Dialog.Title className="text-sm font-semibold text-ink">{title}</Dialog.Title>
            <Dialog.Close className="rounded p-1 text-muted hover:text-ink" aria-label="Close">
              <X size={16} />
            </Dialog.Close>
          </div>
          <div className="flex-1 overflow-y-auto">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
