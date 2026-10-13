"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { AskResponse, Citation } from "@/lib/api";
import { parseAnswer } from "@/lib/citations";
import type { Turn } from "./state";
import styles from "./chat.module.css";

type Props = { turns: Turn[]; fileUrls: Record<string, string> };

export function Thread({ turns, fileUrls }: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const last = turns.at(-1);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [turns.length, last?.status.kind]);

  if (turns.length === 0) {
    return (
      <p className={styles.empty}>
        Answers appear here with their sources. Select a source to read the quoted passage and open its page.
      </p>
    );
  }

  return (
    <>
      <ol className={styles.thread}>
        {turns.map((turn) => (
          <li key={turn.id} className={styles.turn}>
            <p className={styles.question}>{turn.question}</p>
            {turn.status.kind === "pending" && (
              <p className={styles.thinking} role="status">
                Reading your documents
              </p>
            )}
            {turn.status.kind === "failed" && (
              <p className={styles.turnError}>{turn.status.message}</p>
            )}
            {turn.status.kind === "answered" && <Answer response={turn.status.response} fileUrls={fileUrls} />}
          </li>
        ))}
      </ol>
      <div ref={endRef} />
      <p className="visually-hidden" aria-live="polite">
        {last?.status.kind === "answered" && `Answer: ${last.status.response.answer}`}
        {last?.status.kind === "failed" && `Error: ${last.status.message}`}
      </p>
    </>
  );
}

function Answer({ response, fileUrls }: { response: AskResponse; fileUrls: Record<string, string> }) {
  const [open, setOpen] = useState<number | null>(null);
  const panelId = useId();
  const segments = parseAnswer(response.answer, response.citations);
  const openCitation = response.citations.find((c) => c.n === open);

  return (
    <div className={styles.answer}>
      <p className={styles.answerText}>
        {segments.map((seg, i) =>
          seg.kind === "text" ? (
            <span key={i}>{seg.text}</span>
          ) : (
            <Chip
              key={i}
              citation={seg.citation}
              expanded={open === seg.citation.n}
              controls={panelId}
              onToggle={() => setOpen(open === seg.citation.n ? null : seg.citation.n)}
            />
          ),
        )}
      </p>
      {openCitation && <Source id={panelId} citation={openCitation} url={fileUrls[openCitation.document_id]} />}
    </div>
  );
}

function Chip(props: { citation: Citation; expanded: boolean; controls: string; onToggle: () => void }) {
  const { citation } = props;
  return (
    <button
      type="button"
      className={styles.chip}
      aria-expanded={props.expanded}
      aria-controls={props.expanded ? props.controls : undefined}
      aria-label={`Source ${citation.n}: ${citation.document_name}, page ${citation.page}`}
      onClick={props.onToggle}
    >
      <span className={styles.chipDoc}>{citation.document_name}</span>
      <span className={styles.chipPage}>p.&nbsp;{citation.page}</span>
    </button>
  );
}

function Source({ id, citation, url }: { id: string; citation: Citation; url: string | undefined }) {
  return (
    <figure id={id} className={styles.source}>
      <blockquote className={styles.quote}>
        <p>
          <mark>{citation.quote}</mark>
        </p>
      </blockquote>
      <figcaption className={styles.sourceCaption}>
        <span>
          {citation.document_name}, page {citation.page}
        </span>
        {url && (
          <a className={styles.openPage} href={`${url}#page=${citation.page}`} target="_blank" rel="noopener noreferrer">
            Open page {citation.page}
            <span className="visually-hidden"> of {citation.document_name} in a new tab</span>
          </a>
        )}
      </figcaption>
    </figure>
  );
}
