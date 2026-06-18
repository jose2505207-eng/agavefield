# 🌵 Agave Field

**Agave Field** is an enterprise-style field operations workbook for agave agriculture.

It helps agronomists, field supervisors, and workers plan, assign, execute, review, and trace agricultural work in a structured way.

The goal is simple:

> Make field operations feel as organized and reliable as Excel, but easier to use, mobile-friendly, auditable, and ready for real agricultural traceability.

Agave Field is designed for teams that need to know:

- What work was planned
- Who was assigned
- Where the work happened
- What products were used
- What evidence was collected
- What still needs review
- What was approved
- What changed over time
- What the carbon footprint estimate looks like

This project started as a human-centered field record system for agave operations in Jalisco, Mexico, and is evolving into a production-ready field operations platform.

---

## Demo Login

The app includes a demo account so the workflow can be tested immediately.

```txt
Username: DEMO
Password: DEMO
```

Demo mode includes realistic sample data for:

- Organization
- Seasons
- Ranches / farms
- Lots / plots
- Activities
- Products
- Workers
- Evidence rules
- Carbon factors
- Work orders
- Review queue
- Reports

The demo account is useful for testing and presentations. It is not intended to replace real production authentication.

---

## Why Agave Field Exists

Agricultural field work is often managed through a mix of spreadsheets, WhatsApp messages, photos, paper notes, and memory.

That creates problems:

- Work orders can get lost.
- Photos are scattered across different phones and chats.
- Product usage is hard to trace.
- Supervisors may not know what is completed or still pending.
- Evidence is difficult to review later.
- Carbon footprint data is hard to calculate after the fact.
- Reports take too much manual work.
- Audits depend on incomplete information.

Agave Field brings all of that into one structured workflow.

It does not replace the agronomist.

It gives the agronomist a stronger operating system.

---

## Product Vision

Agave Field is inspired by the reliability of Excel, but designed for real field operations.

The app is built around an **Operations Workbook**, where every row represents a work order, planned activity, or field execution record.

Each record can include:

- Ranch or farm
- Lot or plot
- Season
- Activity
- Product
- Dose
- Assigned worker
- Due date
- Required evidence
- GPS status
- Weather snapshot
- Carbon footprint estimate
- Review status
- Approval history
- Audit trail

The main feeling of the product should be:

> “This is a serious operational system. Nothing gets lost.”

---

## Who This Is For

Agave Field is designed for:

- Agronomists
- Field supervisors
- Field workers
- Agave producers
- Distilleries
- Agricultural operations teams
- Sustainability teams
- Auditors
- Traceability and compliance teams

Although the first version is focused on agave agriculture, the workflow can be adapted to other crops and field operations.

---

## Core Workflow

Agave Field follows a simple operational cycle.

---

### 1. Set Up the Catalogs

Before creating work orders, the organization defines its master data.

Catalogs include:

- Ranches / farms
- Lots / plots
- Activities
- Products
- Workers / assignees
- Seasons
- Carbon factors
- Evidence rules

This keeps the system structured.

Instead of typing everything manually every time, users select from approved catalogs. This reduces errors and makes reporting cleaner.

Example:

A supervisor does not type “fertilization” in ten different ways. They select the approved activity from the catalog.

That makes the data easier to review, filter, export, and audit.

---

### 2. Create a Work Order

An agronomist or supervisor creates a work order from the Operations Workbook.

A work order can define:

- What activity needs to be done
- Where it needs to happen
- Which ranch and lot it belongs to
- Who is assigned
- What product is allowed
- What dose should be used
- What evidence is required
- Whether GPS is required
- Whether photos are required
- Whether review is required
- The estimated carbon footprint
- The due date

Example:

> Apply organic fertilizer in Lot A12 at Rancho Los Altos before Friday. Photos and GPS are required. The work must be reviewed before closing.

---

### 3. Assign a Worker

Each work order can be assigned to a worker.

Workers can have multiple contact methods:

