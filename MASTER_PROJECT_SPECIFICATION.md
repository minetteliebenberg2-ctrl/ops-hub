# FC Hub Master Project Specification

**Owner:** [Business Name]  
**Status:** Governing project specification  
**Applies to:** All FC Hub development, testing, recovery, and future sprints  
**Repository:** `C:\FC_Hub`

## 1. Project overview

### 1.1 Purpose

FC Hub is [Business Name]'s integrated desktop business platform. It brings
customer relationships, communications, sales, field operations, billing,
after-sales service, reporting, and supporting utilities into one modular
application.

FC Hub is not a collection of disconnected utilities. Business modules share
master data and participate in one traceable lifecycle:

`Lead → Customer → Site → Inspection → Quotation → Acceptance → Work Order
→ Scheduling → Job Card → Invoice → Payment → Statement → Maintenance
→ Warranty`

### 1.2 Goals

- Maintain one trusted record for each customer, contact, and site.
- Preserve traceability from first enquiry through after-sales service.
- Reduce duplicate data entry and isolated spreadsheets.
- Support safe, predictable business workflows with explicit statuses.
- Protect production data through migrations, validation, audit history,
  backups, and recovery controls.
- Remain usable on the existing supported small-screen layout.
- Allow new capabilities to be added without modifying the application core.

### 1.3 Scope

The platform covers CRM, leads, communications, marketing, sites, visits,
quotations, scheduling, teams, work orders, job cards, finance, maintenance,
warranty, documents, photos, reporting, administration, settings, suppliers,
products, services, imports, exports, notifications, and audit history.

The current product already includes the Module Framework, Module Host,
Communications, CRM foundation, Backup, Troubleshooter, Batch Renamer,
Duplicate Finder, Empty Folder Remover, and File Mover. Remaining business
capabilities are planned extensions of this architecture.

### 1.4 Design philosophy

- Protect working behavior and data before adding features.
- Prefer simple, explicit, maintainable designs.
- Extend the established architecture; never introduce a competing module,
  plugin, persistence, or window framework.
- Build connected workflows rather than isolated modules.
- Keep business rules outside the UI.
- Reuse shared entities and services instead of duplicating data or logic.
- Implement one controlled sprint at a time.

### 1.5 Technology stack

- Python 3
- CustomTkinter for the application shell and module windows
- Tkinter `ttk.Treeview` for existing tabular interfaces
- SQLite for local relational persistence
- Python standard-library filesystem, CSV, email, mailbox, and SQLite support
- `unittest` for automated tests

Additional dependencies require architectural justification, pinned versions,
installation documentation, and regression coverage.

### 1.6 Architecture principles

- A single application root and a single authoritative Module Framework.
- Automatic module discovery through `ModuleManager`.
- Stable module IDs; display names may change.
- Service-first business logic with repository-based persistence.
- Explicit database migrations and transactional changes.
- Foreign keys, indexes, uniqueness constraints, and validation.
- Integer minor units or validated `Decimal` values for money.
- File references in SQLite; document and photo binaries remain on disk.
- Soft delete/archive for business records where history must be retained.
- Immutable audit records for material business changes.
- Role-based authorization at service boundaries and reflected in the UI.

## 2. Repository structure

### 2.1 Root files

- `launcher.py`: configures CustomTkinter, invokes discovery, creates the main
  window, and starts the event loop. It contains no business logic or manual
  module registration.
- Governance Markdown files: define frozen project, development, sprint,
  recovery, and AI-assisted workflow rules.
- `requirements.txt`, when present: records runtime dependencies.

### 2.2 Major folders

- `framework/`: authoritative module contracts, metadata, discovery,
  registration, ordering, and discovery reporting.
- `core/`: reusable domain models, validation, repositories, database access,
  engines, and cross-module domain services.
- `database/`: the protected production SQLite database and future migration
  resources. Tests must never use the production database.
- `gui/`: shared application windows and shared workspace components,
  including `MainWindow`, `ModuleHost`, and shared legacy-compatible screens.
- `modules/`: discoverable business, administration, reporting, and utility
  modules.
