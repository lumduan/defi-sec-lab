"use client";

import type { MemoryStage } from "@/lib/types";
import { KeyValue, PackedWord, Pill, Raw, RawJson, Scroll, Section } from "@/components/ui";

export default function MemoryDetail({ stage, cite }: { stage: MemoryStage; cite: (id: string) => string | undefined }) {
  const m = stage.mapping;
  const s = stage.storage;
  const low = stage.comparisons.find((x) => x.field === "liquidityIndex");
  const high = stage.comparisons.find((x) => x.field === "currentLiquidityRate");
  const trace = stage.controls.trace;
  const preimage = m.preimage.replace(/^0x/, "");
  return (
    <>
      <Section
        title="1. Storage lives at the proxy"
        lead={
          <>
            Calls to the Pool proxy run the implementation&apos;s code with DELEGATECALL, but every read and write hits
            the <em>proxy&apos;s</em> storage. The implementation only defines the <em>layout</em>. Which layout
            applies depends on which revision is deployed.
          </>
        }
      >
        <KeyValue
          rows={[
            ["Pool proxy (read storage here)", <Raw key="p" value={stage.proxy.address} />],
            ["implementation (layout comes from here)", <Raw key="i" value={stage.proxy.implementation} />],
            ["storage slot 0 (lastInitializedRevision)", <>
              <Raw value={stage.proxy.slot0_word} copy={false} /> = {stage.proxy.revision_in_storage}
            </>],
            ["POOL_REVISION() in code", <>
              {stage.proxy.revision_in_code} → aave-v3-origin <b>{stage.proxy.source_tag}</b>
            </>],
          ]}
        />
      </Section>

      <Section
        title="2. Declaration order gives the slot"
        lead={
          <>
            Solidity numbers storage in declaration order, parent contracts first:{" "}
            <a href={cite("pool-inheritance")} target="_blank" rel="noreferrer">
              Pool is VersionedInitializable, PoolStorage, …
            </a>
          </>
        }
      >
        <Scroll>
          <table className="table">
            <thead>
              <tr>
                <th>slot</th>
                <th>variable</th>
                <th>type</th>
                <th>declared in</th>
              </tr>
            </thead>
            <tbody>
              {stage.layout.map((row) => (
                <tr key={row.slot} className={row.slot === String(m.declared_slot) ? "row--highlight" : undefined}>
                  <td className="mono">{row.slot}</td>
                  <td>
                    <code className="mono">{row.name}</code>
                  </td>
                  <td className="mono small">{row.type}</td>
                  <td>
                    <a href={cite(row.citation)} target="_blank" rel="noreferrer">
                      {row.contract}
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Scroll>
      </Section>

      <Section
        title="3. A mapping entry is a hash"
        lead={
          <>
            Slot {m.declared_slot} itself stays empty. The entry for a key lives at{" "}
            <code>keccak256(abi.encode(key, {m.declared_slot}))</code>. The key is USDC&apos;s <em>proxy</em> address,
            the one everyone calls.
          </>
        }
      >
        <div className="derivation">
          <div className="derivation__step">
            <span className="derivation__label">preimage (64 bytes)</span>
            <code className="mono wrap">
              0x<span className="seg seg--key">{preimage.slice(0, 64)}</span>
              <span className="seg seg--slot">{preimage.slice(64)}</span>
            </code>
            <span className="small muted">
              <span className="swatch swatch--key" /> USDC address, left-padded to 32 bytes ·{" "}
              <span className="swatch swatch--slot" /> {m.declared_slot} = 0x{m.declared_slot.toString(16)}
            </span>
          </div>
          <div className="derivation__arrow" aria-hidden="true">
            ↓ keccak256
          </div>
          <div className="derivation__step">
            <span className="derivation__label">base (the struct&apos;s first slot)</span>
            <Raw value={m.base} />
          </div>
          <div className="derivation__arrow" aria-hidden="true">
            ↓ + {m.field_offset} (configuration fills base+0)
          </div>
          <div className="derivation__step">
            <span className="derivation__label">slot we read</span>
            <Raw value={m.slot} />
          </div>
        </div>
        <ul className="bullets small">
          {m.struct_order.map((line) => (
            <li key={line} className="mono">
              {line}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="4. The raw read" lead={<>
        <code>{s.method}</code>({s.address}, slot, {s.block_tag}) returns one 32-byte word:
      </>}>
        <PackedWord
          word={s.word}
          highHex={s.high_hex}
          lowHex={s.low_hex}
          highName="currentLiquidityRate"
          lowName="liquidityIndex"
          highValue={s.high}
          lowValue={s.low}
        />
      </Section>

      <Section title="5. Compare with the function call">
        <Scroll>
          <table className="table">
            <thead>
              <tr>
                <th>field</th>
                <th>bits</th>
                <th>storage (half of the word)</th>
                <th>getReserveData()</th>
                <th>result</th>
              </tr>
            </thead>
            <tbody>
              {[low, high].filter(Boolean).map((c) => (
                <tr key={c!.field}>
                  <td>
                    <code className="mono">{c!.field}</code>
                  </td>
                  <td className="small">{c!.bits}</td>
                  <td>
                    <Raw value={c!.hex} copy={false} />
                    <div>
                      <code className="mono">{c!.storage}</code>
                    </div>
                  </td>
                  <td>
                    <code className="mono">{c!.function}</code>
                  </td>
                  <td>
                    <Pill tone={c!.match ? "pass" : "fail"}>{c!.match ? "MATCH" : "DIFFERENT"}</Pill>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Scroll>
        <p className="small muted">
          If these ever differ, check four things: the wrong half of the word (packing), the implementation address
          instead of the proxy, the wrong struct offset, or reads taken at different blocks.
        </p>
      </Section>

      <Section title="6. Controls">
        <KeyValue
          rows={[
            ["same slot on the implementation address", <>
              <Raw value={stage.controls.implementation_storage.word} copy={false} />{" "}
              <Pill tone={stage.controls.implementation_storage.is_zero ? "pass" : "fail"}>
                {stage.controls.implementation_storage.is_zero ? "empty, as expected" : "not empty"}
              </Pill>
            </>],
            [
              "node trace (prestateTracer) of getReserveData",
              trace.available ? (
                <>
                  node read {trace.pool_slots_read} Pool slots · this slot read{" "}
                  <Pill tone={trace.read_slot ? "pass" : "fail"}>{trace.read_slot ? "yes" : "no"}</Pill> · value matches{" "}
                  <Pill tone={trace.value_matches ? "pass" : "fail"}>{trace.value_matches ? "yes" : "no"}</Pill>
                </>
              ) : (
                <span className="muted">{trace.note}</span>
              ),
            ],
          ]}
        />
      </Section>

      <RawJson value={stage} />
    </>
  );
}
