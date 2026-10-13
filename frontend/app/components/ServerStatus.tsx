import type { BootPhase } from "@/lib/wake";
import styles from "./shared.module.css";

export function ServerStatus({ server, onRetry }: { server: BootPhase; onRetry: () => void }) {
  switch (server.phase) {
    case "waking":
      return (
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
      );
    case "failed":
      return (
        <div className={styles.errorBox} role="alert">
          <p>{server.message}</p>
          <button type="button" className={styles.secondaryButton} onClick={onRetry}>
            Try again
          </button>
        </div>
      );
    case "unconfigured":
      return (
        <div className={styles.errorBox} role="alert">
          <p>This deployment has no API address. Set NEXT_PUBLIC_API_URL and rebuild.</p>
        </div>
      );
    default:
      return null;
  }
}