- Email
- Phone
- Preferred contact method
- Preferred language

The system uses the worker’s preferred contact method when possible.

If the preferred method is missing, the system can fall back to another available method.

For example:

- If the worker prefers email and has an email address, the app prepares an email message.
- If the worker prefers phone or WhatsApp and has a phone number, the app prepares a phone-based message.
- If no real provider is configured, the app uses Demo Outbox.

---

### 4. Send the Work Order Link

Agave Field can generate an execution link for the assigned worker.

The link opens a mobile-friendly page where the worker can complete the task.

Example English message:

```txt
Hello Juan, you have a new Agave Field work order: Fertilization at Rancho Los Altos / Lot A12. Open your field task here: [execution link]
```

Example Spanish message:

```txt
Hola Juan, tienes una nueva orden de trabajo en Agave Field: Fertilización en Rancho Los Altos / Lote A12. Abre tu tarea de campo aquí: [enlace]
```

The message language can follow the worker’s preferred language.

---

### 5. Complete the Task in the Field

The worker opens the execution link on a phone.

The mobile execution page shows only the work order assigned to that worker.

The worker can complete the required steps and provide field evidence.

Evidence can include:

- Checklist completion
- Photos
- GPS location
- Notes
- Product usage
- Weather snapshot
- Completion status

The goal is to make field execution simple, clear, and hard to lose.

---

### 6. Submit for Review

After the worker completes the task, the work order can be submitted.

Submitted work appears in the **Review Queue**.

The agronomist or supervisor can then:

- Approve the work
- Reject the work
- Request corrections
- Review missing evidence
- Check photos and GPS
- Confirm product and dose information
- Review carbon footprint estimates

This creates a clean separation between field execution and agronomic approval.

---

### 7. Record the Audit Trail

Agave Field is designed with traceability in mind.

Important actions can be recorded in an audit trail, including:

- Work order created
- Work order edited
- Worker assigned
- Execution link generated
- Execution link sent
- Evidence submitted
- Review requested
- Work approved
- Work rejected
- Work closed
- Catalog record created
- Catalog record edited
- Catalog record archived

This helps answer important questions:

- Who changed this?
- When was it changed?
- What was changed?
- What was the previous value?
- Who approved the work?

This is important for operational discipline, compliance, sustainability reporting, and accountability.

---

### 8. Review Reports and Carbon Data

Agave Field includes reporting foundations for:

- Work orders by season
- Work orders by ranch
- Work orders by lot
- Pending activities
- Completed activities
- Product usage
- Evidence completeness
- Review status
- Carbon footprint totals

Carbon tracking is part of the core workflow.

Carbon estimates can be calculated based on:

- Activity type
- Product used
- Dose
- Area covered
- Carbon factor
- Operational assumptions

This allows the team to build field-level sustainability records as work is completed, instead of trying to calculate everything later.

---

## Main Modules

### Operations

The main workbook view.

This is where users can see, filter, search, and manage field work orders.

The Operations page is designed to feel like a professional spreadsheet-style control room.

---

### Work Orders

Used to create and manage specific field tasks.

Each work order can include:

- Assignment
- Activity details
- Product information
- Due dates
- Required evidence
- Status
- Review rules

---

### Catalogs

Catalogs are the master data of the system.

They keep the app clean, structured, and consistent.

Catalogs include:

- Ranches / farms
- Lots / plots
- Activities
- Products
- Workers / assignees
- Carbon factors
- Evidence rules
- Seasons

Each catalog supports a structured workflow such as:

- View records
- Search records
- Add records
- Edit records
- Archive records
- Show archived records
- Validate required fields

---

### Evidence

Evidence stores proof of field execution.

Evidence can include:

- Photos
- GPS location
- Notes
- Weather snapshot
- Signatures
- Documents

The purpose is to create reliable field history.

---

### Review Queue

The Review Queue shows submitted work that needs approval.

