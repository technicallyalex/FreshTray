# Invoices and standalone mode — local preview

This development build adds invoicing and a standalone workspace. Nothing is automatically uploaded, emailed, or published.

## Work without FreshBooks

1. Quit any other FreshTray copy and open the local preview executable.
2. Open **Settings → FreshBooks connection** and turn **Standalone mode** on. A first-time user without a connection starts in this workspace already. Turn it off to use a saved FreshBooks connection; setup is available only in this Settings section.
3. Open **Business & local records**. Save your business name, email, address and default currency.
4. Choose **Client**, enter the client name, billing email and address, then save. Add projects, saved items and expenses as needed. Existing records can be selected and edited from the same dialog.
5. Log work from **Log time**, **Monthly hours**, or **Timer**. Local clients and projects appear there. No FreshBooks account or initial internet connection is needed.

Standalone mode disables automatic and manual update networking as well as FreshBooks background sync. Records remain encrypted for the current Windows account. Standalone records are separate from connected-account records and are not migrated or uploaded by connecting an account.

## Create, review and manage an invoice

1. Select **Invoices → New invoice**, then choose a client, issue/due dates, currency and optional purchase order.
2. Add manual lines, choose saved items, or select **Import unbilled entries**.
3. In the import review, choose a date range (or enter custom dates), projects, and expense mode. Set a bulk hourly rate when needed. Expenses keep their own amounts.
4. Choose Detailed, Grouped or Simple format, grouping and description details. Review the preview and total, then **Add to invoice**.
5. Check line quantities, rates, taxes, notes, terms and discount. **Save invoice** reserves imported sources against duplicate local billing and assigns a standalone invoice number when blank.
6. **Preview** displays the invoice document. **Export PDF** generates a local, paginated PDF without a provider request.

Grouping preserves monetary totals. A mixed-rate or fractional-hour group may be represented as one combined amount, with hours in its description, to avoid rounding the quantity into a different total. Review imported rates; unassigned time or unavailable rate information may start at zero.

The list supports number/client search and status/client filters. Unsaved edits are checkpointed locally; **Resume unsaved draft** returns to them. Starting or opening a different invoice asks before discarding a retained unfinished draft.

For standalone invoices, **Mark sent (local)** records your own delivery status, **Record payment** records money you already received, and **Archive invoice** hides the invoice while retaining it in encrypted storage. Recording a payment never charges a client. Archiving releases imported entries for reuse. Paid/partially paid invoices are read-only for invoice-content edits; previews and PDF exports remain available.

## Email through your own mail app

- **Email draft:** export a PDF first. This opens a `mailto:` draft addressed to the client, with subject/body filled in. **Attach the exported PDF yourself**, choose the sending account, review and send in your mail app.
- **Email file with PDF:** saves an `.eml` file with the PDF attached. Open it in a compatible email app. Some apps honor its unsent-draft and From fields; others open it as a message or use their default account. Check the recipient, attachment and sending account before sending.

FreshTray never sends email itself. The business email is used in the signature and email-file header; `mailto:` cannot reliably select a sending account or attach a file. A mail app/account still needs internet connectivity to deliver email, though some clients can queue drafts offline.

Exported PDFs and email files are ordinary, unencrypted documents at the location you choose. Treat them as client billing documents. The encrypted workspace is local to your Windows account; a portable executable does not make encrypted credentials or records portable between Windows users.

## Connect FreshBooks with the wizard

The five-step wizard offers standalone mode or explains developer-app creation, the registered HTTPS redirect, scopes, credentials, browser consent and the return URL. Credentials and tokens stay in the existing encrypted vault; no secrets are embedded in the build.

Use **Invoices → Setup wizard**, create or edit your FreshBooks developer app, and add the scopes shown. Copy the redirect URI exactly. Enter the client ID and secret, open sign-in, approve access, then paste the complete browser return URL. The localhost error page is expected in this manual HTTPS-return flow. Sign-in attempts expire after five minutes.

After connecting, select the intended business. In **Settings → FreshBooks connection**, use **Refresh account lists** for time tracking, or choose **Clients**, **Invoices**, **Estimates**, or **Payments** under **Refresh saved records**. If FreshBooks still denies access after adding permissions, revoke the old FreshBooks authorization and sign in again. Enter your business details before PDF or email export.

FreshBooks mode caches downloaded invoices, catalogs and per-client unbilled entries. Opening the invoice import view loads saved entries and checks for updates for that client when connected. Access to other team members' time depends on your FreshBooks role.

