"use client";

import Link from "next/link";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { ApiError, type Config } from "@/lib/api";
import { setupClient } from "@/lib/client";
import { DocumentPanel } from "./DocumentPanel";
import { Thread } from "./Thread";
import { initialState, occupiesSlot, readyDocuments, reducer } from "./state";
import styles from "./chat.module.css";

const WAKE_DEADLINE_MS = 120_000;
const SLOW_AFTER_MS = 1_500;
const MAX_QUESTION = 1_000;

const STARTERS = [
  "Summarize the main points.",
  "What dates or deadlines does it mention?",
  "What does it say about costs or payment?",
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function describe(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "rate_limited" && err.retryAfter !== null) {
      const s = err.retryAfter;
      return `${err.message} Try again in ${s} second${s === 1 ? "" : "s"}.`;
    }
    return err.message;
  }
  return "Something went wrong in the page. Reload it and try again.";
}

const isSessionGone = (err: unknown) => err instanceof ApiError && err.code === "session_not_found";

function rejectReason(file: File, config: Config): string | null {
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) return "Only PDF files can be uploaded.";
  if (file.size > config.max_file_mb * 1024 * 1024) return `PDFs must be ${config.max_file_mb} MB or smaller.`;
  return null;
}

let keySeq = 0;
const nextKey = () => `k${++keySeq}`;

