"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** Native modal <dialog>: focus is trapped while open, Esc closes it, focus returns to the opener. */
export default function StageDialog({
  open,
  onClose,
  kicker,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  kicker: string;
  title: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby="stage-dialog-title"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose(); // click on the backdrop
      }}
    >
      <div className="dialog__panel">
        <header className="dialog__header">
          <div>
            <p className="kicker">{kicker}</p>
            <h2 id="stage-dialog-title">{title}</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close details">
            ✕
          </button>
        </header>
        <div className="dialog__body">{open ? children : null}</div>
      </div>
    </dialog>
  );
}
