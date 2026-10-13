"use client";

import { useState } from "react";
import type { Server, Upload, UploadStatus } from "./state";
import styles from "./chat.module.css";

type Props = {
  server: Server;
  uploads: Upload[];
  sessionExpired: boolean;
  panelError: string | null;
  onFiles: (files: File[]) => void;
  onReupload: (entries: { key: string; file: File }[]) => void;
  onRemove: (key: string) => void;
  onRetryBoot: () => void;
};

function statusText(status: UploadStatus): string {
  switch (status.kind) {
    case "queued":
      return "Waiting to upload";
    case "uploading":
      return `Uploading ${Math.round(status.progress * 100)}%`;
    case "processing":
      return "Reading and indexing";
    case "ready":
      return `${status.doc.pages} ${status.doc.pages === 1 ? "page" : "pages"}`;
    case "removing":
      return "Removing";
    case "failed":
      return status.message;
    case "stale":
      return "Needs uploading again";
  }
}

const busy = (s: UploadStatus) => s.kind === "queued" || s.kind === "uploading" || s.kind === "processing";

export function DocumentPanel(props: Props) {
  const { server, uploads, sessionExpired, panelError } = props;
  const [dragging, setDragging] = useState(false);
  const ready = server.phase === "ready";
  const stale = uploads.filter((u) => u.status.kind === "stale");

  return (
    <section className={styles.panel} aria-labelledby="documents-heading">
      <h2 id="documents-heading" className={styles.panelHeading}>
        Documents
      </h2>

      {server.phase === "waking" && (
        <div className={styles.waking} role="status">
          {server.slow ? (
            <>
              <p className={styles.wakingTitle}>Waking up the server</p>
              <p>It runs on free hosting that sleeps when idle, so this can take about 30 seconds.</p>
              <div className={styles.wakingBar} aria-hidden="true" />
            </>
          ) : (
            <p>Connecting to the server</p>
          )}
        </div>
      )}

      {server.phase === "failed" && (
        <div className={styles.errorBox} role="alert">
          <p>{server.message}</p>
          <button type="button" className={styles.secondaryButton} onClick={props.onRetryBoot}>
            Try again
          </button>
        </div>
      )}

      {server.phase === "unconfigured" && (
        <div className={styles.errorBox} role="alert">
          <p>This deployment has no API address. Set NEXT_PUBLIC_API_URL and rebuild.</p>
        </div>
      )}

      {ready && (
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
            accept="application/pdf,.pdf"
            multiple
            className="visually-hidden"
            onChange={(e) => {
              props.onFiles(Array.from(e.target.files ?? []));
              e.target.value = "";
            }}
          />
          <span className={styles.dropzoneTitle}>Drop PDFs here or choose files</span>
          <span className={styles.dropzoneLimits}>
            Up to {server.config.max_documents} files, {server.config.max_file_mb} MB and {server.config.max_pages} pages
            each. Scanned PDFs without a text layer won&apos;t work.
          </span>
        </label>
      )}

      <div aria-live="polite" className={styles.panelMessages}>
        {sessionExpired && stale.length > 0 && (
          <div className={styles.expired}>
            <p>Your session expired, so the server no longer has your documents. Upload them again to keep asking.</p>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => props.onReupload(stale.map(({ key, file }) => ({ key, file })))}
            >
              Upload {stale.length === 1 ? "it" : "them"} again
            </button>
          </div>
        )}
        {panelError && (
          <p className={styles.rowError} role="alert">
            {panelError}
          </p>
        )}
      </div>

      {uploads.length > 0 && (
        <ul className={styles.docList}>
          {uploads.map(({ key, file, status }) => (
            <li key={key} className={styles.doc} data-status={status.kind}>
              <span className={styles.docIcon} aria-hidden="true">
                PDF
              </span>
              <div className={styles.docBody}>
                <span className={styles.docName} title={file.name}>
                  {file.name}
                </span>
                <span className={styles.docStatus} role={status.kind === "failed" ? "alert" : undefined}>
                  {statusText(status)}
                </span>
                {(status.kind === "uploading" || status.kind === "processing") && (
                  <progress
                    className={styles.progress}
                    aria-label={`${file.name} progress`}
                    max={1}
                    value={status.kind === "uploading" ? status.progress : undefined}
                  />
                )}
              </div>
              {!busy(status) && (
                <button
                  type="button"
                  className={styles.removeButton}
                  aria-label={`Remove ${file.name}`}
                  disabled={status.kind === "removing"}
                  onClick={() => props.onRemove(key)}
                >
                  <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
                    <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                  </svg>
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
