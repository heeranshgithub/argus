# PLAN — Part 2: Sessions CRUD & Persistence

**Goal:** Stand up the `sessions` resource end-to-end. A user can create a research session from a form, see all their sessions in a history list, and open a detail page (still empty of workflow/report — those come in Parts 3–4). Everything persists in Mongo, validates on both sides, and behaves correctly in loading/error/empty states.

**Exit criteria:**
- `POST /api/sessions` creates a session in Mongo; `GET /api/sessions` lists them; `GET /api/sessions/{id}` fetches one.
- Frontend has a Create form (Zod validated), a History page, and a Detail page shell.
- camelCase wire ↔ snake_case Mongo confirmed end-to-end by tests.
- Loading skeletons, empty states, and error toasts all wired.
- `ruff`, `pytest`, `eslint`, `tsc` green.

---

## 1. Data Model

### `sessions` collection (Mongo, snake_case)
| field           | type          | notes                                  |
|-----------------|---------------|----------------------------------------|
| `_id`           | ObjectId      | mapped to `id` on wire                 |
| `company_name`  | str           | required, 1–200 chars                  |
| `website`       | str           | required, URL (http/https)             |
| `objective`     | str           | required, 1–2000 chars                 |
| `status`        | str           | enum: `created`, `running`, `completed`, `failed` — default `created` |
| `created_at`    | datetime (UTC)| set on insert                          |
| `updated_at`    | datetime (UTC)| set on insert + on update              |

Indexes:
- `created_at: -1` (history list ordering)
- `status: 1` (filter later)

---

## 2. Backend

### 2.1 New files
```
backend/app/
  models/
    session.py            # SessionCreate, SessionUpdate, SessionOut, SessionStatus
    mongo_base.py         # MongoModel base (id alias for _id)
  repositories/
    __init__.py
    session_repo.py       # async CRUD on sessions collection
  api/
    sessions.py           # /api/sessions routes
  services/
    __init__.py
    session_service.py    # thin orchestration above repo (room for later logic)
backend/tests/
  test_sessions_api.py
  test_session_repo.py
```

### 2.2 Models (`models/session.py`)
- `SessionStatus(StrEnum)`: `created | running | completed | failed`.
- `SessionCreate(ApiModel)`: `company_name`, `website` (`HttpUrl`), `objective`.
- `SessionUpdate(ApiModel)`: optional `status`.
- `SessionOut(ApiModel)`: `id`, `company_name`, `website`, `objective`, `status`, `created_at`, `updated_at`.
- All inherit `ApiModel` so the wire is camelCase automatically.

### 2.3 Mongo base (`models/mongo_base.py`)
- Helper to convert Mongo document → `SessionOut` (`_id` → `id` as string).
- Avoid leaking `ObjectId` to Pydantic; convert at the repo edge.

### 2.4 Repository (`repositories/session_repo.py`)
Pure async functions taking the `AsyncIOMotorDatabase`:
- `create(db, data: SessionCreate) -> SessionOut`
- `list(db, limit: int, skip: int) -> list[SessionOut]`
- `get(db, session_id: str) -> SessionOut | None`
- `update_status(db, session_id: str, status: SessionStatus) -> SessionOut | None`

All writes set `updated_at = datetime.now(UTC)`. `create` also sets `created_at` and `status="created"`.

Raises `SessionNotFound` (custom exception) when an id doesn't exist; the API handler turns it into a 404 with the standard error contract.

### 2.5 API routes (`api/sessions.py`)
- `POST /api/sessions` → 201 `SessionOut`
- `GET /api/sessions?limit=20&skip=0` → `{ items: SessionOut[], total: int }` (paginated)
- `GET /api/sessions/{session_id}` → `SessionOut` or 404

Notes:
- `session_id` path validator rejects non-ObjectId strings with a clean 400.
- All routes return through `response_model=...` with `response_model_by_alias=True`.

### 2.6 Error additions
- `SessionNotFound` → 404 `{ error: { code: "session_not_found", ... } }`.
- Invalid ObjectId → 400 `{ error: { code: "invalid_id", ... } }`.

### 2.7 Tests
- `test_session_repo.py` — uses a real local Mongo (or `mongomock-motor`) to verify create/list/get/update_status, ordering by `created_at desc`, and not-found behavior.
- `test_sessions_api.py` — full HTTP tests with `httpx.AsyncClient`:
  - POST camelCase payload → 201 → response keys are camelCase.
  - Stored Mongo document has snake_case fields (asserted directly against the DB).
  - GET list returns newest first.
  - GET missing id → 404 with the error contract shape.
  - Validation: missing fields, invalid URL, oversized strings → 422.

---

## 3. Frontend

### 3.1 New files
```
frontend/src/
  app/
    sessions/
      page.tsx                  # History list
      new/page.tsx              # Create form
      [id]/page.tsx             # Detail shell
  components/
    sessions/
      session-create-form.tsx
      session-list.tsx
      session-list-item.tsx
      session-empty-state.tsx
      session-detail-header.tsx
  services/
    sessions.ts                 # RTK Query endpoints
  schemas/
    session.ts                  # Zod schemas
  types/
    session.ts                  # TS types matching backend (camelCase)
```

