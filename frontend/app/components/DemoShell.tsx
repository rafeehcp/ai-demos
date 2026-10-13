import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./shared.module.css";

export function DemoShell({ children }: { children: ReactNode }) {
  return (
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Link href="/" className={styles.back}>
            All demos
          </Link>
          <p className={styles.notice} role="note">
            Demo only. Don&apos;t upload real or confidential documents.
          </p>
        </div>
      </header>
      {children}
    </div>
  );
}
