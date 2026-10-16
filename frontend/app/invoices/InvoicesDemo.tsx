"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import { DemoShell } from "@/app/components/DemoShell";
import { ServerStatus } from "@/app/components/ServerStatus";
import shared from "@/app/components/shared.module.css";
import type { ApiClient, Config, ExtractResponse } from "@/lib/api";
import { setupClient } from "@/lib/client";
import { batchReducer, buildCsv, buildJson, fileKind, rejectReason, type Card } from "@/lib/invoices";
import { countPdfPages } from "@/lib/pdf";
import { describeError, SLOW_AFTER_MS, waitForServer } from "@/lib/wake";
import { InvoiceCard } from "./InvoiceCard";
import styles from "./invoices.module.css";

const SAMPLES = [
  { url: "/samples/sample-invoice.pdf", name: "sample-invoice.pdf", type: "application/pdf" },
  { url: "/samples/sample-receipt.jpg", name: "sample-receipt.jpg", type: "image/jpeg" },
];

type Server =
  | { phase: "waking"; slow: boolean }
  | { phase: "ready"; config: Config }
  | { phase: "failed"; message: string }
  | { phase: "unconfigured" };

type Job = { id: string; file: File };

function download(text: string, fileName: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

export function InvoicesDemo() {
  const [setup] = useState(setupClient);
  const client = setup.kind === "unconfigured" ? null : setup.client;
  const [server, setServer] = useState<Server>(
    setup.kind === "unconfigured" ? { phase: "unconfigured" } : { phase: "waking", slow: false },
  );
  const [cards, dispatch] = useReducer(batchReducer, []);
  const [notice, setNotice] = useState<string | null>(null);
  const waking = server.phase === "waking";

  // The work list lives outside React state: one worker drains it, one file at a time.
  const queue = useRef<Job[]>([]);
  const files = useRef(new Map<string, File>());
  const running = useRef(false);
  const objectUrls = useRef<string[]>([]);
  const nextId = useRef(0);

  useEffect(() => {
    if (!client || !waking) return;
    let cancelled = false;
    const slowTimer = setTimeout(() => setServer({ phase: "waking", slow: true }), SLOW_AFTER_MS);
    (async () => {
      if (!(await waitForServer(client, () => cancelled))) return;
      const config = await client.config();
      if (!cancelled) setServer({ phase: "ready", config });
    })()
      .catch((err) => {
        if (!cancelled) setServer({ phase: "failed", message: describeError(err) });
      })
      .finally(() => clearTimeout(slowTimer));
    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, [client, waking]);

  useEffect(() => {
    const urls = objectUrls.current;
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  const drain = async (api: ApiClient) => {
    if (running.current) return;
    running.current = true;
    try {
      for (let job = queue.current.shift(); job; job = queue.current.shift()) {
        dispatch({ type: "start", id: job.id });
        try {
          dispatch({ type: "done", id: job.id, result: await api.extractInvoice(job.file) });
        } catch (err) {
          dispatch({ type: "failed", id: job.id, message: describeError(err) });
        }
      }
    } finally {
      running.current = false;
    }
  };

  const addFiles = async (picked: File[]) => {
    if (!client || server.phase !== "ready" || picked.length === 0) return;
    const { config } = server;
    const room = Math.max(0, config.invoice_max_files - cards.length);
    setNotice(
      picked.length > room
        ? `A batch holds up to ${config.invoice_max_files} files, so ${picked.length - room} ${picked.length - room === 1 ? "file was" : "files were"} left out. Start over to add more.`
        : null,
    );
    const added: Card[] = [];
    for (const file of picked.slice(0, room)) {
      const kind = fileKind(file);
      const pages = kind === "pdf" ? await countPdfPages(file).catch(() => null) : null;
      const reason = rejectReason(file, pages, config);
      const id = `f${++nextId.current}`;
      const url = URL.createObjectURL(file);
      objectUrls.current.push(url);
      added.push({
        id,
        name: file.name,
        kind,
        url,
        status: reason ? { state: "failed", message: reason, retryable: false } : { state: "queued" },
      });
      if (!reason) {
        files.current.set(id, file);
        queue.current.push({ id, file });
      }
    }
    dispatch({ type: "add", cards: added });
    void drain(client);
  };

  const retry = (id: string) => {
    const file = files.current.get(id);
    if (!client || !file) return;
    dispatch({ type: "retry", id });
    queue.current.push({ id, file });
    void drain(client);
  };

  const startOver = () => {
    queue.current = [];
    files.current.clear();
    objectUrls.current.forEach((url) => URL.revokeObjectURL(url));
    objectUrls.current.length = 0;
    setNotice(null);
    dispatch({ type: "clear" });
  };

  const loadSamples = async () => {
    try {
      const loaded = await Promise.all(
        SAMPLES.map(async (sample) => {
          const response = await fetch(sample.url);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return new File([await response.blob()], sample.name, { type: sample.type });
        }),
      );
      await addFiles(loaded);
    } catch {
      setNotice("The sample invoices couldn't be loaded. Reload the page and try again.");
    }
  };

  const results: ExtractResponse[] = cards.flatMap((c) => (c.status.state === "done" ? [c.status.result] : []));
  const ready = server.phase === "ready";
  const full = ready && cards.length >= server.config.invoice_max_files;

  return (
    <DemoShell>
      <main className={styles.page}>
        <div className={styles.intro}>
          <h1 className={styles.title}>Invoice → JSON</h1>
          <p className={styles.lede}>
            Upload invoices or receipts, as PDFs or photos, and get their vendor, dates, line items, tax and totals as
            structured data. The app then does the arithmetic itself, so a misread number shows up as a failed check.
            {ready && ` Extraction by ${server.config.provider_label}.`}
            {setup.kind === "mock" && " Running against the built-in mock server."}
          </p>
        </div>

        <ServerStatus server={server} onRetry={() => setServer({ phase: "waking", slow: true })} />

        {ready && !full && <UploadArea config={server.config} onFiles={addFiles} onSamples={loadSamples} />}

        {notice && (
          <p className={styles.notice} role="status">
            {notice}
          </p>
        )}

        {cards.length > 0 && (
          <section className={styles.batch} aria-labelledby="batch-heading">
            <div className={styles.toolbar}>
              <h2 id="batch-heading" className={styles.batchHeading}>
                {results.length} of {cards.length} {cards.length === 1 ? "file" : "files"} extracted
              </h2>
              <div className={styles.actions}>
                <button
                  type="button"
                  className={shared.secondaryButton}
                  disabled={results.length === 0}
                  onClick={() => download("﻿" + buildCsv(results), "invoices.csv", "text/csv;charset=utf-8")}
                >
                  Download CSV
                </button>
                <button
                  type="button"
                  className={shared.secondaryButton}
                  disabled={results.length === 0}
                  onClick={() => download(buildJson(results), "invoices.json", "application/json")}
                >
                  Download JSON
                </button>
                <button type="button" className={styles.linkButton} onClick={startOver}>
                  Start over
                </button>
              </div>
            </div>
            <ul className={styles.cards}>
              {cards.map((card) => (
                <InvoiceCard key={card.id} card={card} onRetry={() => retry(card.id)} />
              ))}
            </ul>
          </section>
        )}
      </main>
    </DemoShell>
  );
}

function UploadArea(props: { config: Config; onFiles: (files: File[]) => void; onSamples: () => void }) {
  const [dragging, setDragging] = useState(false);
  const { config } = props;
  return (
    <div className={styles.upload}>
      <label
        className={styles.dropzone}
        data-dragging={dragging || undefined}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          props.onFiles(Array.from(e.dataTransfer.files));
        }}
      >
        <input
          type="file"
          multiple
          accept="application/pdf,.pdf,image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
          className="visually-hidden"
          onChange={(e) => {
            const picked = Array.from(e.target.files ?? []);
            e.target.value = "";
            props.onFiles(picked);
          }}
        />
        <span className={styles.dropzoneTitle}>Drop invoices or receipts here or choose files</span>
        <span className={styles.dropzoneLimits}>
          Up to {config.invoice_max_files} files: PDFs of up to {config.invoice_max_pages} pages, or PNG, JPEG and WebP
          photos, each up to {config.max_file_mb} MB. Files are read one at a time.
        </span>
      </label>
      <div className={styles.sampleRow}>
        <span>No invoice to hand?</span>
        <button type="button" className={shared.secondaryButton} onClick={props.onSamples}>
          Try sample invoices
        </button>
      </div>
    </div>
  );
}
