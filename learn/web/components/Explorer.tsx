"use client";

import { useCallback, useState, type ReactNode } from "react";

import { groupDigits, roundPercent, shortHex } from "@/lib/format";
import type { BooksStage, ChainStage, Inspection, Loaded, MemoryStage, ProxiesStage, Source } from "@/lib/types";
import StageDialog from "./StageDialog";
import ThemeToggle from "./ThemeToggle";
import BooksDetail from "./stages/BooksDetail";
import ChainDetail from "./stages/ChainDetail";
import MemoryDetail from "./stages/MemoryDetail";
import ProxiesDetail, { maxCodeSize } from "./stages/ProxiesDetail";
import { ByteBar, PackedWord, Pill, toneForStatus } from "./ui";

const STAGE_META = [
  { kicker: "Stage 1", title: "Are we in the real bank?", question: "Is this node really Arbitrum One, at exactly the block we pinned?" },
  { kicker: "Stage 2", title: "Storefront vs backroom", question: "Which contract holds the state, and where does the code live?" },
  { kicker: "Stage 3", title: "Open the books", question: "What does getReserveData(USDC) return, raw bytes first?" },
  { kicker: "Stage 4", title: "Read through to raw memory", question: "Does raw storage agree with the function call?" },
] as const;

function SourceBadge({ loaded, source }: { loaded: Loaded; source: Source }) {
  const data = loaded.data;
  if (!data) return null;
  const block = groupDigits(data.block.number);
  if (loaded.origin === "snapshot") {
    return (
      <p className="source-badge source-badge--snapshot" role="status">
        <Pill tone="muted">snapshot</Pill> Committed snapshot · block {block} · {data.block.timestamp_iso}
        <span className="small muted"> · backend not reachable ({loaded.error})</span>
      </p>
    );
  }
  return (
    <p className={`source-badge source-badge--${source}`} role="status">
      <Pill tone={source === "fork" ? "pass" : "info"}>{source === "fork" ? "live · pinned fork" : "live · real chain"}</Pill>{" "}
      {source === "fork" ? "Pinned Arbitrum fork" : "Arbitrum One latest block"} · block {block} · {data.block.timestamp_iso}
    </p>
  );
}

function StageNode({
  index,
  onOpen,
  status,
  children,
}: {
  index: number;
  onOpen: () => void;
  status: ReactNode;
  children: ReactNode;
}) {
  const meta = STAGE_META[index];
  const titleId = `stage-${index + 1}-title`;
  return (
    <li className="flow__item">
      {/* The whole card opens the details on click (unless text is being selected, so raw values stay copyable).
          Keyboard and screen-reader users get the real button in the heading. */}
      <article
        className="node"
        aria-labelledby={titleId}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("button, a")) return;
          if (window.getSelection()?.toString()) return;
          onOpen();
        }}
      >
        <header className="node__head">
          <span className="node__index" aria-hidden="true">
            {index + 1}
          </span>
          <div className="node__titles">
            <span className="kicker">{meta.kicker}</span>
            <h2 className="node__title" id={titleId}>
              <button type="button" className="node__button" onClick={onOpen} aria-haspopup="dialog">
                {meta.title}
              </button>
            </h2>
            <p className="node__question">{meta.question}</p>
          </div>
          <div className="node__status">{status}</div>
        </header>
        <div className="node__body">{children}</div>
        <p className="node__open" aria-hidden="true">
          Open the mechanism and raw values →
        </p>
      </article>
    </li>
  );
}

function ChainSummary({ stage }: { stage: ChainStage }) {
  const symbol = (status: string) => (status === "pass" ? "✓" : status === "info" ? "i" : status === "fail" ? "✗" : "–");
  return (
    <div className="summary">
      <ul className="checks">
        {stage.checks.map((c) => (
          <li key={c.id} className="checks__row">
            <Pill tone={toneForStatus(c.status)}>{symbol(c.status)}</Pill>
            <span>{c.label}</span>
            <code className="mono">{c.actual && c.actual.length > 20 ? shortHex(c.actual, 10, 8) : c.actual}</code>
          </li>
        ))}
      </ul>
      <div className="facts">
        <span>
          chain id <b className="mono">{stage.exchanges[0]?.decoded}</b>
        </span>
        <span>
          block <b className="mono">{groupDigits(stage.block.number)}</b>
        </span>
        <span>
          client <b className="mono">{stage.client_version}</b>
        </span>
      </div>
    </div>
  );
}

