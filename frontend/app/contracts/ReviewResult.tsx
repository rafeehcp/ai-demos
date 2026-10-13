"use client";

import { useId, useState, type ReactNode } from "react";
import shared from "@/app/components/shared.module.css";
import type { ContractReview, Evidence as EvidenceData, ReviewResponse } from "@/lib/api";
import { exportFileName, exportJson, groupClauses, SEVERITY_LABELS } from "@/lib/review";
import styles from "./contracts.module.css";

type Props = { result: ReviewResponse; fileUrl: string; onReset: () => void };

function download(result: ReviewResponse) {
  const url = URL.createObjectURL(new Blob([exportJson(result)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = exportFileName(result.document_name);
  a.click();
  URL.revokeObjectURL(url);
}

export function ReviewResult({ result, fileUrl, onReset }: Props) {
  const { review } = result;
  const unverified = [...review.key_terms, ...review.clauses, ...review.risks].filter((i) => !i.evidence.verified).length;

  return (
    <article className={styles.result} aria-labelledby="result-heading">
      <header className={styles.resultHeader}>
        <div>
          <p className={styles.kicker}>{review.contract_type}</p>
          <h2 id="result-heading" className={styles.resultTitle}>
            {result.document_name}
          </h2>
          <p className={styles.meta}>
            {result.pages} {result.pages === 1 ? "page" : "pages"}
            {unverified > 0 && ` · ${unverified} ${unverified === 1 ? "quote" : "quotes"} not found in the document`}
          </p>
        </div>
        <div className={styles.actions}>
          <button type="button" className={shared.secondaryButton} onClick={() => download(result)}>
            Download JSON
          </button>
          <button type="button" className={styles.linkButton} onClick={onReset}>
            Review another contract
          </button>
        </div>
      </header>

      <p className={styles.disclaimer} role="note">
        Not legal advice. An AI model wrote this review, so check anything that matters against the contract itself.
      </p>

      <section className={styles.block} aria-labelledby="summary-heading">
        <h3 id="summary-heading" className={styles.blockHeading}>
          Summary
        </h3>
        <p className={styles.summary}>{review.summary}</p>
        {review.parties.length > 0 && (
          <dl className={styles.parties}>
            {review.parties.map((p) => (
              <div key={`${p.role}-${p.name}`} className={styles.party}>
                <dt>{p.role}</dt>
                <dd>{p.name}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      {review.key_terms.length > 0 && (
        <section className={styles.block} aria-labelledby="terms-heading">
          <h3 id="terms-heading" className={styles.blockHeading}>
            Key terms
          </h3>
          <table className={styles.terms}>
            <thead>
              <tr>
                <th scope="col">Term</th>
                <th scope="col">Value</th>
                <th scope="col">
                  <span className="visually-hidden">Source</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {review.key_terms.map((term, i) => (
                <KeyTermRows key={i} term={term} fileUrl={fileUrl} />
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className={styles.block} aria-labelledby="risks-heading">
        <h3 id="risks-heading" className={styles.blockHeading}>
          Risks
        </h3>
        {review.risks.length === 0 ? (
          <p className={styles.none}>The review found no risks worth flagging.</p>
        ) : (
          <ul className={styles.items}>
            {review.risks.map((risk, i) => (
              <Item
                key={i}
                title={risk.title}
                headingLevel={4}
                body={risk.explanation}
                evidence={risk.evidence}
                fileUrl={fileUrl}
                badge={
                  <span className={styles.severity} data-severity={risk.severity}>
                    {SEVERITY_LABELS[risk.severity]}
                  </span>
                }
              />
            ))}
          </ul>
        )}
      </section>

      {review.clauses.length > 0 && (
        <section className={styles.block} aria-labelledby="clauses-heading">
          <h3 id="clauses-heading" className={styles.blockHeading}>
            Clauses
          </h3>
          {groupClauses(review.clauses).map((group) => (
            <div key={group.kind} className={styles.group}>
              <h4 className={styles.groupHeading}>{group.label}</h4>
              <ul className={styles.items}>
                {group.clauses.map((clause, i) => (
                  <Item
                    key={i}
                    title={clause.title}
                    headingLevel={5}
                    body={clause.plain_english}
                    evidence={clause.evidence}
                    fileUrl={fileUrl}
                  />
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}
    </article>
  );
}

function KeyTermRows({ term, fileUrl }: { term: ContractReview["key_terms"][number]; fileUrl: string }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <>
      <tr>
        <th scope="row">{term.label}</th>
        <td>{term.value}</td>
        <td className={styles.sourceCell}>
          <EvidenceChip evidence={term.evidence} expanded={open} controls={panelId} onToggle={() => setOpen(!open)} />
        </td>
      </tr>
      {open && (
        <tr className={styles.panelRow}>
          <td colSpan={3}>
            <EvidencePanel id={panelId} evidence={term.evidence} fileUrl={fileUrl} />
          </td>
        </tr>
      )}
    </>
  );
}

type ItemProps = {
  title: string;
  headingLevel: 4 | 5;
  body: string;
  evidence: EvidenceData;
  fileUrl: string;
  badge?: ReactNode;
};

function Item(props: ItemProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const Heading = props.headingLevel === 4 ? "h4" : "h5";
  return (
    <li className={styles.item}>
      <div className={styles.itemHead}>
        {props.badge}
        <Heading className={styles.itemTitle}>{props.title}</Heading>
        <EvidenceChip evidence={props.evidence} expanded={open} controls={panelId} onToggle={() => setOpen(!open)} />
      </div>
      <p className={styles.itemBody}>{props.body}</p>
      {open && <EvidencePanel id={panelId} evidence={props.evidence} fileUrl={props.fileUrl} />}
    </li>
  );
}

function EvidenceChip(props: { evidence: EvidenceData; expanded: boolean; controls: string; onToggle: () => void }) {
  const { evidence } = props;
  return (
    <button
      type="button"
      className={styles.chip}
      data-verified={evidence.verified}
      aria-expanded={props.expanded}
      aria-controls={props.expanded ? props.controls : undefined}
      aria-label={evidence.verified ? `Quote from page ${evidence.page}` : "Quote not verified"}
      onClick={props.onToggle}
    >
      {evidence.verified ? <>p.&nbsp;{evidence.page}</> : "Unverified"}
    </button>
  );
}

function EvidencePanel({ id, evidence, fileUrl }: { id: string; evidence: EvidenceData; fileUrl: string }) {
  if (!evidence.verified) {
    return (
      <div id={id} className={styles.unverified}>
        <p className={styles.unverifiedTitle}>Quote not found in document</p>
        <p>The model&apos;s quote for this point isn&apos;t in the contract text, so it isn&apos;t shown. Check this point yourself.</p>
      </div>
    );
  }
  return (
    <figure id={id} className={styles.source}>
      <blockquote className={styles.quote}>
        <p>
          <mark>{evidence.quote}</mark>
        </p>
      </blockquote>
      <figcaption className={styles.sourceCaption}>
        <span>Page {evidence.page}</span>
        <a className={styles.openPage} href={`${fileUrl}#page=${evidence.page}`} target="_blank" rel="noopener noreferrer">
          Open page {evidence.page}
          <span className="visually-hidden"> of the contract in a new tab</span>
        </a>
      </figcaption>
    </figure>
  );
}