- `utilities/`: retained compatibility utilities where still required. New
  business logic belongs in the appropriate core or module layer.
- `tests/`: unit, integration, workflow, migration, regression, and safe
  temporary-database tests.
- `config/`: non-secret configuration resources and future controlled
  application defaults.
- `assets/`: branding and static application assets.
- `exports/`: user-generated exports; application code must not treat these as
  authoritative records.
- `backups/`: backup outputs where configured; backup destinations remain
  user-controlled.

### 2.3 Standard module structure

```text
modules/
    module_name/
        __init__.py
        module.py
        services.py
        windows.py
```

`module.py` is the discovery entry point. Additional repository, model, export,
or dialog files are allowed when they have clear responsibilities. A module
must not recreate shared infrastructure.

### 2.4 Module Framework

`BaseModule`, `ModuleInfo`, `ModuleManager`, and `ModuleDiscoveryReport` are the
permanent framework. `ModuleManager` discovers module folders, imports the
single valid module class, validates metadata, prevents duplicate IDs and
instances, orders modules deterministically, and reports failures without
blocking healthy modules.

Modules implement `create_window(master)` and return their root widget.
Discovery is idempotent. The launcher never imports individual modules.

### 2.5 Service and repository separation

- Windows collect user intent, present state, and call services.
- Services enforce validation, workflow transitions, permissions, numbering,
  transactions, and cross-entity coordination.
- Repositories execute parameterized persistence operations and map rows to
  domain objects.
- Models represent business data and do not perform UI work.
- Exporters and importers operate through services; they do not bypass
  validation or repositories.

### 2.6 Configuration

Business settings, numbering rules, templates, reminder defaults, email
defaults, and user preferences will be managed through the Settings module.
Secrets must not be committed or printed. Temporary development paths must
never be hard-coded.

## 3. Application architecture

### 3.1 Startup and navigation

The launcher invokes module discovery and creates `MainWindow`. Navigation is
generated from visible discovered modules, preserves order and disabled state,
and displays each module name once. The sidebar scrolls independently.

`ModuleHost` owns common workspace margins, expansion, focus transfer, module
creation error presentation, and one active module window. Switching modules
destroys the previous window and creates a new instance. Resizing never
recreates a module. The host does not add global scrolling or intercept
Treeview and textbox wheel behavior.

### 3.2 Business request path

```text
User action
  → module window/dialog
  → module or core service
  → validation and permission check
  → repository transaction
  → database and audit record
  → notification/document/export event where applicable
  → refreshed UI
```

Multi-entity workflows are coordinated by one service transaction or an
explicit recoverable workflow. Windows never perform ad hoc SQL.

### 3.3 Communications

The existing Communications architecture owns mailbox discovery, contact
candidate extraction, normalization, classification, review, ignore lists,
CRM matching, and CRM import history. Marketing extends these capabilities but
does not duplicate mailbox intelligence or cleanup.

### 3.4 Backup and recovery

Backup protects project files, configuration, documents, and the SQLite
database through the established guarded workflow. New storage locations must
be included deliberately in backup manifests and recovery verification.
Migrations must preserve data and must not undermine recovery procedures.

### 3.5 Diagnostics and troubleshooting

Troubleshooter consumes the authoritative discovery report and registered
diagnostic checks. Checks report health without silently repairing or mutating
business data. Future modules register checks through the existing diagnostics
framework rather than creating separate health systems.

## 4. Coding standards

### 4.1 Python and naming

- Use conventional, explicit Python.
- Classes use `PascalCase`; functions, methods, variables, and modules use
  `snake_case`; constants use `UPPER_SNAKE_CASE`.
- Keep functions focused and names aligned with established business terms.
- Use `pathlib.Path`, context managers, dataclasses where appropriate, and
  type hints where they materially improve clarity.
- Order imports: standard library, third-party, FC Hub.
- Avoid hidden global state, circular imports, and unused imports.

### 4.2 Business architecture

- Services own business behavior.
- Repositories own persistence.
- Shared rules are implemented once at the lowest appropriate shared layer.
- Cross-module operations use public service contracts.
- Workflow transitions are explicit and validated.
- Status values are controlled constants or reference data, not arbitrary UI
  strings.