function ProxiesSummary({ stage }: { stage: ProxiesStage }) {
  const max = maxCodeSize(stage);
  const shown = stage.rows.filter((r) => r.key === "pool" || r.edge);
  const edge = stage.rows.find((r) => r.edge);
  return (
    <div className="summary">
      <div className="split">
        <div className="split__head">
          <span />
          <span>Proxy · storefront</span>
          <span>Implementation · backroom</span>
        </div>
        {shown.map((r) => (
          <div key={r.key} className={`split__row${r.edge ? " split__row--edge" : ""}`}>
            <div className="split__name">{r.label}</div>
            <ByteBar size={r.proxy.code_size} max={max} tone="proxy" label={`${r.label} proxy`} />
            {r.implementation ? (
              <ByteBar size={r.implementation.code_size} max={max} tone="impl" label={`${r.label} implementation`} />
            ) : (
              <span />
            )}
          </div>
        ))}
      </div>
      {edge ? (
        <p className="callout callout--edge">
          <strong>Edge.</strong> {edge.label} keeps its implementation in the <b>ZeppelinOS slot</b>, not EIP-1967.
          Its EIP-1967 slot reads <code className="mono">0x0…0</code>, so tools that only check that slot (such as{" "}
          <code>cast implementation</code>) find nothing.
        </p>
      ) : null}
    </div>
  );
}