Saving a connected-account invoice writes an encrypted local draft. **Sync saved drafts** explicitly creates or updates the invoices in FreshBooks. The confirmation warns that linked time/expenses may become billed there. This does not email clients. Existing line IDs, source linkage and tax metadata are retained, and updates send all retained invoice lines.

Changed server versions block overwrite. Uncertain writes remain under Review and are not retried automatically. Check FreshBooks before using **I checked FreshBooks: retry**; retrying an invoice that already exists can duplicate it. **Keep local; do not sync** retains the invoice without another provider write. A provider total mismatch blocks PDF export until the calculation is reviewed.

In **Payments**, use the calendar button to choose the received date or type it directly. New connected payment records, corrections, and removals save locally and start syncing immediately. If FreshBooks is unreachable before submission, the change stays saved and retries automatically. If FreshBooks may have received it, review the payment history before trying again. Payments queued by older builds still require explicit sync.

## Verification and limits

Automated checks use fictional records and fake transports, not live customer invoices. Tests cover decimal arithmetic, duplicate-source reservations, local timer receipts, client/currency separation, conflict/ambiguous-write handling, standalone operation with sockets blocked, PDF/email output and draft recovery. PDF samples include a multi-page invoice and were rendered for visual inspection.

Actual FreshBooks acceptance of linked invoices, account-specific billing/tax behavior, OAuth consent in your account and email-client interoperability still need intentional user testing. No live customer data was written during development. Monetary calculations currently use two-decimal rounding; verify jurisdiction-specific tax treatment and currency precision before issuing an invoice.

References: [Invoices](https://www.freshbooks.com/api/invoices), [expenses](https://www.freshbooks.com/api/expenses), [time entries](https://www.freshbooks.com/api/time_entries), [OAuth](https://www.freshbooks.com/api/authentication), and [mailto standard](https://www.rfc-editor.org/rfc/rfc6068.txt).

## Business logo

Open **Business & local records → Business details → Choose logo** and select a PNG or JPEG. The app keeps a resized copy in local encrypted storage and embeds it in invoice previews, PDFs and attached email drafts. The original image file is no longer required. Use Change logo or Remove logo to update it. Existing saved invoice snapshots retain their branding; changing the logo with an editable invoice open also applies it to that draft. Save the invoice to keep that change. This does not upload a logo to FreshBooks.


## Connected business details and logo

Opening Invoices while connected refreshes invoice data, business name/address/contact details and the logo supplied by the most recently updated invoice presentation. Refresh invoices to retry. These are cached per connected account in encrypted storage for offline use; standalone business details remain separate. FreshBooks does not document a separate default-brand logo read endpoint, so accounts without an invoice logo can use Choose logo. Existing connections may need reauthorization with user:business:read and user:uploads:read using the setup wizard. Failed logo refreshes retain the cached image. Only same-origin FreshBooks upload-image URLs are fetched; no external image links or redirects receive account credentials.

Invoice list descriptions are single-line previews. The expanded editor wraps full descriptions and keeps invoice rows separated. Its preferred size is 1220 by 980, limited to the screen's available work area.

API references: https://www.freshbooks.com/api/systems and https://www.freshbooks.com/api/invoice_presentation_attachments


## Window and setup QA

Automatic panel sizing preserves the window's current center, shifting as needed to keep the window inside the monitor work area. Docked windows retain their taskbar-edge alignment. The setup wizard uses a fixed-width scrolling viewport and restores your saved redirect URI when opened.


## Settings-only setup wizard

The connection setup wizard is available only in Settings → FreshBooks connection. It has four pages: developer app, permissions, sign-in, and verification. Standalone mode is a separate Settings toggle. Switching it retains both workspaces and does not upload local records. The wizard loads one page at a time, clears secret/return fields when closed, and arms local stall capture for page navigation as well as opening.

The main window centers on first launch. Subsequent launches restore its last saved position; disconnected monitors or screen changes are handled by moving it back into the available work area. Docked mode keeps its taskbar-edge alignment.


## Idle connection-panel fix

Window fitting, initial placement and position saving use regular application event timers rather than the animation clock. Panel sizes use a bounded 240 ms cubic tween around the current center, driven by the application event loop. The resize cover was removed, and Settings measures its content independently of window height. This prevents a paused animation clock from leaving the connection panel stuck in a resizing state. Local regression coverage includes quiet idle, frequent background state changes and packaged wizard/idle tests.


The invoice browser virtualizes its rows and unloads inactive views. Account downloads commit in one background transaction, while UI state reads copy only exposed data. These changes prevent a large cached invoice history from blocking panel navigation.
