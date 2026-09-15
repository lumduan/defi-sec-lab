"use client";

import { useState, type ReactNode } from "react";

import { groupDigits } from "@/lib/format";

export type Tone = "pass" | "fail" | "edge" | "info" | "muted";

export function toneForStatus(status: string): Tone {
  if (status === "pass") return "pass";
  if (status === "fail") return "fail";
  if (status === "info") return "info";
  return "muted";
}

export function Pill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`pill pill--${tone}`}>{children}</span>;
}

export function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="copy"
      aria-label="Copy value"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        } catch {
          /* clipboard unavailable: nothing to do */
        }
      }}
    >
      {copied ? "copied" : "copy"}
    </button>
  );
}

/** An exact raw value (hex word, ray integer, address) in monospace, with a copy button. */
export function Raw({ value, copy = true }: { value: string; copy?: boolean }) {
  return (
    <span className="raw">
      <code className="mono">{value}</code>
      {copy ? <CopyButton value={value} /> : null}
    </span>
  );
}

export function Section({ title, lead, children }: { title: string; lead?: ReactNode; children: ReactNode }) {
  return (
    <section className="section">
      <h3>{title}</h3>
      {lead ? <p className="section__lead">{lead}</p> : null}
      {children}
    </section>
  );
}

export function RawJson({ value, label = "Raw JSON for this stage" }: { value: unknown; label?: string }) {
  return (
    <details className="rawjson">
      <summary>{label}</summary>
      <pre className="mono">{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

/** A bar whose length is proportional to a byte count, on a shared maximum (so bars compare to scale). */
export function ByteBar({ size, max, tone, label }: { size: number; max: number; tone: "proxy" | "impl"; label?: string }) {
  const pct = Math.max(0.6, (size / max) * 100);
  return (
    <div className={`bytebar bytebar--${tone}`} role="img" aria-label={`${label ?? tone}: ${size} bytes of code`}>
      <span className="bytebar__fill" style={{ width: `${pct}%` }} />
      <span className="bytebar__label mono">
        <span className="bytebar__role">{tone === "proxy" ? "proxy" : "implementation"} · </span>
        {groupDigits(size)} bytes
      </span>
    </div>
  );
}

/** One 256-bit storage word, drawn as its two packed uint128 halves. */
export function PackedWord({
  word,
  highHex,
  lowHex,
  highName,
  lowName,
  highValue,
  lowValue,
}: {
  word: string;
  highHex: string;
  lowHex: string;
  highName: string;
  lowName: string;
  highValue: string;
  lowValue: string;
}) {
  const high = highHex.replace(/^0x/, "");
  const low = lowHex.replace(/^0x/, "");
  return (
    <figure className="packed" aria-label={`storage word ${word}`}>
      <div className="packed__word mono">
        <span className="packed__prefix">0x</span>
        <span className="packed__half packed__half--high">{high}</span>
        <span className="packed__half packed__half--low">{low}</span>
      </div>
      <div className="packed__legend">
        <div className="packed__cell packed__cell--high">
          <span className="packed__bits">bits 255 … 128 · high 128</span>
          <span className="packed__name">{highName}</span>
          <code className="mono">{highValue}</code>
        </div>
        <div className="packed__cell packed__cell--low">
          <span className="packed__bits">bits 127 … 0 · low 128</span>
          <span className="packed__name">{lowName}</span>
          <code className="mono">{lowValue}</code>
        </div>
      </div>
      <figcaption>One 32-byte slot holds two uint128 fields. Solidity packs the first-declared field into the low bits.</figcaption>
    </figure>
  );
}

export function KeyValue({ rows }: { rows: [ReactNode, ReactNode][] }) {
  return (
    <dl className="kv">
      {rows.map(([k, v], i) => (
        <div className="kv__row" key={i}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Scroll({ children }: { children: ReactNode }) {
  return <div className="scroll">{children}</div>;
}