- Errors are handled at appropriate boundaries and include useful context.
- Exceptions are never silently suppressed.

### 4.3 Database and migration rules

- All schema changes use ordered, versioned migrations.
- A schema-version table records successfully applied migrations.
- Each migration runs transactionally where SQLite permits.
- Migration failure rolls back and leaves the prior version usable.
- Existing data is preserved and verified.
- Tests apply migrations from an empty database and every supported prior
  version using temporary databases.
- SQL is parameterized.
- Foreign keys are enabled on every connection.
- Multi-step writes use explicit transactions and rollback on failure.
- Financial calculations never use binary floating-point persistence.

### 4.4 UI standards

- Keep one Tk root and established parent-child relationships.
- UI work remains on the Tkinter thread.
- Preserve native Treeviews, selection behavior, and attached scrollbars.
- Use `ModuleHost`; do not add module caching or global wheel bindings.
- Dense controls reflow only when required for reachability.
- Dialogs validate before writing and clearly distinguish Save, Cancel,
  Archive, Delete, and destructive actions.
- Do not place business logic in callbacks.

### 4.5 Logging and documentation

Logs include enough context to diagnose failure without exposing client data or
secrets. Logs must have bounded growth. Architectural, schema, installation,
registration, recovery, and frozen workflow changes require corresponding
documentation updates.

### 4.6 Testing expectations

Every module requires repository, service, workflow, migration, and regression
tests. Tests use temporary storage, deterministic data, and no production
mailboxes or database. A test result may only be reported when actually run.

## 5. Database design

### 5.1 Existing schema

The current database contains:

- `customers`
- `customer_contacts`
- `customer_addresses`
- `customer_sites`
- `customer_activities`
- `communication_candidates`
- `communication_occurrences`
- `communication_ignore_list`
- `communication_import_history`

Customers, contacts, addresses, communication review, and CRM import are
existing foundations. Sites and activities are existing but require migration
to complete relationship integrity before production use.

The versioned migration foundation is implemented under `core/migrations`.
Migration version 1 represents this existing nine-table baseline without
normalising or redesigning it. `schema_migrations` is authoritative and
`PRAGMA user_version` mirrors the latest completed version for Backup
compatibility. Existing production databases are never migrated silently.

### 5.2 Common conventions

- Business primary keys are stable text UUIDs unless a justified immutable
  sequence key is more appropriate.
- Human-readable numbers are separate unique fields generated by the numbering
  service.
- Relationship columns use foreign keys and indexed lookup paths.
- Records include `created_at`, `created_by`, `updated_at`, and `updated_by`
  where identity is available.
- Archivable records include `archived_at`, `archived_by`, and an archive
  reason. Issued financial and audit records are never physically deleted by
  ordinary UI operations.
- Timestamps use a consistent ISO 8601 representation.
- Monetary columns use integer minor units with an explicit currency code.
- Quantities and rates use validated decimal representations.

### 5.3 Planned tables by domain

The exact migration names and column sets are approved sprint deliverables,
but the following entities and relationships are authoritative.

#### Identity, configuration, and control

- `users`: application identities and active state.
- `roles`: unique role definitions.
- `permissions`: stable permission codes.
- `user_roles` and `role_permissions`: many-to-many authorization mappings.
- `user_preferences`: per-user display and workflow preferences.
- `business_settings`: legal name, contact details, branding references,
  currency, VAT registration, and defaults.
- `system_settings`: typed application configuration.
- `numbering_sequences`: document type, prefix, next value, padding, optional
  yearly reset, and last reset year.
- `templates` and `template_versions`: controlled document, email, and message
  templates with immutable published versions.
- `audit_log`: append-only entity, action, actor, timestamp, reason, and
  structured before/after metadata.
- `notifications`: recipient, type, linked entity, due time, status, and
  delivery state.

#### CRM, leads, and sites

- `customers`: one customer master with a unique customer number.
- `customer_contacts`: contacts belonging to customers.
- `customer_addresses`: structured addresses; duplicated free-text site
  addresses are not authoritative.
