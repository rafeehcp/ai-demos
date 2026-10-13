import Link from "next/link";
import styles from "./page.module.css";

const UPCOMING = [
  {
    title: "Contract reviewer",
    summary: "Reads a contract, flags clauses worth a second look, and explains why.",
  },
  {
    title: "Invoice → JSON",
    summary: "Turns a PDF invoice into structured JSON your app can import.",
  },
];

export default function Home() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p className={styles.name}>Mohamed Rafeeh Ibrahim</p>
        <nav aria-label="Profiles">
          <ul className={styles.profiles}>
            <li>
              <a href="https://github.com/rafeehcp/">GitHub</a>
            </li>
            <li>
              <a href="https://www.linkedin.com/in/pomagom13/">LinkedIn</a>
            </li>
          </ul>
        </nav>
      </header>

      <main>
        <section className={styles.hero} aria-labelledby="hero-heading">
          <div className={styles.heroText}>
            <h1 id="hero-heading" className={styles.headline}>
              I add AI features to the Python and JavaScript apps you already run.
            </h1>
            <p className={styles.lede}>
              I&apos;m a senior Python and TypeScript developer. I build the AI part of a product into your existing
              backend and frontend, so it fits your data, your users, and your deployment. The demos below are small,
              working versions of that work. Try them, then read the code on GitHub.
            </p>
          </div>

          <figure className={styles.sample}>
            <p className={styles.sampleQuestion}>When can the tenant end the lease early?</p>
            <p className={styles.sampleAnswer}>
              With 60 days&apos; written notice after the first year{" "}
              <span className={styles.sampleChip}>
                lease.pdf <b>p.&nbsp;4</b>
              </span>
              . An early-exit fee of one month&apos;s rent applies{" "}
              <span className={styles.sampleChip}>
                lease.pdf <b>p.&nbsp;5</b>
              </span>
              .
            </p>
            <figcaption className={styles.sampleCaption}>
              Sample answer from Chat with your docs. Each source opens its page in your PDF.
            </figcaption>
          </figure>
        </section>

        <section className={styles.demos} aria-labelledby="demos-heading">
          <h2 id="demos-heading" className={styles.sectionHeading}>
            Demos
          </h2>
          <ul className={styles.demoList}>
            <li className={`${styles.demo} ${styles.demoLive}`}>
              <h3 className={styles.demoTitle}>
                <Link href="/chat" className={styles.demoLink}>
                  Chat with your docs
                </Link>
              </h3>
              <p className={styles.demoSummary}>
                Upload a PDF and ask questions about it. Every answer cites the page it came from, and one click opens
                that page.
              </p>
              <p className={styles.demoAction} aria-hidden="true">
                Try it now
              </p>
            </li>
            {UPCOMING.map((demo) => (
              <li key={demo.title} className={styles.demo}>
                <h3 className={styles.demoTitle}>{demo.title}</h3>
                <p className={styles.demoSummary}>{demo.summary}</p>
                <p className={styles.soon}>Coming soon</p>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className={styles.footer}>
        <p>
          Want something like this in your app? Reach me on{" "}
          <a href="https://www.linkedin.com/in/pomagom13/">LinkedIn</a>.
        </p>
      </footer>
    </div>
  );
}
