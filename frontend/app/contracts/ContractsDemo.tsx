"use client";

import { useEffect, useState } from "react";
import { DemoShell } from "@/app/components/DemoShell";
import { ServerStatus } from "@/app/components/ServerStatus";
import shared from "@/app/components/shared.module.css";
import type { Config, ReviewResponse } from "@/lib/api";
import { setupClient } from "@/lib/client";
import { countPdfPages } from "@/lib/pdf";
import { currentStep, reviewSteps } from "@/lib/review";
import { describeError, SLOW_AFTER_MS, waitForServer } from "@/lib/wake";
import { ReviewResult } from "./ReviewResult";
import styles from "./contracts.module.css";

const SAMPLE = { url: "/samples/sample-lease.pdf", name: "sample-lease.pdf" };

type Server =
  | { phase: "waking"; slow: boolean }
  | { phase: "ready"; config: Config }
  | { phase: "failed"; message: string }
  | { phase: "unconfigured" };

type Run =
  | { kind: "idle" }
  | { kind: "reviewing"; fileName: string; pages: number | null; startedAt: number }
  | { kind: "done"; result: ReviewResponse; fileUrl: string }
  | { kind: "failed"; fileName: string; message: string };

function rejectReason(file: File, config: Config): string | null {
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) return "Only PDF files can be reviewed.";
  if (file.size > config.max_file_mb * 1024 * 1024) return `PDFs must be ${config.max_file_mb} MB or smaller.`;
  return null;
}

export function ContractsDemo() {
  const [setup] = useState(setupClient);
  const client = setup.kind === "unconfigured" ? null : setup.client;
  const [server, setServer] = useState<Server>(
    setup.kind === "unconfigured" ? { phase: "unconfigured" } : { phase: "waking", slow: false },
  );
  const [run, setRun] = useState<Run>({ kind: "idle" });
  const waking = server.phase === "waking";

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

  const fileUrl = run.kind === "done" ? run.fileUrl : null;
  useEffect(() => () => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
  }, [fileUrl]);

  const review = async (file: File) => {
    if (!client || server.phase !== "ready" || run.kind === "reviewing") return;
    const reason = rejectReason(file, server.config);
    if (reason) {
      setRun({ kind: "failed", fileName: file.name, message: reason });
      return;
    }
    const pages = await countPdfPages(file).catch(() => null);
    setRun({ kind: "reviewing", fileName: file.name, pages, startedAt: Date.now() });
    try {
      const result = await client.reviewContract(file);
      setRun({ kind: "done", result, fileUrl: URL.createObjectURL(file) });
    } catch (err) {
      setRun({ kind: "failed", fileName: file.name, message: describeError(err) });
    }
  };

  const reviewSample = async () => {
    try {
      const response = await fetch(SAMPLE.url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      await review(new File([await response.blob()], SAMPLE.name, { type: "application/pdf" }));
    } catch {
      setRun({ kind: "failed", fileName: SAMPLE.name, message: "The sample contract couldn't be loaded. Reload the page and try again." });
    }
  };

  const ready = server.phase === "ready";

  return (
    <DemoShell>
      <main className={styles.page}>
        <div className={styles.intro}>
          <h1 className={styles.title}>Contract reviewer</h1>
          <p className={styles.lede}>
            Upload a contract and get its parties, key terms, clauses and risks in plain English. Every point cites a
            quote, and every quote is checked against the document before you see it.
            {ready && ` Reviews by ${server.config.provider_label}.`}
            {setup.kind === "mock" && " Running against the built-in mock server."}
          </p>
        </div>

        <ServerStatus server={server} onRetry={() => setServer({ phase: "waking", slow: true })} />

        {ready && run.kind !== "done" && run.kind !== "reviewing" && (
          <UploadArea config={server.config} onFile={review} onSample={reviewSample} />
        )}

        {run.kind === "failed" && (
          <div className={shared.errorBox} role="alert">
            <p>
              <strong>{run.fileName}</strong>: {run.message}
            </p>
          </div>
        )}

        {run.kind === "reviewing" && <Progress fileName={run.fileName} pages={run.pages} startedAt={run.startedAt} />}

        {run.kind === "done" && (
          <ReviewResult result={run.result} fileUrl={run.fileUrl} onReset={() => setRun({ kind: "idle" })} />
        )}
      </main>
    </DemoShell>
  );
}

function UploadArea(props: { config: Config; onFile: (file: File) => void; onSample: () => void }) {
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
          const file = e.dataTransfer.files[0];
          if (file) props.onFile(file);
        }}
      >
        <input
          type="file"
          accept="application/pdf,.pdf"
          className="visually-hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) props.onFile(file);
          }}
        />
        <span className={styles.dropzoneTitle}>Drop a contract PDF here or choose a file</span>
        <span className={styles.dropzoneLimits}>
          One PDF, up to {config.max_file_mb} MB and {config.contract_max_pages} pages. Scanned PDFs without a text
          layer won&apos;t work.
        </span>
      </label>
      <div className={styles.sampleRow}>
        <span>No contract to hand?</span>
        <button type="button" className={shared.secondaryButton} onClick={props.onSample}>
          Try a sample contract
        </button>
      </div>
    </div>
  );
}

function Progress({ fileName, pages, startedAt }: { fileName: string; pages: number | null; startedAt: number }) {
  const [now, setNow] = useState(startedAt);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, []);
  const steps = reviewSteps(pages);
  const current = currentStep(now - startedAt);

  return (
    <section className={styles.progress} aria-labelledby="progress-heading">
      <h2 id="progress-heading" className={styles.progressHeading}>
        Reviewing {fileName}
      </h2>
      <ol className={styles.steps}>
        {steps.map((step, i) => (
          <li key={step} className={styles.step} data-state={i < current ? "done" : i === current ? "current" : "todo"}>
            {step}
          </li>
        ))}
      </ol>
      <p className={styles.progressNote}>This usually takes 10 to 40 seconds.</p>
      <p className="visually-hidden" role="status">
        {steps[current]}
      </p>
    </section>
  );
}