- `customer_sites`: customer-owned operational locations referencing a
  structured address.
- `customer_activities`: timeline events linked to customer and optionally
  contact, site, and originating business entity.
- `leads`: source, referral, owner, stage, status, estimated value, follow-up,
  and conversion links.
- `lead_activities`: lead-specific interactions before conversion.
- `visits`: site inspection or service visit booking, assignee, status, and
  outcomes.
- `visit_checklist_items`, `visit_measurements`, and `visit_observations`:
  structured inspection evidence.

#### Products, services, suppliers, and purchasing

- `product_categories`: shared hierarchy for products, services, and labour.
- `products`: stock or non-stock material catalogue.
- `services`: service and reusable labour catalogue.
- `price_history`: effective-dated selling and cost prices.
- `suppliers` and `supplier_contacts`: supplier master data.
- `supplier_products`: supplier catalogue references and costs.
- `purchase_orders` and `purchase_order_items`: controlled procurement linked
  to suppliers and optionally work orders.

#### Sales and quotations

- `quotations`: customer, site, visit, number, revision, status, issue and
  expiry dates, currency, subtotal, discount, VAT, and total minor units.
- `quotation_items`: ordered product, service, labour, or free-description
  lines with quantity, price, tax, and calculated totals.
- `quotation_revisions`: immutable snapshots of issued revisions.
- `quotation_acceptances`: acceptance/rejection evidence, actor, date, and
  reason.

#### Operations and scheduling

- `employees`: staff identity, status, and contact information.
- `subcontractors`: operational subcontractor records linked to supplier data
  where appropriate.
- `teams` and `team_members`: named working teams and effective membership.
- `skills` and `resource_skills`: assignment qualifications.
- `schedules`: time allocation linked to visits, work orders, or maintenance.
- `work_orders`: operational scope generated from accepted quotations,
  maintenance requests, or authorised manual work.
- `work_order_tasks`, `work_order_materials`, and `work_order_assignments`:
  execution plan and resource requirements.
- `job_cards`: actual execution, arrival, departure, completion, sign-off, and
  outcome.
- `job_card_labour`, `job_card_materials`, and `job_card_checklist_items`:
  actual job consumption and completion evidence.

#### Finance

- `invoices` and `invoice_items`: controlled issued billing records linked to
  customer, site, quotation, work order, and job card where applicable.
- `credit_notes` and `credit_note_items`: immutable authorised invoice
  adjustments.
- `payments`: payment receipts with method, reference, date, and unallocated
  balance.
- `payment_allocations`: amounts allocated between payments and invoices or
  credit notes.
- `statements`: generated statement headers and period metadata.
- `statement_items`: immutable generated ledger lines when statement snapshots
  are required.

#### After-sales

- `installed_assets`: products or equipment installed at a site, with serial,
  installation, source job, and status.
- `maintenance_plans`: recurring service definition, interval, SLA, and active
  dates.
- `maintenance_events`: scheduled and completed maintenance linked to assets,
  sites, work orders, and job cards.
- `warranties`: provider, covered asset/work, terms, start, expiry, and status.
- `warranty_claims`: claim workflow, evidence, decision, and resulting work.

#### Documents, photos, marketing, and integration

- `documents`: metadata and filesystem reference; never binary document data.
- `document_links`: many-to-many links from documents to permitted business
  entities.
- `document_versions`: immutable file-version references and checksums.
- `photos`: filesystem reference, category (`Before`, `During`, `After`),
  caption, date, and capture metadata.
- `photo_links`: links to visits, sites, work orders, job cards, maintenance,
  and warranty records.
- `marketing_consents`: channel, status, source, evidence, and timestamp.
- `marketing_segments` and `segment_members`: controlled audience definitions.
- `campaigns`, `campaign_recipients`, and `campaign_events`: campaign content,
  suppression, sending state, unsubscribe, delivery, open, and click events.
- `import_batches`, `import_rows`, and `import_errors`: preview, validation,
  commit, rollback status, and audit trail.
- `export_history`: export type, filters, actor, time, destination metadata,
  and result.

#### Backup metadata