This helps agronomists focus on what needs attention instead of searching through messages, spreadsheets, and photo galleries.

---

### Reports

Reports help the team understand what happened across the operation.

Reports can show:

- Activity totals
- Product usage
- Pending work
- Completed work
- Evidence completeness
- Review progress
- Carbon estimates

---

### Carbon

The Carbon module helps estimate and review the environmental footprint of field activities.

This is especially important for agricultural traceability, sustainability programs, and future reporting requirements.

---

### Settings

Settings allow the organization to manage configuration such as:

- Organization name
- User profile
- Language preference
- Timezone
- Default season
- Integration status
- Demo/live mode visibility
- API configuration foundations

---

## Language Support

Agave Field includes a foundation for English and Spanish.

The goal is to make the app usable for teams where supervisors, agronomists, and field workers may prefer different languages.

Supported language foundation:

- English
- Spanish

---

## Worker Contact System

Each worker can have multiple contact methods.

Worker fields can include:

- Name
- Role
- Email
- Phone
- Preferred contact method
- Language
- Status
- Notes

The system decides how to prepare the work order link based on the worker’s available contact information.

Priority example:

1. Use the preferred contact method.
2. If the preferred method is missing, fall back to another available method.
3. If no real provider is configured, create a Demo Outbox message.

---

## Demo Outbox

The Demo Outbox is used when real email, WhatsApp, or SMS providers are not configured.

Instead of failing, the app creates a preview of the message.

This allows users to:

- Copy the message
- Copy the execution link
- Test the workflow
- Understand what would be sent in production

This keeps demo mode honest.

The app does not pretend to send real messages when no provider is connected.

---

## Demo vs Production

### Demo Mode

Demo mode is useful for testing, presentations, and early feedback.

It may use:

- Seeded demo data
- Demo login
- Mock integrations
- Demo Outbox
- Local or session persistence
- Placeholder weather
- Placeholder evidence storage

### Production Mode

Production mode should use:

- Real authentication
- Real database
- Secure file storage
- Real email, WhatsApp, or SMS provider
- Real weather API
- Secure API key management
- Role-based access control
- Production audit logging
- Backup and monitoring

The current demo can run without production integrations.

When keys are missing, the app should fall back to demo behavior instead of crashing.

---

## Production Integrations

Agave Field is designed to support production integrations such as:

- Supabase / Postgres database
- Object storage for photos
- Weather API
- Email provider
- WhatsApp Cloud API
- SMS provider
- Authentication provider
- Role-based access control
- Secure server-side API key storage

---

## Environment Variables

Create a `.env.local` file based on `.env.example`.

Example:

```txt
NEXT_PUBLIC_APP_URL=

DATABASE_URL=

NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

WEATHER_API_KEY=

EMAIL_PROVIDER_API_KEY=

WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=

TELEGRAM_BOT_TOKEN=

ENCRYPTION_KEY=
```

Important:

Do not commit real secrets to GitHub.

Production secrets should be stored securely in the deployment platform, such as Vercel environment variables.

---

## Local Development

Install dependencies:

```bash
npm install
```

Run the development server:

```bash
npm run dev
```

Open the app:

```txt
http://localhost:3000
```

Build the app:

```bash
npm run build
```

Run linting:

```bash
npm run lint
```

Run type checking, if available:

```bash
npm run typecheck
```

Run tests, if available:

```bash
npm run test
```

---

## Suggested Demo Flow

Use this flow to test the app from beginning to end.

### Step 1: Log In

Use:

```txt
DEMO / DEMO
```

### Step 2: Review the Catalogs

Open Catalogs and review:

- Ranches
- Lots
- Activities
- Products
- Workers
- Seasons
- Evidence Rules
- Carbon Factors

Add or edit a few records.

---

### Step 3: Create or Open a Work Order

Go to Operations or Work Orders.

Create or select a work order.

Assign a worker.

Make sure the worker has an email or phone number.

---

### Step 4: Send the Work Order Link

Use the Send Link action.

