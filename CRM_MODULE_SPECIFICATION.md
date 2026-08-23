# FC Hub CRM Module Specification

**Status:** Frozen specification baseline (`SPRINT_PROCESS.md` section 7),
**amended 2026-07-28** per section 12A below. Sections describing tables,
columns, or behaviour not yet present in the codebase are **planned**, not
implemented, per `MASTER_PROJECT_SPECIFICATION.md` section 13. Any further
change to this document starts a new sprint from this frozen baseline
rather than patching it casually.
**Governs:** `modules/crm/`, `core/customer.py`, `core/contact.py`,
`core/address.py`, `core/crm_repository.py`, `core/crm_service.py`,
`core/crm_validation.py`, and the `customers`, `customer_contacts`,
`customer_addresses`, `customer_sites`, `customer_activities` tables.
**Parent documents:** `MASTER_PROJECT_SPECIFICATION.md` (sections 1, 5.1,
5.3, 6.1–6.2, 7.1), `PROJECT_RULES.md`, `DEVELOPMENT_STANDARDS.md`,
`DEVELOPMENT_SPECIFICATION.md`, `SPRINT_PROCESS.md`. If anything here
conflicts with those documents, the parent documents win and work stops for
resolution before code changes, per master spec section 13.

This document exists so that CRM implementation can proceed as one
controlled sprint (per `SPRINT_PROCESS.md`) against a frozen specification,
instead of design-while-coding.

---

## 1. Audited baseline (what exists today)

Confirmed by direct inspection of the repository on 2026-07-28:

- `modules/crm/` is a discovered module (`CRMModule` → `CRMUtility` →
  `BaseModule`) showing a four-tab `CTkTabview` (Customers, Contacts, Sites,
  Activities) with read-only `ttk.Treeview` tables and a Refresh button. No
  create/edit/delete/search UI exists yet.
- `core/customer.py`, `core/contact.py`, `core/address.py` define the
  `Customer`, `Contact`, `Address` dataclasses. `modules/crm/services.py`
  defines module-local `Site` and `Activity` dataclasses (these should move
  to `core/` — see section 9).
- `core/crm_repository.py` provides `CustomerRepository`, `ContactRepository`,
  `AddressRepository` (parameterized SQL, upsert via `ON CONFLICT`).
  `modules/crm/services.py` provides `CRMModuleRepository` for sites and
  activities.
- `core/crm_service.py` provides `CRMService` with basic save/list/search and
  a `import_contact()` method used by Communications' CRM-matching workflow.
- `core/crm_validation.py` provides minimal required-field and email-format
  checks; no duplicate detection, no archive/status workflow.
- Migration `v0001_baseline` created `customers`, `customer_contacts`,
  `customer_addresses`, `customer_sites`, `customer_activities` as the
  unmodified nine-table legacy baseline (master spec section 5.1). Migration
  `v0002` added Communications signature fields (unrelated to CRM).
