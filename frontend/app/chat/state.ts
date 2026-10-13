import type { AskResponse, Config, DocumentInfo } from "@/lib/api";

export type Server =
  | { phase: "waking"; slow: boolean }
  | { phase: "ready"; sessionId: string; config: Config }
  | { phase: "failed"; message: string }
  | { phase: "unconfigured" };

export type UploadStatus =
  | { kind: "queued" }
  | { kind: "uploading"; progress: number }
  | { kind: "processing" }
  | { kind: "ready"; doc: DocumentInfo }
  | { kind: "removing"; doc: DocumentInfo }
  | { kind: "failed"; message: string }
  /** The server lost this document when its session expired; the File is still here. */
  | { kind: "stale" };

export type Upload = { key: string; file: File; status: UploadStatus };

export type TurnStatus =
  | { kind: "pending" }
  | { kind: "answered"; response: AskResponse }
  | { kind: "failed"; message: string };

export type Turn = { id: string; question: string; status: TurnStatus };

export type State = {
  server: Server;
  uploads: Upload[];
  /**
   * Object URLs for uploaded files by document id. Never pruned while the page
   * is open, so citations in earlier answers can still open their page after
   * the document is removed or the session resets.
   */
  fileUrls: Record<string, string>;
  turns: Turn[];
  /** Shown after a silent session reset until the user re-uploads. */
  sessionExpired: boolean;
  /** An error about the document list that belongs to no single row. */
  panelError: string | null;
};

export type Action =
  | { type: "wakingSlow" }
  | { type: "ready"; sessionId: string; config: Config }
  | { type: "bootFailed"; message: string }
  | { type: "retryBoot" }
  | { type: "sessionReset"; sessionId: string }
  | { type: "uploadQueued"; key: string; file: File }
  | { type: "uploadRejected"; key: string; file: File; message: string }
  | { type: "uploadProgress"; key: string; progress: number }
  | { type: "uploadDone"; key: string; doc: DocumentInfo; url: string }
  | { type: "uploadFailed"; key: string; message: string }
  | { type: "removeStarted"; key: string }
  | { type: "removeFailed"; key: string; message: string }
  | { type: "removed"; key: string }
  | { type: "asked"; id: string; question: string }
  | { type: "answered"; id: string; response: AskResponse }
  | { type: "askFailed"; id: string; message: string };

export function initialState(server: Server): State {
  return { server, uploads: [], fileUrls: {}, turns: [], sessionExpired: false, panelError: null };
}

function setUpload(state: State, key: string, status: UploadStatus): State {
  return { ...state, uploads: state.uploads.map((u) => (u.key === key ? { ...u, status } : u)) };
}

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "wakingSlow":
      return state.server.phase === "waking" ? { ...state, server: { phase: "waking", slow: true } } : state;
    case "ready":
      return { ...state, server: { phase: "ready", sessionId: action.sessionId, config: action.config } };
    case "bootFailed":
      return { ...state, server: { phase: "failed", message: action.message } };
    case "retryBoot":
      return { ...state, server: { phase: "waking", slow: true } };
    case "sessionReset": {
      if (state.server.phase !== "ready") return state;
      // Anything the old session held is gone; failed rows keep their own message.
      const uploads = state.uploads.map((u): Upload =>
        u.status.kind === "failed" ? u : { ...u, status: { kind: "stale" } },
      );
      return {
        ...state,
        server: { ...state.server, sessionId: action.sessionId },
        uploads,
        sessionExpired: true,
      };
    }
    case "uploadQueued":
      return {
        ...state,
        sessionExpired: false,
        panelError: null,
        uploads: [
          ...state.uploads.filter((u) => u.key !== action.key),
          { key: action.key, file: action.file, status: { kind: "queued" } },
        ],
      };
    case "uploadRejected":
      return {
        ...state,
        uploads: [...state.uploads, { key: action.key, file: action.file, status: { kind: "failed", message: action.message } }],
      };
    case "uploadProgress":
      return setUpload(
        state,
        action.key,
        action.progress >= 1 ? { kind: "processing" } : { kind: "uploading", progress: action.progress },
      );
    case "uploadDone":
      return {
        ...setUpload(state, action.key, { kind: "ready", doc: action.doc }),
        fileUrls: { ...state.fileUrls, [action.doc.id]: action.url },
      };
    case "uploadFailed":
      return setUpload(state, action.key, { kind: "failed", message: action.message });
    case "removeStarted": {
      const upload = state.uploads.find((u) => u.key === action.key);
      if (upload?.status.kind !== "ready") return state;
      return { ...setUpload(state, action.key, { kind: "removing", doc: upload.status.doc }), panelError: null };
    }
    case "removeFailed": {
      const upload = state.uploads.find((u) => u.key === action.key);
      if (upload?.status.kind !== "removing") return state;
      return { ...setUpload(state, action.key, { kind: "ready", doc: upload.status.doc }), panelError: action.message };
    }
    case "removed":
      return { ...state, uploads: state.uploads.filter((u) => u.key !== action.key) };
    case "asked":
      return { ...state, turns: [...state.turns, { id: action.id, question: action.question, status: { kind: "pending" } }] };
    case "answered":
    case "askFailed": {
      const status: TurnStatus =
        action.type === "answered"
          ? { kind: "answered", response: action.response }
          : { kind: "failed", message: action.message };
      return { ...state, turns: state.turns.map((t) => (t.id === action.id ? { ...t, status } : t)) };
    }
  }
}

/** Uploads that occupy one of the session's document slots. */
export function occupiesSlot(u: Upload): boolean {
  return u.status.kind !== "failed" && u.status.kind !== "stale";
}

export function readyDocuments(state: State): DocumentInfo[] {
  return state.uploads.flatMap((u) => (u.status.kind === "ready" ? [u.status.doc] : []));
}