export function ChatDemo() {
  const [setup] = useState(setupClient);
  const [state, dispatch] = useReducer(
    reducer,
    setup,
    (s) => initialState(s.kind === "unconfigured" ? { phase: "unconfigured" } : { phase: "waking", slow: false }),
  );
  const [question, setQuestion] = useState("");
  const sessionRef = useRef<string | null>(null);
  const resetRef = useRef<Promise<void> | null>(null);
  const client = setup.kind === "unconfigured" ? null : setup.client;
  const { server } = state;
  const waking = server.phase === "waking";

  useEffect(() => {
    if (!client || !waking) return;
    let cancelled = false;
    const slowTimer = setTimeout(() => dispatch({ type: "wakingSlow" }), SLOW_AFTER_MS);
    (async () => {
      const deadline = Date.now() + WAKE_DEADLINE_MS;
      // A sleeping free-tier host can drop or stall the first requests; keep knocking.
      for (;;) {
        try {
          await client.health(60_000);
          break;
        } catch (err) {
          if (cancelled) return;
          if (Date.now() > deadline) throw err;
          await sleep(3_000);
        }
      }
      const [config, sessionId] = await Promise.all([client.config(), client.createSession()]);
      if (cancelled) return;
      sessionRef.current = sessionId;
      dispatch({ type: "ready", sessionId, config });
    })()
      .catch((err) => {
        if (!cancelled) dispatch({ type: "bootFailed", message: describe(err) });
      })
      .finally(() => clearTimeout(slowTimer));
    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, [client, waking]);

  const fileUrlsRef = useRef(state.fileUrls);
  useEffect(() => {
    fileUrlsRef.current = state.fileUrls;
  }, [state.fileUrls]);
  useEffect(() => () => Object.values(fileUrlsRef.current).forEach((url) => URL.revokeObjectURL(url)), []);

  /** Replaces an expired session once, however many in-flight calls notice it. */
  const resetSession = useCallback(
    (expiredId: string): Promise<void> => {
      if (!client) return Promise.resolve();
      if (sessionRef.current !== expiredId) return resetRef.current ?? Promise.resolve();
      resetRef.current = client
        .createSession()
        .then((sessionId) => {
          sessionRef.current = sessionId;
          dispatch({ type: "sessionReset", sessionId });
        })
        .catch((err) => dispatch({ type: "bootFailed", message: describe(err) }));
      return resetRef.current;
    },
    [client],
  );

  const uploadOne = useCallback(
    async (key: string, file: File) => {
      const sessionId = sessionRef.current;
      if (!client || !sessionId) return;
      dispatch({ type: "uploadProgress", key, progress: 0 });
      try {
        const doc = await client.uploadDocument(sessionId, file, (progress) =>
          dispatch({ type: "uploadProgress", key, progress }),
        );
        dispatch({ type: "uploadDone", key, doc, url: URL.createObjectURL(file) });
      } catch (err) {
        if (isSessionGone(err)) await resetSession(sessionId);
        else dispatch({ type: "uploadFailed", key, message: describe(err) });
      }
    },
    [client, resetSession],
  );

  const addFiles = async (entries: { key: string; file: File }[]) => {
    if (server.phase !== "ready") return;
    let free = server.config.max_documents - state.uploads.filter(occupiesSlot).length;
    const accepted: typeof entries = [];
    for (const { key, file } of entries) {
      const reason =
        rejectReason(file, server.config) ??
        (free > 0 ? null : `You can upload up to ${server.config.max_documents} documents. Remove one to add another.`);
      if (reason) {
        dispatch({ type: "uploadRejected", key: nextKey(), file, message: reason });
        continue;
      }
      free--;
      accepted.push({ key, file });
      dispatch({ type: "uploadQueued", key, file });
    }
    // One at a time: the free-tier backend has 512 MB and embeds each upload in memory.
    for (const { key, file } of accepted) await uploadOne(key, file);
  };

  const remove = async (key: string) => {
    const upload = state.uploads.find((u) => u.key === key);
    const sessionId = sessionRef.current;
    if (!upload || !client || !sessionId) return;
    if (upload.status.kind !== "ready") {
      dispatch({ type: "removed", key });
      return;
    }
    dispatch({ type: "removeStarted", key });
    try {
      await client.deleteDocument(sessionId, upload.status.doc.id);
      dispatch({ type: "removed", key });
    } catch (err) {
      if (isSessionGone(err)) {
        await resetSession(sessionId);
        dispatch({ type: "removed", key });
      } else {
        dispatch({ type: "removeFailed", key, message: describe(err) });
      }
    }
  };

  const ask = async (raw: string) => {
    const text = raw.trim();
    const sessionId = sessionRef.current;
    if (!text || !client || !sessionId) return;
    const id = nextKey();
    setQuestion("");
    dispatch({ type: "asked", id, question: text });
    try {
      const response = await client.ask(sessionId, text);
      dispatch({ type: "answered", id, response });
    } catch (err) {
      if (isSessionGone(err)) {
        dispatch({
          type: "askFailed",
          id,
          message: "Your session expired, so the server no longer has your documents. Upload them again, then ask again.",
        });
        await resetSession(sessionId);
      } else {
        dispatch({ type: "askFailed", id, message: describe(err) });
      }
    }
  };

  const docs = readyDocuments(state);
  const pending = state.turns.some((t) => t.status.kind === "pending");
  const canType = server.phase === "ready" && docs.length > 0;
  const canAsk = canType && !pending;
  const askHint =
    server.phase !== "ready"
      ? "The question box opens once the server is ready."
      : docs.length === 0
        ? "Upload a PDF to start asking."
        : pending
          ? "Working on your last question."
          : null;

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

      <div className={styles.layout}>
        <div className={styles.intro}>
          <h1 className={styles.title}>Chat with your docs</h1>
          <p className={styles.lede}>
            Upload up to {server.phase === "ready" ? server.config.max_documents : 3} PDFs and ask about them. Each
            answer cites the page it came from.
            {server.phase === "ready" && ` Answers by ${server.config.provider_label}.`}
            {setup.kind === "mock" && " Running against the built-in mock server."}
          </p>
        </div>

        <DocumentPanel
          server={server}
          uploads={state.uploads}
          sessionExpired={state.sessionExpired}
          panelError={state.panelError}
          onFiles={(files) => addFiles(files.map((file) => ({ key: nextKey(), file })))}
          onReupload={(entries) => addFiles(entries)}
          onRemove={remove}
          onRetryBoot={() => dispatch({ type: "retryBoot" })}
        />

        <section className={styles.conversation} aria-labelledby="conversation-heading">
          <h2 id="conversation-heading" className="visually-hidden">
            Conversation
          </h2>
          <Thread turns={state.turns} fileUrls={state.fileUrls} />

          {docs.length > 0 && state.turns.length === 0 && (
            <div className={styles.starters}>
              <p id="starters-label" className={styles.startersLabel}>
                Try one of these
              </p>
              <ul aria-labelledby="starters-label">
                {STARTERS.map((s) => (
                  <li key={s}>
                    <button type="button" className={styles.starter} disabled={!canAsk} onClick={() => ask(s)}>
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <form
            className={styles.composer}
            onSubmit={(e) => {
              e.preventDefault();
              if (canAsk) ask(question);
            }}
          >
            <label htmlFor="question" className={styles.composerLabel}>
              Ask about your documents
            </label>
            <div className={styles.composerRow}>
              <textarea
                id="question"
                className={styles.textarea}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    if (canAsk) ask(question);
                  }
                }}
                maxLength={MAX_QUESTION}
                rows={2}
                disabled={!canType}
                aria-describedby={askHint ? "ask-hint" : undefined}
                placeholder={canType ? "When can the tenant end the lease early?" : undefined}
              />
              <button type="submit" className={styles.askButton} disabled={!canAsk || question.trim() === ""}>
                Ask
              </button>
            </div>
            {askHint && (
              <p id="ask-hint" className={styles.hint}>
                {askHint}
              </p>
            )}
          </form>
        </section>
      </div>
    </div>
  );
}
