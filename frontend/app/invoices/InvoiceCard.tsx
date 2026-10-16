import Image from "next/image";
import shared from "@/app/components/shared.module.css";
import type { Check, Invoice, Party } from "@/lib/api";
import { CHECK_LABELS, DOCUMENT_LABELS, formatAmount, formatMoney, STATUS_LABELS, type Card } from "@/lib/invoices";
import styles from "./invoices.module.css";

const STATUS_MARKS: Record<Check["status"], string> = { pass: "✓", fail: "✕", skipped: "–" };

export function InvoiceCard({ card, onRetry }: { card: Card; onRetry: () => void }) {
  const { status } = card;
  return (
    <li className={styles.card} data-state={status.state}>
      <div className={styles.cardHead}>
        <Thumbnail card={card} />
        <div className={styles.cardTitle}>
          {status.state === "done" ? (
            <Summary invoice={status.result.invoice} fileName={card.name} />
          ) : (
            <>
              <p className={styles.fileName}>{card.name}</p>
              {status.state === "queued" && <p className={styles.stateText}>Waiting for its turn</p>}
              {status.state === "extracting" && (
                <>
                  <p className={styles.stateText} role="status">
                    Reading the document and checking the numbers
                  </p>
                  <div className={shared.wakingBar} aria-hidden="true" />
                </>
              )}
              {status.state === "failed" && (
                <div className={styles.failure} role="alert">
                  <p>{status.message}</p>
                  {status.retryable && (
                    <button type="button" className={shared.secondaryButton} onClick={onRetry}>
                      Try again
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </div>
        {status.state === "done" && status.result.invoice.total !== null && (
          <p className={styles.total}>
            <span className={styles.totalLabel}>Total</span>
            <span className={styles.totalValue}>{formatMoney(status.result.invoice.total, status.result.invoice.currency)}</span>
          </p>
        )}
      </div>
      {status.state === "done" && <Details invoice={status.result.invoice} />}
    </li>
  );
}

function Thumbnail({ card }: { card: Card }) {
  const label = card.kind === "image" ? null : card.kind === "pdf" ? "PDF" : "File";
  return (
    <a className={styles.thumb} href={card.url} target="_blank" rel="noopener noreferrer">
      {card.kind === "image" ? (
        <Image src={card.url} alt="" width={64} height={84} unoptimized className={styles.thumbImage} />
      ) : (
        <span className={styles.thumbTile} aria-hidden="true">
          {label}
        </span>
      )}
      <span className="visually-hidden">Open {card.name} in a new tab</span>
    </a>
  );
}

function Summary({ invoice, fileName }: { invoice: Invoice; fileName: string }) {
  const meta = [
    invoice.invoice_number && `No. ${invoice.invoice_number}`,
    invoice.issue_date && `Issued ${invoice.issue_date}`,
    invoice.due_date && `Due ${invoice.due_date}`,
  ].filter(Boolean);
  return (
    <>
      <p className={styles.kicker}>
        {DOCUMENT_LABELS[invoice.document_type]} · <span className={styles.kickerFile}>{fileName}</span>
      </p>
      <h3 className={styles.vendor}>{invoice.vendor?.name ?? "Vendor not shown"}</h3>
      {meta.length > 0 && <p className={styles.meta}>{meta.join(" · ")}</p>}
    </>
  );
}

function Details({ invoice }: { invoice: Invoice }) {
  const failed = invoice.checks.filter((c) => c.status === "fail");
  return (
    <div className={styles.details}>
      <div className={styles.checksBlock}>
        <h4 className="visually-hidden">Checks</h4>
        <ul className={styles.checks}>
          {invoice.checks.map((check) => (
            <li key={check.name} className={styles.check} data-status={check.status}>
              <span aria-hidden="true" className={styles.checkMark}>
                {STATUS_MARKS[check.status]}
              </span>
              {CHECK_LABELS[check.name]}
              <span className={styles.checkStatus}>{STATUS_LABELS[check.status]}</span>
            </li>
          ))}
        </ul>
        {failed.length > 0 && (
          <ul className={styles.failedChecks}>
            {failed.map((check) => (
              <li key={check.name}>
                <strong>{CHECK_LABELS[check.name]}:</strong> {check.detail}
              </li>
            ))}
          </ul>
        )}
        <details className={styles.checkDetails}>
          <summary>What each check found</summary>
          <dl>
            {invoice.checks.map((check) => (
              <div key={check.name}>
                <dt>{CHECK_LABELS[check.name]}</dt>
                <dd>{check.detail}</dd>
              </div>
            ))}
          </dl>
        </details>
      </div>

      {(invoice.vendor || invoice.customer) && (
        <dl className={styles.parties}>
          {invoice.vendor && <PartyBlock label="From" party={invoice.vendor} />}
          {invoice.customer && <PartyBlock label="Billed to" party={invoice.customer} />}
        </dl>
      )}

      {invoice.line_items.length > 0 ? (
        <div className={styles.tableWrap}>
          <table className={styles.lines}>
            <thead>
              <tr>
                <th scope="col">Description</th>
                <th scope="col">Qty</th>
                <th scope="col">Price</th>
                <th scope="col">Amount</th>
              </tr>
            </thead>
            <tbody>
              {invoice.line_items.map((line, i) => (
                <tr key={i}>
                  <td>{line.description}</td>
                  <td>{line.quantity ?? ""}</td>
                  <td>{line.unit_price ? formatAmount(line.unit_price) : ""}</td>
                  <td>{formatAmount(line.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className={styles.none}>No line items found.</p>
      )}

      <dl className={styles.totals}>
        {invoice.subtotal !== null && <TotalRow label="Subtotal" value={formatAmount(invoice.subtotal)} />}
        {invoice.discount !== null && <TotalRow label="Discount" value={formatAmount(invoice.discount)} />}
        {invoice.taxes.map((tax, i) => (
          <TotalRow key={i} label={tax.rate_percent ? `${tax.label} ${tax.rate_percent}%` : tax.label} value={formatAmount(tax.amount)} />
        ))}
        {invoice.total !== null && (
          <TotalRow label={invoice.currency ? `Total (${invoice.currency})` : "Total"} value={formatAmount(invoice.total)} strong />
        )}
      </dl>
    </div>
  );
}

function PartyBlock({ label, party }: { label: string; party: Party }) {
  return (
    <div className={styles.party}>
      <dt>{label}</dt>
      <dd>
        <span className={styles.partyName}>{party.name}</span>
        {[party.address, party.tax_id && `Tax ID ${party.tax_id}`, party.email].filter(Boolean).map((line) => (
          <span key={line} className={styles.partyLine}>
            {line}
          </span>
        ))}
      </dd>
    </div>
  );
}

function TotalRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={styles.totalRow} data-strong={strong || undefined}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