If no real provider is configured, check the Demo Outbox.

Copy the generated execution link.

---

### Step 5: Open the Worker Link

Open the execution link.

Complete the work order as if you were the field worker.

Add notes and required evidence placeholders.

Submit the work.

---

### Step 6: Review the Submission

Go to the Review Queue.

Approve, reject, or request correction.

---

### Step 7: Check Reports and Carbon

Review the Reports and Carbon modules to see operational summaries and carbon estimates.

---

## Current Status

Agave Field currently focuses on the production-demo workflow.

The goal is to make the product usable with demo data while keeping a clean path toward real production deployment.

Current foundations include:

- Enterprise-style app shell
- Operations workbook
- Catalog system
- Demo login
- Demo data
- Worker contact model
- Work order link flow
- Evidence requirements
- Review queue foundation
- Carbon tracking foundation
- Settings foundation
- English/Spanish localization foundation
- Demo Outbox fallback
- Audit trail foundation

---

## Safety Notes

Agave Field is an operational support system.

It does not replace professional agronomic judgment.

The app helps organize field work, evidence, review, and traceability, but final decisions should remain with qualified agronomists and responsible supervisors.

Important safety principles:

- Human review is required for critical decisions.
- Field workers should only execute approved work orders.
- Product usage should follow legal, agronomic, and safety requirements.
- The system should not recommend unsafe treatments or dosages.
- Evidence and audit history should be preserved.
- Production secrets should never be stored in public code.

---

## AI Position

The core product does not require AI to be useful.

The current foundation is based on:

> Human Work Order + Human Evidence + Human Review + Structured Records = Reliable Agave History

AI image analysis, automated recommendations, or advanced copilots can be added later, but they should not weaken the core workflow.

The product must remain useful even with no AI API key.

Future AI features may include:

- Photo classification
- Field note summarization
- Evidence quality checks
- Pest or disease detection support
- Carbon reporting assistance
- Predictive lot risk scoring

Any AI feature should support the agronomist, not replace them.

---

## Production Checklist

Before using Agave Field as a real production system, the following should be completed:

- Connect production database
- Add real authentication
- Add role-based access control
- Secure server-side secret storage
- Connect object storage for photos
- Connect email provider
- Connect WhatsApp or SMS provider
- Connect weather provider
- Harden execution link security
- Add token expiration and revocation
- Add full audit retention
- Add backup/export strategy
- Add monitoring and error tracking
- Add privacy and security review
- Add real organization onboarding
- Add production data migration strategy

---

## Design Philosophy

Agave Field is not designed to be flashy.

It is designed to be trusted.

The interface should feel:

- Clear
- Dense
- Calm
- Serious
- Structured
- Operational
- Reliable

The goal is not decoration.

The goal is control.

A field team should be able to open Agave Field and understand what is happening, what is pending, what needs review, and what has already been approved.

---

## Future Roadmap

Possible future features include:

- Real-time field worker updates
- Offline-first mobile execution
- Photo upload and compression
- GPS map view
- Weather automation
- WhatsApp Cloud API integration
- Email notifications
- Advanced carbon reporting
- Excel import/export
- PDF reports
- AI-assisted field notes
- AI photo analysis for evidence review
- Multi-organization support
- Advanced permissions
- Audit-ready compliance exports
- Satellite / NDVI integration
- Drone imagery upload
- Predictive lot risk scoring

---

## Built With

Agave Field is designed around a modern web stack.

Possible stack components include:

- Next.js
- TypeScript
- React
- Tailwind CSS
- Zod validation
- Supabase-ready architecture
- Vercel deployment
- Modular repository/data layer

---

## Project Mission

Agave Field exists to give agricultural teams a stronger operating system.

Not more chaos.

Not more scattered messages.

Not another spreadsheet that slowly breaks.

A clean, structured, traceable workflow for the field.

From planning to execution.

From evidence to review.

From carbon estimates to operational reports.

One field record at a time.