Backup file manifests remain owned by the Backup module. If persisted in the
primary database, backup-run tables may contain run metadata, checksums,
verification state, and destination references, but never substitute for the
backup files themselves.

### 5.4 Key relationships and indexes

- Customer number, lead number, site number, quotation number, work-order
  number, job-card number, invoice number, credit-note number, statement
  number, maintenance number, and warranty number are unique.
- Contacts and sites reference customers.
- Visits reference customers and sites.
- Quotations reference customers and sites; quotation revisions and items
  reference quotations.
- Accepted quotations generate linked work orders.
- Schedules reference assignable resources and a visit, work order, or
  maintenance event.
- Job cards reference work orders.
- Invoices reference customers and the source work.
- Payment allocations reference valid payments and financial documents.
- Maintenance and warranty reference sites, installed assets, and source work.
- Documents and photos use validated link tables rather than repeated nullable
  foreign keys.
- Index all foreign keys, human document numbers, active statuses, dates used
  in queues, searchable names, normalized email addresses, and due dates.

### 5.5 Numbering strategy

The numbering service generates numbers transactionally from
`numbering_sequences`. It supports configurable prefixes, padding, and a
future optional yearly reset. Generated numbers are unique and are never
reused after cancellation or archiving. Internal UUIDs remain stable when a
display number changes format.

### 5.6 Migration strategy

Migrations are ordered, immutable after release, checksummed, and recorded in a
schema-version table. Startup detects pending migrations but must not perform a
destructive migration silently. Each migration has preconditions, transactional
application, verification, and a documented recovery path. Production data is
backed up and verified before schema migration.

## 6. Business workflow

### 6.1 Lead to customer

1. Create or import a lead with source, owner, status, and follow-up.
2. Record activities and reminders.
3. Qualify or disqualify the lead with a reason.
4. Conversion searches for existing customers and contacts before creating
   records.
5. Successful conversion links the lead permanently to the resulting customer,
   contact, and site; it does not copy uncontrolled duplicate data.

### 6.2 Customer, site, and inspection

1. Assign customer and site numbers through the numbering service.
2. Validate contacts and structured addresses.
3. Book an inspection/site visit and assign an available qualified resource.
4. Capture checklist results, measurements, observations, recommendations,
   documents, and photos.
5. Mark the visit completed, cancelled, or requiring follow-up. Completion
   updates the site timeline and may initiate a quotation.

### 6.3 Quotation and acceptance

1. Build a draft from reusable products, services, labour, and visit findings.
2. Calculate line totals, discount, VAT, subtotal, and total deterministically.
3. Issue a numbered immutable revision and generate the approved document.
4. Track expiry and notify responsible users.
5. Accept, reject, expire, cancel, or revise with actor and reason.
6. Acceptance creates one linked work order through an idempotent service
   operation.

### 6.4 Work, scheduling, and completion

1. Plan tasks, materials, skills, priority, and target dates.
2. Assign teams, employees, or authorised subcontractors without conflicts.
3. Generate a job card for execution.
4. Capture actual labour, materials, notes, checklists, photos, and signatures.
5. Record partial completion, exception, cancellation, rework, or completion.
6. Approved completion updates site history and makes work eligible for
   invoicing and installed-asset creation.

### 6.5 Invoice, payment, and statement

1. Generate a draft invoice from approved quotation or actual completed work
   according to business settings.
2. Validate customer billing data, VAT, source links, and totals.
3. Issue an immutable numbered invoice.
4. Record payments independently and allocate them transactionally.
5. Corrections use credit notes or controlled reversals, never deletion of
   issued records.
6. Generate statements from the customer ledger for a defined period.
7. Overdue balances create reminders according to settings.

### 6.6 Maintenance and warranty

1. Register installed assets from completed work.
2. Create maintenance plans and future events.
3. Due events enter scheduling and generate linked work orders/job cards.
4. Warranty coverage is evaluated against dates, assets, terms, and exclusions.
5. Claims preserve evidence, decisions, resulting work, and costs.
6. All events appear in site and customer history.

## 7. Module specifications

### 7.1 CRM and Customers