### 3.2 Types (`types/session.ts`)
```ts
export type SessionStatus = 'created' | 'running' | 'completed' | 'failed';

export interface Session {
  id: string;
  companyName: string;
  website: string;
  objective: string;
  status: SessionStatus;
  createdAt: string;  // ISO
  updatedAt: string;
}

export interface SessionListResponse {
  items: Session[];
  total: number;
}
```

### 3.3 Zod (`schemas/session.ts`)
```ts
export const sessionCreateSchema = z.object({
  companyName: z.string().min(1).max(200),
  website: z.string().url(),
  objective: z.string().min(1).max(2000),
});
export type SessionCreateInput = z.infer<typeof sessionCreateSchema>;
```
Used both for form validation and for the RTK Query mutation arg type.

### 3.4 RTK Query (`services/sessions.ts`)
Inject endpoints into the base `api`:
- `getSessions: builder.query<SessionListResponse, { limit?: number; skip?: number }>` — `providesTags: ['Session']`
- `getSession: builder.query<Session, string>` — `providesTags: (r, e, id) => [{ type: 'Session', id }]`
- `createSession: builder.mutation<Session, SessionCreateInput>` — `invalidatesTags: ['Session']`

### 3.5 Pages

**`/sessions/new`** — Create form
- ShadCN `Card` with `Input` + `Textarea` + `Label`.
- React Hook Form (add `react-hook-form` + `@hookform/resolvers`) with `zodResolver(sessionCreateSchema)`.
- Submit → `createSession` → on success: Sonner success toast + `router.push('/sessions/[id]')`.
- On error: parse standard error contract, show toast with `error.message`.
- Disable button while pending, show spinner.

**`/sessions`** — History
- `useGetSessionsQuery` with default pagination.
- Loading: 5 `Skeleton` rows.
- Empty: `SessionEmptyState` with CTA → `/sessions/new`.
- Loaded: list of `SessionListItem` (company name, objective preview, status badge, relative time).
- Top-right "New Session" button.
- Auto-refetch on focus (RTK Query default behavior is enough).

**`/sessions/[id]`** — Detail shell
- `useGetSessionQuery(id)`.
- Renders `SessionDetailHeader` (company, website link, objective, status badge, created time).
- Two empty placeholder panels labeled "Workflow" and "Report" (filled in Parts 3–4).
- 404 path: if query returns `session_not_found`, render a friendly "not found" view with a link back to history.

### 3.6 Status badge
- Small `components/ui/status-badge.tsx` mapping `SessionStatus` → color (gray/blue/green/red) + label. Reused later for workflow runs.

### 3.7 Navigation
- Update root `layout.tsx` to include a thin top nav: "Argus" logo, link to `/sessions`. Mobile-friendly.

---

## 4. Cross-cutting

### 4.1 Naming bridge verification
A backend test inserts a document via the API, then reads the raw Mongo doc and asserts:
- Stored keys: `company_name`, `created_at`, etc. (snake_case)
- API response keys: `companyName`, `createdAt`, etc. (camelCase)

This is the canonical proof that the bridge works for a real resource.

### 4.2 Error UX
- All RTK Query errors funnel through a small helper `toApiError(e)` that returns `{ code, message }` from the standard contract; UI shows `message` in a Sonner toast.

### 4.3 Time formatting
- Add `date-fns` (lightweight). Helper `formatRelative(iso: string)` for list items.

---

## 5. Step-by-Step Execution Order

1. Backend: `models/session.py`, `mongo_base.py`, `repositories/session_repo.py`. Add unit tests for repo (mongomock-motor).
2. Backend: `api/sessions.py`, register on the router, add error mappings. Add API tests.
3. Backend: add indexes on app startup (`sessions.created_at`, `sessions.status`) — idempotent `create_index` calls in the Mongo lifespan.
4. Frontend: types, Zod schemas, RTK Query endpoints.
5. Frontend: build pages in order — `new` → `[id]` shell → history list.
6. Wire status badge + empty/loading/error states.
7. Manual smoke: create a session, see it in history, open detail, refresh, restart backend → still there.
8. Run all linters and tests. Commit.

---

## 6. Out of Scope for Part 2

- Running the LangGraph workflow (Part 3).
- SSE / real-time progress (Part 4).
- Report rendering and chat (Parts 4–5).
- Deleting or editing sessions (not required by the spec; can be added later if time allows).
- Auth / multi-user (entire project assumes single-user demo unless explicitly added).

---

## 7. Definition of Done — Part 2

- [ ] `POST/GET /api/sessions` and `GET /api/sessions/{id}` work and are tested
- [ ] Mongo documents are snake_case; API payloads are camelCase (asserted by test)
- [ ] Create form validates with Zod and submits via RTK Query
- [ ] History page renders with loading, empty, and error states
- [ ] Detail page shell renders session header and 404s cleanly
- [ ] Status badge component reusable for later workflow states
- [ ] `ruff check`, `pytest`, `eslint`, `tsc --noEmit` all green
- [ ] Sessions persist across backend restarts
