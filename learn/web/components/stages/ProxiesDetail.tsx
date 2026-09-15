"use client";

import type { ProxiesStage } from "@/lib/types";
import { ByteBar, KeyValue, Pill, Raw, RawJson, Scroll, Section } from "@/components/ui";

export function maxCodeSize(stage: ProxiesStage): number {
  return Math.max(...stage.rows.flatMap((r) => [r.proxy.code_size, r.implementation?.code_size ?? 0]));
}

export default function ProxiesDetail({ stage, cite }: { stage: ProxiesStage; cite: (id: string) => string | undefined }) {
  const max = maxCodeSize(stage);
  const d = stage.slot_derivations;
  return (
    <>
      <Section
        title="The mechanism"
        lead={
          <>
            A proxy is a small contract (the storefront) that forwards every call with <code>DELEGATECALL</code> to an
            implementation (the backroom). The implementation&apos;s code runs against the <em>proxy&apos;s</em>{" "}
            storage. The proxy keeps the implementation address in one fixed storage slot. That slot number is derived
            from a hash, so in practice it cannot collide with ordinary variables, which count up from slot 0.
          </>
        }
      >
        <Scroll>
          <table className="table">
            <thead>
              <tr>
                <th>standard</th>
                <th>preimage</th>
                <th>keccak256(preimage)</th>
                <th>slot</th>
                <th>used by</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <a href={cite(d.eip1967.citation)} target="_blank" rel="noreferrer">
                    EIP-1967
                  </a>
                </td>
                <td>
                  <code className="mono">&quot;{d.eip1967.preimage}&quot;</code>
                </td>
                <td>
                  <Raw value={d.eip1967.keccak256} copy={false} />
                </td>
                <td>
                  <Raw value={d.eip1967.slot} />
                  <div className="small muted">keccak − 1</div>
                </td>
                <td>Aave Pool, aToken, debt token, USDC.e</td>
              </tr>
              <tr>
                <td>
                  <a href={cite(d.zeppelinos.citation)} target="_blank" rel="noreferrer">
                    ZeppelinOS (legacy)
                  </a>
                </td>
                <td>
                  <code className="mono">&quot;{d.zeppelinos.preimage}&quot;</code>
                </td>
                <td>
                  <Raw value={d.zeppelinos.keccak256} copy={false} />
                </td>
                <td>
                  <Raw value={d.zeppelinos.slot} />
                  <div className="small muted">keccak, no − 1</div>
                </td>
                <td>Circle&apos;s native USDC</td>
              </tr>
            </tbody>
          </table>
        </Scroll>
      </Section>

      <Section
        title="Code size, to scale"
        lead="eth_getCode returns the runtime bytecode stored at an address. All bars share one maximum, so their lengths compare directly."
      >
        <div className="split">
          <div className="split__head">
            <span />
            <span>Proxy · storefront</span>
            <span>Implementation · backroom</span>
          </div>
          {stage.rows.map((r) => (
            <div key={r.key} className={`split__row${r.edge ? " split__row--edge" : ""}`}>
              <div className="split__name">
                {r.label} {r.edge ? <Pill tone="edge">edge</Pill> : null}
              </div>
              <ByteBar size={r.proxy.code_size} max={max} tone="proxy" label={`${r.label} proxy`} />
              {r.implementation ? (
                <ByteBar size={r.implementation.code_size} max={max} tone="impl" label={`${r.label} implementation`} />
              ) : (
                <span className="muted">no implementation found</span>
              )}
            </div>
          ))}
        </div>
      </Section>

      <Section
        title="Both slots, read on every proxy"
        lead="eth_getStorageAt(address, slot) at the same block. On each contract exactly one slot holds an address."
      >
        <Scroll>
          <table className="table">
            <thead>
              <tr>
                <th>contract</th>
                <th>EIP-1967 slot word</th>
                <th>ZeppelinOS slot word</th>
                <th>implementation</th>
              </tr>
            </thead>
            <tbody>
              {stage.rows.map((r) => (
                <tr key={r.key} className={r.edge ? "row--edge" : undefined}>
                  <td>
                    <a href={cite(r.citation)} target="_blank" rel="noreferrer">
                      {r.label}
                    </a>
                    <div className="small muted mono">{r.address}</div>
                  </td>
                  <td>
                    <Raw value={r.slots.eip1967} copy={false} />
                  </td>
                  <td>
                    <Raw value={r.slots.zeppelinos} copy={false} />
                  </td>
                  <td>
                    {r.implementation ? (
                      <>
                        <Raw value={r.implementation.address} />
                        <div className="small">
                          found in <Pill tone={r.edge ? "edge" : "info"}>{r.implementation_slot}</Pill>
                        </div>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Scroll>
        <div className="callout callout--edge" role="note">
          <strong>Edge case that standard tools miss.</strong> {stage.edge_note}
        </div>
      </Section>

      <Section title="Registry cross-check" lead="Aave contracts don't hardcode the Pool. They ask the PoolAddressesProvider.">
        <KeyValue
          rows={[
            ["call", <>
              <code className="mono">{stage.registry.call}</code> · selector{" "}
              <Raw value={stage.registry.selector} copy={false} />
            </>],
            ["raw result", <Raw key="r" value={stage.registry.result} />],
            ["decoded (low 20 bytes)", <Raw key="d" value={stage.registry.decoded} />],
            ["address book", <>
              <Raw value={stage.registry.address_book} copy={false} />{" "}
              <Pill tone={stage.registry.match ? "pass" : "fail"}>{stage.registry.match ? "match" : "mismatch"}</Pill>
            </>],
          ]}
        />
      </Section>

      <Section
        title="What the proxy code routes itself"
        lead={
          <>
            A proxy&apos;s bytecode starts with a function router. Byte <code>0x63</code> is PUSH4; the 4 bytes after it
            are a selector the proxy&apos;s own code checks for (its admin functions, such as <code>upgradeTo</code>).
            Every other selector goes straight to DELEGATECALL.
          </>
        }
      >
        <Scroll>
          <table className="table">
            <thead>
              <tr>
                <th>contract</th>
                <th>first 32 bytes of code</th>
                <th>selectors found as PUSH4</th>
              </tr>
            </thead>
            <tbody>
              {stage.rows.map((r) => (
                <tr key={r.key}>
                  <td>{r.label}</td>
                  <td>
                    <Raw value={r.proxy.code_head} copy={false} />
                  </td>
                  <td>
                    {r.proxy.dispatcher_selectors.filter((s) => s.push4_found).length === 0
                      ? "—"
                      : r.proxy.dispatcher_selectors
                          .filter((s) => s.push4_found)
                          .map((s) => (
                            <div key={s.selector} className="small">
                              <code className="mono">{s.selector}</code> {s.signature}
                            </div>
                          ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Scroll>
      </Section>

      <RawJson value={stage} />
    </>
  );
}