Own customer, contact, address, activity, and account-level views. Services
validate identity, prevent duplication, enforce permissions, coordinate safe
archive, and expose global-search projections. Repositories use the shared
database. UI is master-detail with search, filters, editors, timeline, related
sites, documents, financial summary, and exports.

### 7.2 Communications

Own mailbox intelligence, candidate discovery, review, CRM matching, ignore
lists, and import history. Preserve current architecture. It integrates with
CRM activities, Marketing consent, and templates without duplicating those
modules. Mailbox cleanup remains operationally separate from campaigns.

### 7.3 Marketing

Own consent, suppression, segmentation, campaigns, recipients, templates, and
events. It must comply with POPIA requirements, honour unsubscribe and
suppression before sending, and write communication activities. Permissions
separate campaign design, approval, and sending.

### 7.4 Sites

Own operational site identity, structured address relationship, contacts,
access notes, installed assets, documents, photos, and history. Sites belong to
customers. Search includes site number, name, address, customer, asset serial,
and related work.

### 7.5 Visits

Own booking, assignment, inspection checklists, measurements, observations,
recommendations, outcome, and evidence. Visits integrate with Scheduling,
Sites, Quotes, Notifications, Documents, and Photos.

### 7.6 Quotes

Own quotation numbers, revisions, line items, calculations, issue, expiry,
acceptance, rejection, and document generation. Imports do not bypass pricing
validation. Accepted quotations create work through a controlled idempotent
workflow.

### 7.7 Products and Services

Own categories, products, services, labour items, active state, pricing, cost,
tax behavior, and reusable quotation descriptions. Historical issued document
lines retain snapshots even when catalogue records change.

### 7.8 Suppliers and purchasing

Own supplier details, contacts, products, purchase references, notes, and
purchase orders. Supplier and subcontractor concepts are linked where relevant
but retain distinct responsibilities.

### 7.9 Scheduling and Teams

Own employees, subcontractors, teams, skills, availability, assignments, and
calendar conflict rules. Scheduling operates on visits, work orders, and
maintenance events and produces notifications.

### 7.10 Work Orders and Job Cards

Work Orders own authorised scope, tasks, planned resources, materials,
priority, assignments, and status. Job Cards own actual execution, labour,
materials, evidence, completion, sign-off, and exceptions. Services enforce
valid transitions and source traceability.

### 7.11 Finance

Own invoices, credit notes, payments, allocations, statements, customer
ledger, aged balances, and financial exports. Financial permissions, immutable
issued records, minor-unit money, numbering, audit history, and transactional
allocation are mandatory.

### 7.12 Maintenance

Own plans, recurrence, due events, SLA, service history, and resulting work.
Maintenance integrates with sites, assets, scheduling, job cards, documents,
notifications, finance, and reporting.

### 7.13 Warranty

Own warranty terms, coverage dates, providers, claims, evidence, decisions,
and warranty work. It links to installed assets, jobs, sites, suppliers,
documents, photos, and notifications.

### 7.14 Documents and Photos

Own metadata, validated filesystem locations, checksums, versions, categories,
captions, and entity links. Files are never stored inside SQLite. Delete and
replacement operations require permission, audit history, and recoverable
handling. Before, During, and After are standard photo categories.

### 7.15 Reports and Dashboards

Own reusable read models, filters, statistics, exports, print views, and
role-specific dashboards. Reports query authoritative records and never
recalculate business state differently from services. Dashboards show
actionable queues with drill-through rather than decorative metrics.

### 7.16 Administration

Own users, roles, permissions, reference data, audit review, import oversight,
and controlled configuration. Administrative changes are validated and
audited. Business users receive least privilege.

### 7.17 Settings

Own business details, branding references, VAT, currency, numbering,
templates, email defaults, reminder defaults, and system/user preferences.
Settings are typed, validated, permission-controlled, and cached only with
explicit invalidation.

### 7.18 Backup, Diagnostics, and Troubleshooter

Preserve their existing architecture. Backup includes all authoritative
database, configuration, document, photo, and template storage. Diagnostics
and Troubleshooter gain checks for migrations, storage paths, numbering,
notification queues, and module health through the existing check framework.