- **Confirmed schema gaps**, matching master spec section 5.1's own
  statement that "Sites and activities are existing but require migration to
  complete relationship integrity":
  - `customer_sites.customer_id` and `customer_activities.customer_id` /
    `contact_id` have **no foreign key** and default to `''`, so orphaned or
    misspelled references are currently possible.
  - `customer_sites` stores a free-text `address`/`city`/`province` instead
    of referencing `customer_addresses`, so a site's address is not the
    authoritative structured address (master spec section 5.3).
  - No `archived_at` / `archived_by` / archive reason on any CRM table —
    `CustomerRepository.delete()` performs a **hard delete**, which conflicts
    with master spec section 5.2 ("Soft delete/archive for business records
    where history must be retained").
  - No `created_by` / `updated_by` columns.
  - No unique, human-readable customer number — `customers.id` is a UUID
    only. `numbering_sequences` does not exist.
  - No duplicate-customer detection beyond a manual `LIKE` search.
  - `customer_contacts` has no `is_primary` flag, so "the" contact for a
    customer is not represented.

This baseline, not a hypothetical clean-slate design, is what the plan below
migrates forward. Nothing here proposes discarding or rewriting working
code; it proposes completing it per master spec Phase 1.

---

## 2. Confirmed business rules (replace prior placeholder assumptions)

Provided directly by Minette on 2026-07-28. These bind CRM and every
downstream module that reads customer data — do not substitute different
figures or a different numbering shape.

- **Numbering scheme** (already decided, CRM originates the root number).
  The source documents' `AAA-001` template is not a literal constant —
  `AAA` is the first 3 letters of the customer's own name, uppercased
  (corrected 2026-07-29, see section 12A). Example for a customer named
  "Komatsu Africa":
  - Customer: `KOM-001`
  - Quote: `KOM-001-Q-001`
  - Job: `KOM-001-J-001`
  - Pro forma: `KOM-001-PF-001`
  - Invoice: `KOM-001-INV-001`

  Customer numbers are a sequence **scoped per derived prefix** (zero-padded
  to 3 digits, no yearly reset, never reused) — a second customer whose name
  also starts "Komatsu..." gets `KOM-002`, not a fresh `KOM-001`. A name
  shorter than 3 letters (or symbol-only) pads with `X` (e.g. "3M" →
  `MXX-001`). Quote/job/pro-forma/invoice numbers are a **sequence scoped to
  the owning customer**, not a single global counter per document type.
  CRM's obligation is to guarantee every customer has exactly one immutable
  `<prefix>-###` number and to expose it so that Quotes/Work Orders/Finance
  can build their own numbers on top of it later.
- **Payment terms:** default is 65% deposit / 35% balance. Customers who pay
  via customer-supplied netting (EDI/procurement netting) instead pay 100%
  upfront. This is a **per-customer** attribute, so CRM must store it.
- **Late payment interest:** 12.5% p.a. This is a Finance/Settings default,
  not stored per customer unless a future customer-specific override is
  requested; CRM does not implement it, but must not block Finance from
  reading customer payment terms later.
- **Business identity:** [Business Name] is **not VAT registered**
  (business registration details). This affects `business_settings`
  (Settings module) and quotation/invoice VAT calculation, not the CRM data
  model. `customers.vat_number` is unrelated — it records a *customer's own*
  VAT number, unaffected by this fact. No CRM change follows from this
  beyond confirming that `customers.vat_number` must stay clearly labelled
  as belonging to the customer, not [Business Name].

---

## 3. Module scope

### 3.1 CRM owns

- Customer master identity: name, type, status, contact details, VAT number
  (customer's own), payment terms, notes, customer number.
- Contacts belonging to a customer, including a single designated primary
  contact per customer.
- Structured addresses belonging to a customer (billing, postal, physical,
  site).
- Customer-owned operational sites, each referencing a structured address.
- The customer/contact/site activity timeline (a read model other modules
  write to, not a general-purpose notes field).
- Duplicate-customer and duplicate-contact detection and safe merge.
- Archive/reactivate workflow for customers, contacts, addresses, and sites.
- The customer-number numbering contract (`FAC-###`).
- Global-search projections for customers, contacts, and sites.
- CRM-side of the Communications import workflow it already participates in
  (`CRMService.import_contact`) — unchanged in this spec.

### 3.2 CRM does not own

- Leads and lead-to-customer conversion (`leads`, `lead_activities` —
  future Leads module; conversion writes into CRM through CRM's service
  contract, never directly into CRM tables).
- Mailbox intelligence, candidate discovery, or classification
  (Communications module — unchanged, CRM only consumes its import calls).
- Quotations, work orders, job cards, invoices, or any money calculation
  (payment terms are *stored* by CRM and *used* by Finance/Quotes).
- Documents/Photos storage (CRM links to them through the shared
  `document_links` / `photo_links` tables once those modules exist; CRM
  never stores file bytes).
- User identity, roles, or permission definitions (Administration module —
  CRM enforces permission checks at its service boundary using whatever
  identity is available, but does not define roles).

---

## 4. Domain model (target state)

Field lists below are the **authoritative target**; section 8 gives the
ordered migration path from the audited baseline to this state. Types use
SQLite storage classes as elsewhere in the codebase.

### 4.1 Customer

| Field | Type | Notes |
|---|---|---|
| `id` | TEXT PK | Stable UUID, unchanged. |
| `customer_number` | TEXT, UNIQUE, NOT NULL | `FAC-###`, generated once via the numbering service, never reused or edited by users. |
| `name` | TEXT, NOT NULL | Existing. |
| `customer_type` | TEXT | Existing (e.g. Commercial, Residential, Body Corporate — controlled list, not free text, per master spec 4.2). |
| `status` | TEXT | Controlled: `Active`, `Inactive`, `Archived`. Replaces ad hoc strings. |
| `payment_terms` | TEXT, NOT NULL, DEFAULT `'Standard'` | Controlled: `Standard` (65/35) or `Netting` (100% upfront). See section 2. |
| `email`, `phone`, `website` | TEXT | Existing. |
| `vat_number` | TEXT | Existing; the customer's own VAT number, may be blank. |
| `notes` | TEXT | Existing. |
| `created_at`, `updated_at` | TEXT (ISO 8601) | Existing. |
| `created_by`, `updated_by` | TEXT, nullable | New. Populated with the acting user identifier where available; nullable until Administration/`users` exists, per master spec 5.2. |
| `archived_at`, `archived_by`, `archive_reason` | TEXT, nullable | New. Soft delete/archive per master spec 5.2; `CustomerRepository.delete()` is retired in favour of `archive()`. |

Indexes: `name` (existing), `customer_number` (unique), `status`, normalized
`email`.

### 4.2 Contact

Adds to the existing `customer_contacts` columns:

| Field | Type | Notes |
|---|---|---|
| `is_primary` | INTEGER (0/1), DEFAULT 0 | Exactly one primary contact per customer, enforced in the service layer (a partial unique index is not portable in SQLite without a trigger; service-level enforcement plus a regression test is sufficient here). |
| `created_by`, `updated_by` | TEXT, nullable | Same rationale as Customer. |
| `archived_at`, `archived_by`, `archive_reason` | TEXT, nullable | Same rationale as Customer. |

`customer_id` gains a proper `FOREIGN KEY ... ON DELETE CASCADE` (it is
already declared this way in `v0001`; this column is already correct).

### 4.3 Address

Adds `created_by`/`updated_by` and archive fields as above. `address_type`
becomes a controlled list: `Billing`, `Postal`, `Physical`, `Site`. No other
structural change — `customer_addresses` is already the structured address
table the rest of the schema should reference.

### 4.4 Site

`customer_sites` is normalized to match master spec 5.3
("customer-owned operational locations referencing a structured address"):

No `site_number` — see section 12A. Multiple sites per customer (e.g. a
landlord with several tenanted installation addresses) are distinguished by
their own structured address, not a formatted identifier.

| Field | Type | Notes |
|---|---|---|
| `id` | TEXT PK | Existing. |
| `customer_id` | TEXT, NOT NULL, FK → `customers(id)` | Currently unenforced; becomes a real foreign key. |
| `address_id` | TEXT, NOT NULL, FK → `customer_addresses(id)` | New. Replaces free-text `address`/`city`/`province` as the authoritative address. |
| `name`, `site_type`, `notes` | TEXT | Existing. |
| `created_at`, `updated_at`, `created_by`, `updated_by` | as above |
| `archived_at`, `archived_by`, `archive_reason` | as above |

The legacy free-text `address`, `city`, `province` columns are retained
**read-only** for one migration cycle (populated at migration time into a
new `customer_addresses` row per site, `address_type='Site'`) and then
dropped in a follow-up migration once verified — SQLite cannot drop columns
before schema version 3.35 reliably in this codebase's supported form, so
the safe path is: add new columns → backfill → stop writing legacy columns
→ drop them in a clearly separate, later migration. This avoids a single
migration doing both structural change and destructive column removal.

### 4.5 Activity

`customer_activities` is normalized:

| Field | Type | Notes |
|---|---|---|
| `customer_id` | TEXT, NOT NULL, FK → `customers(id)` ON DELETE CASCADE | Currently unenforced. |
| `contact_id` | TEXT, nullable, FK → `customer_contacts(id)` ON DELETE SET NULL | Currently unenforced; must become nullable+FK, not required. |
| `site_id` | TEXT, nullable, FK → `customer_sites(id)` ON DELETE SET NULL | New — master spec 5.3: activities "optionally" link to site. |
| `source_entity_type`, `source_entity_id` | TEXT, nullable | New — generic pointer so a future Visit, Quote, Work Order, or Invoice can post one activity row without CRM depending on those modules' schemas. Validated against a controlled list of entity types at the service layer, never a raw foreign key (those tables do not exist yet). |
| `activity_type`, `subject`, `activity_date`, `status`, `notes` | TEXT | Existing. |
| `created_at`, `updated_at`, `created_by` | as above | Activities are an append-mostly timeline; no `updated_by`/edit workflow beyond correcting the note text. |

Indexes: `customer_id`, `activity_date` (for timeline ordering and
notification queues per master spec 5.4).

---

## 5. Numbering strategy (CRM's part)

CRM requires one shared capability that does not exist yet: the
`numbering_sequences` table and a `NumberingService` (master spec 5.5),
introduced by this sprint because CRM is its first consumer.

Target `numbering_sequences` row shape:

| Field | Notes |
|---|---|
| `id` | TEXT PK |
| `document_type` | e.g. `customer`, `site` |
| `scope` | `global`, `per_customer`, or `prefix` |
| `scope_id` | empty for `global`; the derived prefix (e.g. `KOM`) for `prefix` scope |
| `prefix` | the actual prefix text stored on the row, e.g. `KOM` |
| `padding` | `3` |
| `next_value` | INTEGER, incremented transactionally |
| `yearly_reset` | 0 for customer numbers (never reset) |
| `last_reset_year` | nullable |

`NumberingService.allocate(connection, document_type, scope=..., scope_id=...,
prefix=..., padding=...)` allocates and persists the next number inside the
same transaction as the record it numbers, so a failed save never burns a
number. This service lives in `core/` (shared), not inside the CRM module,
because Quotes/Jobs/Finance will call the same service later using the
customer number as their scope key — CRM does not own numbering, it is
numbering's first caller.

CRM's concrete obligation: `CustomerRepository.save()` derives the prefix
from `customer.name` via `customer_number_prefix()` (first 3 letters,
uppercased, `X`-padded if shorter, non-letters stripped) and calls
`NumberingService.allocate(..., scope="prefix", scope_id=prefix)` exactly
once, on first save — never regenerating or editing `customer_number`
afterward (master spec 5.5: "Internal UUIDs remain stable when a display
number changes format" — the converse also holds, the display number must
not change once issued). Numbering is scoped **per derived prefix**, not
globally: a second customer whose name yields the same prefix continues
that prefix's own sequence (`KOM-001`, `KOM-002`, ...), not a shared
customer-wide counter.

---

## 6. Validation rules (target state)

In addition to the existing required-name and email-format checks:

- **Customer:** `payment_terms` must be one of the controlled values;
  `status` must be one of the controlled values; a customer cannot be saved
  with `status='Archived'` through the normal save path — only through
  `archive()`.
- **Contact:** setting `is_primary=True` demotes any other primary contact
  for the same customer inside the same transaction (never two primaries).
  A contact cannot be archived if it is the sole remaining contact for an
  `Active` customer without an explicit confirmation (surfaced to the UI,
  not silently blocked).
- **Address:** `address_type` must be one of the controlled values; a
  customer may have at most one `is_primary=True` address per type-scope
  (billing vs postal vs physical), enforced the same way as contact primacy.
- **Site:** `address_id` must belong to the same `customer_id` as the site.
- **Activity:** `customer_id` must reference an existing, non-archived
  customer for new activity creation (historical activities on an archived
  customer remain readable, never blocked from being *viewed*).
- **Duplicate detection:** on customer save, warn (not block) when an
  existing customer shares a normalized email, phone, or a case/whitespace-
  insensitive name match. On contact save, warn on a normalized-email match
  against a different customer. This is presented to the user as a
  confirmation, matching master spec 7.1 ("prevent duplication").

---

## 7. Workflow

### 7.1 Customer lifecycle

1. Create draft (no number yet) → validate → save → `NumberingService`
   issues `customer_number` in the same transaction → customer is `Active`.
2. Edit customer, contacts, addresses independently; each save revalidates
   only its own entity.
3. Archive requires a reason and is blocked while the customer has any
   non-archived site with an open (not-yet-modelled-here, so: any) linked
   downstream record once those modules exist; for this sprint, archiving a
   customer cascades an archive prompt for its active sites but does not
   hard-delete anything, matching current repository behaviour being
   replaced.
4. Reactivate clears `archived_at`/`archived_by`/`archive_reason` and
   returns `status` to `Active`; it is always permitted and always audited.
5. Merge (two customer records determined to be duplicates): one survives,
   the other's contacts/addresses/sites/activities are re-pointed to the
   survivor inside one transaction, and the losing customer becomes
   `Archived` with `archive_reason='Merged into <customer_number>'` — its
   row and number are **never deleted**, so historic references elsewhere
   stay valid.

### 7.2 Timeline

The Activity list for a customer is the single place every module posts a
one-line event (a contact added, a site created, and later a quote issued,
a job completed, an invoice raised). CRM's job in this sprint is only to
make the table safe to write to (real FKs, optional `site_id`, generic
`source_entity_type`/`source_entity_id`); it does not yet receive events
from modules that do not exist.

### 7.3 Communications import (unchanged)

`CRMService.import_contact()` keeps its four existing actions. It gains
`customer_number` allocation transparently through the normal
`save_customer()` path — no interface change is needed for Communications.

---

## 8. Migration plan (ordered, matches `core/migrations` conventions)

Two migrations, each a single transactional version, each independently
verifiable and rollback-safe, continuing from the existing `v0002`:

**`v0003_crm_relationship_integrity`**
1. Add `customer_id` FK constraint groundwork: SQLite cannot add a
   constraint to an existing column, so this migration creates the
   corrected `customer_sites` and `customer_activities` tables under
   temporary names, copies data across (skipping/reporting orphaned rows
   that reference a missing `customer_id` — none are expected against the
   current production data, but the migration must not silently drop them;
   it moves orphans into a `customer_activities_orphaned_v0003` /
   `customer_sites_orphaned_v0003` holding table for manual review instead
   of deleting), drops the old table, renames the new one into place.
2. Add `archived_at`, `archived_by`, `archive_reason`, `created_by`,
   `updated_by` to `customers`, `customer_contacts`, `customer_addresses`,
   `customer_sites`, `customer_activities`.
3. Add `is_primary` to `customer_contacts`.
4. Add indexes: `customer_activities(customer_id)`,
   `customer_activities(activity_date)`, `customer_sites(customer_id)`,
   `customers(status)`.
5. Verification: foreign-key check passes, row counts before/after match
   (plus any rows moved to an orphan table), every existing customer/
   contact/address/site/activity round-trips through the existing
   repository read methods unchanged.

**`v0004_crm_numbering_and_sites`**
1. Create `numbering_sequences`.
2. Add `customer_number` (nullable at first), `payment_terms` (default
   `'Standard'`) to `customers`.
3. Backfill: for every existing customer ordered by `created_at`, allocate
   a `customer_number` through the same numbering logic the service will
   use at runtime (so backfilled numbers and future numbers are one
   contiguous sequence, not two competing schemes). Then make
   `customer_number` `NOT NULL UNIQUE`.
4. Add `address_id` to `customer_sites` (nullable at first); for every
   existing site, create a `customer_addresses` row from its legacy
   `address`/`city`/`province` text (`address_type='Site'`) and point
   `address_id` at it. Then make `address_id` `NOT NULL` with its FK.
   Legacy `address`/`city`/`province` columns on `customer_sites` are kept
   but stop being written to by the application from this version forward;
   they are dropped in a later, separate migration once Minette has
   confirmed the backfilled addresses are correct.
5. No `site_number` — removed per section 12A.
6. Verification: `numbering_sequences.next_value` for `customer` equals
   `count(customers) + 1`; every customer has a unique `FAC-###` number;
   every site has a non-null `address_id` resolving to a real
   `customer_addresses` row for the same customer.

Both migrations run through the existing `core/migrations/runner.py`
transactional/checksum mechanism, mirror `PRAGMA user_version`, and require
a verified pre-migration backup per master spec 5.6 before running against
the production database — i.e. this sprint's own **Backup** work (section
10 of this document) is a precondition for applying `v0003`/`v0004` to
`database/fc_hub.db`, not just an unrelated add-on.

---

## 9. Code changes implied (no code written yet)

- Move `Site` and `Activity` dataclasses from `modules/crm/services.py` into
  `core/site.py` and `core/activity.py`, alongside `Customer`/`Contact`/
  `Address`, so CRM's domain models live in one place per
  `DEVELOPMENT_STANDARDS.md` section 3. `modules/crm/services.py`'s
  `CRMModuleRepository` either merges into `core/crm_repository.py` as
  `SiteRepository`/`ActivityRepository`, or stays as a thin module-local
  wrapper calling into `core` — merging into `core` is preferred so
  `CRMService` becomes the single service boundary, matching master spec
  3.2 ("Windows... call services").
- `CRMService` gains `archive_customer`, `reactivate_customer`,
  `merge_customers`, `set_primary_contact`, `find_possible_duplicates`,
  and site/activity save methods that currently live only in the module's
  repository, so business rules stop being reachable by two different
  paths.
- `CustomerRepository.delete()` is removed from the normal save/delete
  surface used by the UI; a hard-delete capability, if kept at all, moves
  behind an explicit Administration-only operation, not the CRM window.
- `CRMWindow` gains create/edit dialogs, a search box, an archive action,
  and a timeline panel, replacing the current read-only tables — this is
  the largest single piece of new code and should be its own controlled
  change after the data-layer migrations land and are verified, per
  `PROJECT_RULES.md` rule 6 ("one controlled change at a time").

---

## 10. Testing plan

Per master spec section 11 and `DEVELOPMENT_STANDARDS.md` section 10:

- Repository tests (temporary DB): FK enforcement rejects orphaned
  `customer_id`; unique `customer_number`; cascade delete of
  contacts/addresses on customer delete no longer reachable from the
  service layer (archive path only).
- Service tests: numbering allocation is transactional and gap-free under
  a simulated failure after allocation but before commit; primary-contact
  demotion is atomic; duplicate-detection warnings fire on known fixtures
  and do not fire on genuinely distinct customers; merge re-points every
  child row and leaves the losing customer archived, not deleted.
- Migration tests: apply `v0001` → `v0002` → `v0003` → `v0004` against a
  temporary database seeded with representative existing-shape rows
  (including at least one row that would be orphaned) and assert the
  documented outcomes in section 8; also test a completely empty database
  reaching the same end state.
- Workflow test: create customer → add contact → mark primary → add site →
  add activity → archive customer → verify site/contact still readable →
  reactivate, entirely through `CRMService`, no direct SQL.
- Regression: existing `tests/test_crm_import.py` and
  `tests/test_database_migrations.py` continue to pass unmodified in
  behaviour (import contract unchanged; migration test file gains new
  cases, doesn't lose old ones).

---

## 11. Definition of complete (master spec 11.3, applied to CRM)

CRM Phase 1 is complete only when:

- `v0003` and `v0004` apply cleanly from empty and from the current
  production schema, are verified, and are reversible by restoring the
  pre-migration backup (never by a down-migration against live data).
- Every existing customer/contact/address/site/activity is readable and
  unchanged in meaning after migration (spot-checked against a pre-
  migration export).
- Archive replaces delete in the UI and service surface; no UI path can
  hard-delete a customer with contacts/addresses/sites still attached.
- Duplicate warnings and primary-contact enforcement are visible in the UI,
  not just enforced silently in the service.
- All tests in section 10 pass and are recorded per `PROJECT_RULES.md`
  rule 8 ("never claim a test passed unless it was actually run").
- `python -m compileall .` and application launch succeed with the CRM
  module visible and its tabs functional.
- This document is updated if implementation deviates from it, per
  `DEVELOPMENT_STANDARDS.md` section 11 — the document defines the
  architecture, not the reverse.

---

## 12. Open decisions for Minette before implementation begins (resolved)

These were the genuine choices in this spec, now resolved:

1. **Site legacy address columns:** freeze now, drop later — the safer
   default, unchanged. Not explicitly revisited; proceeding on this basis.
2. **`customer_type` and `status` controlled lists:** proceeding on the
   proposed defaults (`customer_type` = `Commercial`, `Residential`,
   `Body Corporate`, `Government`, `Other`; `status` = `Active`,
   `Inactive`, `Archived`) since not objected to; still worth an explicit
   confirmation before this is written into validation code, since
   changing a controlled list later is a data migration, not a one-line
   edit.
3. **`site_number`: removed.** Resolved 2026-07-28 — see section 12A.

## 12A. Amendment log

**2026-07-29 — customer number prefix corrected: derived per customer, not
a fixed "FAC".** Section 2 and section 5 previously interpreted the source
documents' `AAA-001` numbering template literally as `FAC-001` for every
customer, reading `FAC` as a constant referring to [Business Name] itself.
Minette corrected this directly: `AAA` was always a placeholder for "first
3 letters of the company name" — each customer gets its own derived
prefix (e.g. `KOM-001` for Komatsu), not a shared `FAC-001`/`FAC-002`/...
sequence. `core/crm_repository.py`'s `customer_number_prefix()` now derives
the prefix from `customer.name` (first 3 letters, uppercased, padded with
`X` if shorter; non-letters stripped), and `numbering_sequences` is scoped
per prefix (`scope='prefix'`, `scope_id=<prefix>`) instead of one global
`customer` sequence. Two real customers already exist under the old
scheme (`FAC-001` "Andreas Savas", `FAC-002` "Cavaleros Group") — left
as-is pending Minette's decision on whether to renumber them; nothing
downstream referenced those numbers yet. `v0004`'s migration backfill
logic is unchanged (it already applied to production baselining zero
customers, so nothing to correct there) — only the runtime allocation in
`CustomerRepository.save()` changed.

**2026-07-28 — `site_number` removed from scope.** Minette confirmed a
formatted per-site number is not needed: she has customers (landlords) with
multiple installation sites that commonly share one billing address, and
distinguishing sites by their own structured address (section 4.4) is
sufficient — a separate identifier adds complexity nothing in Phase 1
consumes. Removed from section 4.4's domain model, section 8's `v0004`
migration plan, and section 10's testing plan. `v0004` was implemented
without it and is test-verified.

**2026-07-28 — additional CRM-relevant facts, from `C:\For Claude`
(`[Business Name]_OS_Master_Project_Document_v0.1.docx`,
`[Business Name]_OS_Progress_Audit.docx`, and confirmed directly by Minette),
not yet incorporated into sections 4–9 — deferred to the next amendment or
sprint, not acted on in this session:**

- Customer needs a **registration number** field, distinct from
  `vat_number` (a customer's own company registration number, not
  [Business Name]'s).
- **Purchase Order** is standard on [Business Name]'s paperwork but is a
  per-document field (confirmed: appears on the Invoice, not the customer
  master, in `[Business Name]_CRM_Linked.xlsx`) — belongs to the future
  Quotes/Finance module's document model, not `customers`, and is
  optional/tick-box rather than required.
- `customers.vat_number` is confirmed load-bearing: [Business Name] doesn't
  charge VAT (SME, turnover under the VAT-registration threshold), but
  customers' VAT numbers still need to be captured and reflected on
  [Business Name]'s documents.
- Address types should include **Delivery**, not just Billing/Postal/
  Physical/Site (section 4.3's controlled list needs updating).
- A **landlord/multi-tenant billing** pattern was described: one customer
  (the landlord) with several sites, where billing should be manually
  selectable rather than always following the site's own address. This
  falls out naturally from sites and customers each having their own
  `address_id` (site address vs. customer billing address are already
  independent) — no CRM schema change needed — but the future Quotes/
  Finance module must let the billing address be explicitly chosen per
  document, not auto-derived from the job's site.
- **Testimonials:** resolved 2026-07-28 — these are website/marketing
  content, not a CRM concern. Out of scope for CRM entirely.

No code is written against sections 4–9 until these are confirmed or
Minette explicitly says to proceed with the recommended defaults.
