"use client";

import { groupDigits } from "@/lib/format";
import type { ChainStage } from "@/lib/types";
import { KeyValue, Pill, Raw, RawJson, Scroll, Section, toneForStatus } from "@/components/ui";

export default function ChainDetail({ stage }: { stage: ChainStage }) {
  const b = stage.block;
  return (
    <>
      <Section
        title="The mechanism"
        lead={
          <>
            A node answers JSON-RPC: <code>{"{ method, params }"}</code> in, <code>{"{ result }"}</code> out, with numbers
            as hex strings. A block <em>number</em> is only a label. The block <em>hash</em> is the hash of the block
            header, and the header includes the state root, so two nodes that report the same hash at the same height
            agree on the entire state.
          </>
        }
      >
        <ul className="bullets">
          <li>
            <code>eth_chainId</code>: which chain the node claims to be. 42161 is Arbitrum One.
          </li>
          <li>
            <code>eth_blockNumber</code>: the head. Nothing is mined on the pinned fork, so the head is the pin.
          </li>
          <li>
            <code>eth_getBlockByNumber</code>: the header, including hash, timestamp and Arbitrum&apos;s L1 block.
          </li>
          <li>
            <code>web3_clientVersion</code>: which software answered.
          </li>
        </ul>
      </Section>

      <Section title="Checks">
        <Scroll>
          <table className="table">
            <thead>
              <tr>
                <th>check</th>
                <th>expected</th>
                <th>actual</th>
                <th>result</th>
              </tr>
            </thead>
            <tbody>
              {stage.checks.map((c) => (
                <tr key={c.id}>
                  <td>
                    {c.label}
                    {c.note ? <div className="small muted">{c.note}</div> : null}
                  </td>
                  <td>{c.expected ? <Raw value={c.expected} copy={false} /> : "—"}</td>
                  <td>{c.actual ? <Raw value={c.actual} copy={false} /> : "—"}</td>
                  <td>
                    <Pill tone={toneForStatus(c.status)}>{c.status.replace("_", " ")}</Pill>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Scroll>
      </Section>

      <Section title="Raw requests and responses" lead="Exactly what came back over the wire, before any conversion.">
        <Scroll>
          <table className="table">
            <thead>
              <tr>
                <th>method</th>
                <th>params</th>
                <th>raw result</th>
                <th>decoded</th>
              </tr>
            </thead>
            <tbody>
              {stage.exchanges.map((e) => (
                <tr key={e.method}>
                  <td>
                    <code className="mono">{e.method}</code>
                  </td>
                  <td>
                    <code className="mono">{JSON.stringify(e.params)}</code>
                  </td>
                  <td>
                    <pre className="mono cell-pre">
                      {typeof e.result === "string" ? e.result : JSON.stringify(e.result, null, 2)}
                    </pre>
                    {e.note ? <div className="small muted">{e.note}</div> : null}
                  </td>
                  <td>{e.decoded}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Scroll>
      </Section>

      <Section
        title="The block"
        lead="Arbitrum has two block numbers: the L2 block the RPC reports, and the L1 (Ethereum) block it links to. Inside the EVM, block.number returns that L1 number (as the sequencer saw it), not the L2 number."
      >
        <KeyValue
          rows={[
            ["number (L2)", <>
              <Raw value={b.number_hex} copy={false} /> = <b>{groupDigits(b.number)}</b>
            </>],
            ["hash", <Raw key="h" value={b.hash} />],
            ["timestamp", <>
              <Raw value={b.timestamp_hex} copy={false} /> = {b.timestamp} = {b.timestamp_iso}
            </>],
            [
              "l1BlockNumber",
              b.l1_block_number_hex ? (
                <>
                  <Raw value={b.l1_block_number_hex} copy={false} /> = {groupDigits(b.l1_block_number ?? 0)}
                </>
              ) : (
                "—"
              ),
            ],
            ["client", <code key="c" className="mono">{stage.client_version}</code>],
          ]}
        />
      </Section>

      <RawJson value={stage} />
    </>
  );
}
