"use client";

import { groupDigits } from "@/lib/format";
import type { BooksStage, Field, RayIndex, RayRate, TimestampDecoded } from "@/lib/types";
import { KeyValue, Pill, Raw, RawJson, Scroll, Section } from "@/components/ui";

function isRate(d: Field["decoded"]): d is RayRate {
  return typeof d === "object" && "percent_apr" in d;
}
function isIndex(d: Field["decoded"]): d is RayIndex {
  return typeof d === "object" && "value" in d;
}
function isTimestamp(d: Field["decoded"]): d is TimestampDecoded {
  return typeof d === "object" && "iso" in d;
}

function Decoded({ field }: { field: Field }) {
  const d = field.decoded;
  if (typeof d === "string") return field.type === "address" ? <Raw value={d} /> : <code className="mono">{d}</code>;
  if (isRate(d))
    return (
      <span className="small">
        ÷ 10²⁷ = <code className="mono">{d.fraction}</code> → <b>{d.percent_apr} % APR</b>
      </span>
    );
  if (isIndex(d))
    return (
      <span className="small">
        ÷ 10²⁷ = <code className="mono">{d.value}</code>
      </span>
    );
  if (isTimestamp(d))
    return (
      <span className="small">
        {d.iso} ({d.seconds_before_block} s before the block)
      </span>
    );
  return null;
}

function RateSteps({ title, rate }: { title: string; rate: RayRate & { field: string } }) {
  return (
    <div className="steps">
      <h4>
        {title} <span className="muted small">({rate.field})</span>
      </h4>
      <ol>
        <li>
          raw integer, as stored: <Raw value={rate.raw} />
        </li>
        <li>
          unit: <em>ray</em> means 27 implied decimals, so ÷ 10²⁷ = <code className="mono">{rate.fraction}</code> per
          year
        </li>
        <li>
          × 100 = <b className="mono">{rate.percent_apr} %</b> APR (simple annual rate)
        </li>
        <li className="muted">
          derived, not stored: APY ≈ {rate.percent_apy_derived} % using <code className="mono">{rate.apy_formula}</code>
        </li>
      </ol>
    </div>
  );
}

export default function BooksDetail({ stage, cite }: { stage: BooksStage; cite: (id: string) => string | undefined }) {
  const c = stage.call;
  const cfg = stage.configuration;
  return (
    <>
      <Section
        title="The call"
        lead={
          <>
            <code>getReserveData</code> returns a fixed-size struct, so the ABI puts its 15 fields back to back, one
            32-byte word each: {c.word_count} × 32 = {c.returndata_bytes} bytes. Smaller types are left-padded with zeros
            inside their word.
          </>
        }
      >
        <KeyValue
          rows={[
            ["to (Pool proxy)", <Raw key="t" value={c.to} />],
            ["function", <code key="f" className="mono">{c.function}</code>],
            ["selector = keccak256(signature)[0:4]", <Raw key="s" value={c.selector} copy={false} />],
            ["calldata (selector ‖ USDC padded)", <Raw key="cd" value={c.calldata} />],
            ["block", <code key="b" className="mono">{c.block_tag}</code>],
            ["return data", <span key="r">{c.returndata_bytes} bytes</span>],
          ]}
        />
        <details className="rawjson">
          <summary>Raw return data ({c.returndata_bytes} bytes)</summary>
          <pre className="mono wrap">{c.returndata}</pre>
        </details>
      </Section>

      <Section
        title="Rates: raw first, then units"
        lead="Stored rates are per-year values in ray, written by the last state-changing action. APY is not stored anywhere."
      >
        <div className="grid-2">
          <RateSteps title="Supply rate" rate={stage.rates.supply} />
          <RateSteps title="Variable borrow rate" rate={stage.rates.borrow} />
        </div>
      </Section>

      <Section title="All 15 words" lead="Word index, raw 32-byte word, raw integer, then decoded value.">
        <Scroll>
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>field · type</th>
                <th>raw word</th>
                <th>raw integer</th>
                <th>decoded</th>
              </tr>
            </thead>
            <tbody>
              {stage.fields.map((f) => (
                <tr key={f.index}>
                  <td className="mono">{f.index}</td>
                  <td>
                    <code className="mono">{f.name}</code>
                    <div className="small muted">
                      {f.type}
                      {f.note ? ` · ${f.note}` : ""}
                    </div>
                  </td>
                  <td>
                    <Raw value={f.word} copy={false} />
                  </td>
                  <td>
                    <code className="mono break">{f.raw}</code>
                  </td>
                  <td>
                    <Decoded field={f} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Scroll>
      </Section>

      <Section
        title="The risk parameters live in one bitmap"
        lead={
          <>
            Word 0 packs many settings at fixed bit positions (
            <a href={cite("reserve-configuration")} target="_blank" rel="noreferrer">
              ReserveConfiguration.sol
            </a>
            ). Multi-bit fields span whole hex digits, so each one reads straight off the word.
          </>
        }
      >
        <div className="risk">
          {stage.risk_params.map((p) => (
            <div key={p.name} className="risk__card">
              <span className="risk__name">{p.name}</span>
              <span className="risk__value">{p.human}</span>
              <span className="small muted mono">
                raw {groupDigits(p.raw)} bps · hex {p.hex} · bits {p.bits}
              </span>
            </div>
          ))}
        </div>
        <KeyValue rows={[["configuration word", <Raw key="w" value={cfg.word} />], ["as integer", <code key="i" className="mono break">{cfg.raw}</code>]]} />
        <Scroll>
          <table className="table">
            <thead>
              <tr>
                <th>field</th>
                <th>bits</th>
                <th>hex slice</th>
                <th>raw</th>
                <th>meaning</th>
              </tr>
            </thead>
            <tbody>
              {cfg.fields.map((f) => (
                <tr key={f.name} className={f.risk_param ? "row--highlight" : undefined}>
                  <td>
                    <code className="mono">{f.name}</code>
                  </td>
                  <td className="mono">{f.bits}</td>
                  <td className="mono">{f.hex}</td>
                  <td className="mono">{groupDigits(f.raw)}</td>
                  <td>
                    {f.human} <span className="small muted">({f.unit})</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Scroll>
        <h4>
          Flags byte · bits {cfg.flags_byte.bits} · hex <code className="mono">{cfg.flags_byte.hex}</code> · binary{" "}
          <code className="mono">{cfg.flags_byte.binary}</code>
        </h4>
        <div className="flags">
          {cfg.flags_byte.flags.map((f) => (
            <span key={f.bit} className={`flag${f.value ? " flag--on" : ""}${f.name.startsWith("unused") ? " flag--unused" : ""}`}>
              <span className="mono">bit {f.bit}</span> {f.name} = {f.value}
            </span>
          ))}
        </div>
        <h4>Bits left behind by removed fields</h4>
        <p className="small muted">Shown raw, not interpreted: a removed field can leave old bits in place.</p>
        <div className="flags">
          {cfg.holes.map((h) => (
            <span key={h.bits} className={`flag${h.raw ? " flag--edge" : ""}`}>
              <span className="mono">bits {h.bits}</span> {h.name} = {h.raw}
            </span>
          ))}
        </div>
        {stage.risk_params.length === 3 ? (
          <p className="small">
            <Pill tone="info">note</Pill> LTV caps how much can be borrowed against this collateral. The liquidation
            threshold sets when a position becomes liquidatable, and the bonus is the liquidator&apos;s discount. The
            reserve factor, caps and flags set how the market itself behaves.
          </p>
        ) : null}
      </Section>

      <RawJson value={stage} />
    </>
  );
}