### 7.19 Search, imports, exports, permissions, and notifications

These are shared platform services, not competing module frameworks:

- Global search covers customers, contacts, sites, leads, quotes, jobs,
  invoices, documents, and activities with permission-filtered results.
- Imports support existing customers, contacts, sites, Excel invoices, PDF
  invoices, historical records, and CSV data through preview, validation,
  duplicate handling, transactional commit, failure rollback, and audit.
- Exports use stable fields, deterministic ordering, explicit filters, and
  audit history.
- Notifications support follow-ups, visits, quotation expiry, scheduled work,
  outstanding invoices, maintenance due, and warranty expiry.
- Permission checks occur in services even when the UI hides an action.

## 8. UI standards

### 8.1 Navigation and module layout

- Navigation is dynamic, ordered, independently scrollable, and readable in
  supported appearance modes.
- Module names appear once. Modules own their visible headings.
- Home and module views use shared `ModuleHost` margins.
- One active module workspace exists at a time.
- Standard module layout: heading, action/search area, primary content, and
  status or summary area where needed.

### 8.2 Controls and behavior

- Primary actions are clearly named; destructive actions are visually and
  spatially distinct.
- Dense toolbars reflow without mixing geometry managers.
- Tables retain native Treeview behavior, explicit selection mode, attached
  vertical scrollbars, and horizontal scrollbars when existing data is wider
  than the workspace.
- Search is debounced or explicitly submitted for expensive queries and does
  not reload unnecessary records.
- Editors display validation adjacent to the relevant fields and preserve
  entered data after a validation failure.
- Long operations provide progress, cancellation where safe, and protection
  against callbacks to destroyed widgets.

### 8.3 Visual standards

- Use the existing CustomTkinter theme, Segoe UI typography, established
  spacing, and readable contrast.
- Support Light, Dark, and System appearance modes.
- Do not encode meaning through color alone.
- Maintain keyboard focus, sensible tab order, readable labels, and adequate
  control targets.
- Dialogs identify the business record and consequence of the action.
- Status bars use concise plain language and do not expose sensitive details.

## 9. Reporting

### 9.1 Standard outputs

- CSV for stable row-oriented data exchange.
- Excel for formatted multi-sheet operational and financial analysis.
- PDF for issued customer documents and fixed-layout reports.
- Print views derived from the same approved templates as PDFs.
- On-screen statistics and dashboards backed by tested queries.

### 9.2 Required report families

- CRM: customer, contact, site, activity, archive, and duplicate review.
- Sales: lead pipeline, lead source, conversion, quotation status, expiry,
  revision, acceptance, and value.
- Operations: visits, schedule, assignments, work-order status, job completion,
  labour, materials, rework, and exceptions.
- Finance: invoices, credit notes, receipts, allocations, statements, aged
  balances, debtors, revenue, and VAT-ready summaries.
- After-sales: installed assets, maintenance due/overdue/completed, service
  history, warranty expiry, and claims.
- Marketing: consent, suppression, campaigns, delivery, unsubscribe, opens,
  and clicks where supported lawfully and technically.
- Administration: audit events, import outcomes, numbering exceptions,
  notification failures, backup verification, and system health.

Reports require permission checks, documented filters, stable column order,
correct numeric sorting, and reconciliation to authoritative records.

## 10. Import and export

### 10.1 Supported inputs

Controlled imports cover CSV, approved Excel workbooks, extracted PDF invoice
data, and historical records. PDF is an extraction source requiring explicit
human verification, not a trusted structured format.

### 10.2 Import lifecycle

1. Select a file and import type.
2. Read without altering business data.
3. Map source fields to defined target fields.
4. Normalize and validate every row.
5. Detect duplicates using module-specific rules.
6. Present a preview with accepted, warning, and rejected rows.
7. Require confirmation and permission.
8. Commit transactionally through services and repositories.
9. Roll back the batch on fatal failure.
10. Record batch, row outcomes, actor, source checksum, and errors.

Imports never write directly to production tables from a UI parser.

### 10.3 Export lifecycle

Exports state their scope, filters, format, destination, and record count.
They use deterministic ordering, escape data safely, do not overwrite without
confirmation, and record material business exports in audit history.

