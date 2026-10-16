# Frontend

Next.js App Router site for the AI demos. `/` lists the demos, `/chat` is
Chat with your docs, `/contracts` is the contract reviewer and `/invoices` is Invoice → JSON. The typed client for `docs/api.md` is in `lib/api.ts`.

## Run

```sh
npm install
npm run dev        # http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL` to the backend base URL (see `.env.example`). Next
inlines it at build time, so rebuild after changing it.

## Mock mode

When `NEXT_PUBLIC_API_URL` is unset under `npm run dev`, or set to `mock` in
any build, the app talks to an in-memory mock (`lib/mock.ts`) that follows the
API contract. The first health check takes 2.5 seconds, so the "waking up"
state shows. Questions that start with these commands return contract errors:

| Question starts with | Result |
|---|---|
| `!429` | `rate_limited` with `Retry-After: 30` |
| `!expire` | the session is dropped and the call returns `session_not_found` |
| `!quota` | `llm_quota` |
| `!none` | an answer with no citations |

A contract review returns a real review of the sample lease
(`lib/mock-review.ts`) with one quote that isn't in the contract, so the
unverified state shows. An invoice extraction returns the real result for
the sample receipt for any image and for the sample invoice for any PDF
(`lib/mock-invoices.ts`), so a failed check shows. Uploading a file named
`error.pdf` to either demo returns `llm_error`.

A production build with `NEXT_PUBLIC_API_URL` unset shows a configuration
error instead of falling back to the mock.

## Check

```sh
npm run lint
npm test
npm run build
```