function BooksSummary({ stage }: { stage: BooksStage }) {
  const indexField = stage.fields.find((x) => x.name === "liquidityIndex");
  const index = indexField && typeof indexField.decoded === "object" && "value" in indexField.decoded ? indexField.decoded : null;
  return (
    <div className="summary">
      <div className="scroll">
        <table className="table table--compact table--stack">
          <caption className="sr-only">Raw ray values first, then the conversion</caption>
          <thead>
            <tr>
              <th>field</th>
              <th>raw integer (ray)</th>
              <th>÷ 10²⁷</th>
              <th>%</th>
            </tr>
          </thead>
          <tbody>
            {index ? (
              <tr>
                <td data-label="field">liquidityIndex</td>
                <td data-label="raw integer (ray)">
                  <code className="mono">{index.raw}</code>
                </td>
                <td data-label="÷ 10²⁷">
                  <code className="mono">{index.value}</code>
                </td>
                <td data-label="%" className="muted">growth factor</td>
              </tr>
            ) : null}
            {[stage.rates.supply, stage.rates.borrow].map((r) => (
              <tr key={r.field}>
                <td data-label="field">{r.field}</td>
                <td data-label="raw integer (ray)">
                  <code className="mono">{r.raw}</code>
                </td>
                <td data-label="÷ 10²⁷">
                  <code className="mono">{r.fraction}</code>
                </td>
                <td data-label="%">
                  <b>{roundPercent(r.percent_apr)} % APR</b>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="risk risk--compact">
        {stage.risk_params.map((p) => (
          <div key={p.name} className="risk__card">
            <span className="risk__name">
              {p.name === "ltv" ? "LTV" : p.name === "liquidationThreshold" ? "Liquidation threshold" : "Liquidation bonus"}
            </span>
            <span className="risk__value">{p.human}</span>
            <span className="small muted mono">
              {groupDigits(p.raw)} bps · bits {p.bits}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MemorySummary({ stage }: { stage: MemoryStage }) {
  const s = stage.storage;
  const low = stage.comparisons.find((c) => c.field === "liquidityIndex");
  return (
    <div className="summary">
      <PackedWord
        word={s.word}
        highHex={s.high_hex}
        lowHex={s.low_hex}
        highName="currentLiquidityRate"
        lowName="liquidityIndex"
        highValue={s.high}
        lowValue={s.low}
      />
      {low ? (
        <div className="compare">
          <div className="compare__side">
            <span className="small muted">getReserveData().liquidityIndex</span>
            <code className="mono">{low.function}</code>
          </div>
          <div className="compare__eq">
            <Pill tone={low.match ? "pass" : "fail"}>{low.match ? "MATCH" : "DIFFERENT"}</Pill>
          </div>
          <div className="compare__side">
            <span className="small muted">storage slot base+1, low 128 bits</span>
            <code className="mono">{low.storage}</code>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function Explorer({ initial }: { initial: Loaded }) {
  const [loaded, setLoaded] = useState<Loaded>(initial);
  const [source, setSource] = useState<Source>("fork");
  const [pending, setPending] = useState<Source | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<number | null>(null);

  const switchSource = useCallback(
    async (next: Source) => {
      if (next === source && loaded.origin !== "snapshot") return;
      setPending(next);
      setError(null);
      try {
        const response = await fetch(`/api/inspection?source=${next}`, { cache: "no-store" });
        const body = (await response.json()) as Loaded;
        if (body.data) {
          setLoaded(body);
          setSource(next);
        } else {
          setError(body.error ?? "the inspector API returned no data");
        }
      } catch {
        setError("could not reach this page's server");
      } finally {
        setPending(null);
      }
    },
    [source, loaded.origin],
  );

  const data = loaded.data as Inspection;
  const [chain, proxies, books, memory] = data.stages;
  const cite = (id: string) => data.citations.find((c) => c.id === id)?.url;
  const anyCheckFailed = chain.checks.some((c) => c.status === "fail");
  const allChecksPass = chain.checks.every((c) => c.status === "pass" || c.status === "info");
  const edgeCount = proxies.rows.filter((r) => r.edge).length;
  const allMatch = memory.comparisons.every((c) => c.match);

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <img src="/icon.svg" alt="" width={28} height={28} />
          <span>
            defi-sec-lab <span className="muted">/ learn</span>
          </span>
        </div>
        <div className="topbar__controls">
          <div className="segmented" role="group" aria-label="Data source">
            {(["fork", "live"] as const).map((s) => (
              <button
                key={s}
                type="button"
                className="segmented__button"
                aria-pressed={source === s && loaded.origin === "api"}
                disabled={pending !== null}
                onClick={() => switchSource(s)}
              >
                {pending === s ? "loading…" : s === "fork" ? "Pinned fork" : "Live chain"}
              </button>
            ))}
          </div>
          <ThemeToggle />
        </div>
      </header>

      <section className="hero">
        <p className="kicker">Aave V3 · native USDC · Arbitrum One</p>
        <h1>Reading a lending market from raw state</h1>
        <p className="hero__lead">
          Four stages, top to bottom. Each one is a question you can check yourself. Open a stage to see the mechanism
          and every raw value: hex words, ray integers and packed storage.
        </p>
        <SourceBadge loaded={loaded} source={source} />
        {error ? (
          <p className="alert" role="alert">
            Could not load {pending ?? "that view"}: {error}. Still showing the previous data.
          </p>
        ) : null}
      </section>

      <ol className="flow">
        <StageNode
          index={0}
          onOpen={() => setOpen(0)}
          status={
            anyCheckFailed ? (
              <Pill tone="fail">check failed</Pill>
            ) : allChecksPass ? (
              <Pill tone="pass">verified</Pill>
            ) : (
              <Pill tone="muted">partly verified</Pill>
            )
          }
        >
          <ChainSummary stage={chain} />
        </StageNode>
        <StageNode index={1} onOpen={() => setOpen(1)} status={edgeCount ? <Pill tone="edge">{edgeCount} edge case</Pill> : <Pill tone="info">proxies</Pill>}>
          <ProxiesSummary stage={proxies} />
        </StageNode>
        <StageNode index={2} onOpen={() => setOpen(2)} status={<Pill tone="info">{books.call.returndata_bytes} bytes</Pill>}>
          <BooksSummary stage={books} />
        </StageNode>
        <StageNode index={3} onOpen={() => setOpen(3)} status={<Pill tone={allMatch ? "pass" : "fail"}>{allMatch ? "match" : "mismatch"}</Pill>}>
          <MemorySummary stage={memory} />
        </StageNode>
      </ol>

      <StageDialog
        open={open !== null}
        onClose={() => setOpen(null)}
        kicker={open !== null ? `${STAGE_META[open].kicker} · block ${groupDigits(data.block.number)}` : ""}
        title={open !== null ? STAGE_META[open].title : ""}
      >
        {open === 0 ? <ChainDetail stage={chain} /> : null}
        {open === 1 ? <ProxiesDetail stage={proxies} cite={cite} /> : null}
        {open === 2 ? <BooksDetail stage={books} cite={cite} /> : null}
        {open === 3 ? <MemoryDetail stage={memory} cite={cite} /> : null}
      </StageDialog>

      <footer className="footer">
        <details>
          <summary>Sources ({data.citations.length})</summary>
          <ul>
            {data.citations.map((c) => (
              <li key={c.id}>
                <a href={c.url} target="_blank" rel="noreferrer">
                  {c.label}
                </a>
              </li>
            ))}
          </ul>
        </details>
        <p className="small muted">
          How this page gets data: the browser only talks to this page&apos;s server. That server calls an internal
          API on a Docker network that has no route to the host. The API reads the pinned anvil fork, or the real chain
          through <code>RPC_URL</code>, and that URL never leaves the API. Generated {data.generated_at}. Source:{" "}
          <a href="https://github.com/lumduan/defi-sec-lab" target="_blank" rel="noreferrer">
            lumduan/defi-sec-lab
          </a>
          .
        </p>
      </footer>
    </div>
  );
}