## 11. Testing and acceptance

### 11.1 Automated tests

- Model and validation unit tests.
- Repository CRUD, query, constraint, and transaction tests.
- Service permission, numbering, transition, calculation, and rollback tests.
- End-to-end workflow tests from lead conversion through payment and
  maintenance using temporary databases.
- Migration tests from every supported schema version.
- Import preview, duplicate, rollback, and audit tests.
- Export format and numeric correctness tests.
- Module discovery, host lifecycle, navigation, and responsive UI regression
  tests.
- Backup inclusion and recovery tests for new storage.
- Database integrity and foreign-key checks.

### 11.2 Manual verification

Manual acceptance covers application launch, module navigation, minimum-size
layout, all appearance modes, editors, dialogs, keyboard focus, tables,
long-running operations, cancellation, generated documents, printing, and
the complete business workflow with representative data.

### 11.3 Definition of complete

A module is complete only when:

- Its business workflow operates end to end.
- Validation, permissions, audit, archive, search, notifications, imports,
  exports, documents, and related-module integration are addressed where
  applicable.
- Repository, service, workflow, migration, and regression tests pass.
- Syntax, imports, application launch, module smoke tests, and database
  integrity checks pass.
- Production data and backup/recovery compatibility are preserved.
- Visible behavior is manually accepted.
- Documentation matches the implemented system.

## 12. Future implementation roadmap

### Phase 1: data and CRM foundation

1. Introduce versioned migrations and schema verification.
2. Correct CRM foreign keys, site/address normalization, indexes, archive
   fields, audit fields, and numbering foundations.
3. Add CRM repository/service tests.
4. Deliver customer, contact, address, and site master-detail editors and
   customer timeline.

### Phase 2: leads, visits, and quotations

1. Implement lead ownership, stages, follow-up, activities, and conversion.
2. Implement visit booking, inspection evidence, documents, and photos.
3. Implement products, services, labour items, pricing, and suppliers.
4. Implement quotation revisions, calculations, issue, expiry, acceptance,
   templates, and PDF generation.

### Phase 3: operations

1. Generate work orders from accepted quotations.
2. Implement employees, subcontractors, teams, skills, and availability.
3. Implement scheduling and conflict validation.
4. Implement job cards, actual labour/materials, checklists, signatures,
   documents, photos, completion, and site history.

### Phase 4: finance

1. Implement invoice and credit-note numbering and lifecycle.
2. Generate billing from authorised work.
3. Implement payments, allocations, reversals, and customer ledger.
4. Implement statements, aged balances, and financial exports.

### Phase 5: after-sales and marketing

1. Implement installed assets, maintenance plans, recurring work, and
   maintenance notifications.
2. Implement warranty coverage, expiry, claims, and resulting work.
3. Extend Communications with consent, segmentation, suppression,
   unsubscribe, campaigns, and templates without duplicating mailbox
   intelligence.

### Phase 6: oversight and hardening

1. Implement operational, sales, finance, maintenance, and audit reports.
2. Implement permission-aware actionable dashboards.
3. Complete Administration, Settings, global search, notification delivery,
   import/export oversight, and role management.
4. Verify performance, backup/recovery, migration safety, accessibility,
   documentation, and the complete integrated workflow.

Each phase is divided into frozen, reviewable sprints. A later phase does not
justify bypassing incomplete validation, migrations, tests, audit, permissions,
or recovery work in an earlier dependency.

## 13. Governance

This document describes the approved project direction. Existing frozen
architecture remains authoritative unless formally revised. Planned sections
define expected architecture but do not claim implementation.

The following documents remain binding and are read before every sprint:

- `PROJECT_RULES.md`
- `DEVELOPMENT_STANDARDS.md`
- `DEVELOPMENT_SPECIFICATION.md`
- `SPRINT_PROCESS.md`
- `AI_WORKFLOW.md`
- `RECOVERY_PLAYBOOK.md`

If documents conflict, work stops for explicit resolution before code or
database changes are made. No sprint implementation becomes architecture
merely because code was written; approved specifications govern the code.
