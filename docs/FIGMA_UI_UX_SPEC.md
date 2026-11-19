# AI Foodie UI/UX blueprint for Figma

## Product frame

Design for a responsive food ordering and restaurant operations product. Desktop dashboards use a 1440 × 1024 frame; customer mobile flows use 390 × 844. Keep map and kitchen actions usable on touch screens. The four roles share the same design system and status language.

## Personas

| Persona | Goals | Friction to solve | Key success measure |
|---|---|---|---|
| Customer: Ananya, 28, Bengaluru | Find safe meals, order quickly, know where the rider is | Allergy uncertainty, unclear ETA | Confident checkout and visible live progress |
| Restaurant Admin: Rohan, 36 | Manage menu, sales, stock, and service quality | Switching between disconnected tools | Exceptions and performance visible at a glance |
| Kitchen Staff: Meera, 31 | Prepare the right orders in the right sequence | Rush periods, unclear modifiers | Low missed-item rate and fast status updates |
| Delivery Partner: Vikram, 25 | Accept work, navigate pickup/drop, share location | Poor connectivity and battery use | Clear next action and reliable route state |

## End-to-end journey map

| Stage | Customer | Restaurant/Admin + Kitchen | Delivery partner | Product response |
|---|---|---|---|---|
| Discover | Filter cuisine, diet, allergens | Review menu availability | Set availability online | Recommendation cards explain dietary matches |
| Decide | Open menu, inspect item details | Update stock and item status | Wait for assignment | Allergy notes remain visible through cart |
| Checkout | Confirm address and payment | Receive prioritized ticket | Receive nearest eligible assignment | Confirmation includes prep and travel estimate |
| Prepare | Watch progress | Kitchen accepts, prepares, marks ready | Navigate to restaurant | Shared order status and timestamped updates |
| Deliver | Follow map and ETA | Monitor delay and inventory alerts | Share GPS and confirm handoff | WebSocket location moves rider marker and route |
| Complete | Rate and reorder | Review sales and service metrics | Review earnings and availability | Receipt, feedback, and delivery record |

## Dashboard wireframes

### Customer dashboard and tracking

Header: logo, delivery address selector, search, cart, account. Main content: recommendation rail, category chips, restaurant cards. Restaurant detail: hero image, cuisine/rating/delivery metadata, menu categories, item cards with dietary and allergen labels. Checkout: order summary, address, payment choice, allergy reminder, primary place-order action. Tracking screen: status and ETA panel above a 60/40 split of order timeline and map; map includes restaurant, destination, rider, route, and accessible status text. Mobile collapses to map followed by a bottom-sheet order summary.

### Restaurant admin

Persistent left navigation: Overview, Orders, Menu, Inventory, Analytics, Settings. Header: restaurant selector, date range, alerts, profile. Overview: four metric cards, sales trend, order status distribution, low-stock list. Orders: searchable/filterable table with status, priority, age, and detail drawer. Inventory: stock table with level indicator and restock action. Analytics: revenue and best-selling items with date controls. Keep destructive actions in confirmation dialogs.

### Kitchen staff

Header: kitchen name, online state, active order count, sound toggle. Main canvas: three responsive columns for Confirmed, Preparing, Ready. Each order card shows priority, elapsed time, promised time, item quantities, modifiers, allergy warning, and one prominent next-state action. At tablet width use two columns; on phones use status tabs. Highlight overdue orders with both color and text.

### Delivery partner

Header: availability switch, connection status, profile/earnings. Main area: assigned delivery cards with pickup/drop addresses, customer call link, payout, notes, and action progression. Map card shows pickup, customer, rider, and route. Provide `Start live GPS`, a clear permission-denied message, and a demo simulation action only in demo builds. On narrow screens use a map-first layout and sticky primary action.

## Design tokens

| Token | Value | Use |
|---|---|---|
| Brand orange | `#F97316` | Primary actions, active route |
| Ink | `#172033` | Main text |
| Secondary text | `#64748B` | Labels and supporting text |
| Success | `#15803D` | Ready, delivered, safe confirmation |
| Warning | `#B45309` | Delays and attention states |
| Danger | `#B91C1C` | Errors, allergy warning, destructive action |
| Canvas | `#F5F7FA` | Page background |
| Surface | `#FFFFFF` | Cards and panels |
| Border | `#E2E8F0` | Dividers and input edges |

Typography: Plus Jakarta Sans for headings and UI, system sans-serif fallback; body 16/24 px, labels 14/20 px, page title 28/36 px, card title 18/26 px. Use weights 400, 500, 600, 700. Spacing base 4 px: `space-1=4`, `space-2=8`, `space-3=12`, `space-4=16`, `space-6=24`, `space-8=32`, `space-12=48`. Radius: 8 px controls, 16 px cards, 24 px hero panels. Minimum touch target 44 × 44 px. Focus ring: 2 px `#2563EB` with 2 px offset.

## Components and states

Create variants for primary/secondary/quiet buttons, inputs, search, dietary chips, status badges, metric cards, order cards, empty states, toast, modal, and map legend. Each interactive component needs default, hover, focus, pressed, disabled, loading, and error states. Never use color as the only way to convey order status or food safety.

## Prototype linking instructions

1. Create pages `00 Foundations`, `01 Customer`, `02 Admin`, `03 Kitchen`, `04 Delivery`, and `05 Prototype`.
2. Build color/type/spacing styles first, then reusable controls and card components with variants.
3. Link Customer: Browse → Restaurant → Item detail → Cart → Address/payment → Confirmation → Tracking → Rating.
4. Link Admin: Overview → Orders → Order drawer; Overview → Inventory → Restock confirmation; Overview → Analytics.
5. Link Kitchen: Queue → Preparing → Ready; include overdue and allergy-warning branches.
6. Link Delivery: Assignment → Accept → Pickup → Live route → Delivered; create GPS denied and offline branches with retry actions.
7. Use Smart Animate for status changes and map marker movement; use dissolve for modal transitions. Keep transitions 150–250 ms and provide a reduced-motion alternative.
8. Add prototype hotspots only to visible controls, label each frame by role and state, and test all journeys at desktop, tablet, and mobile sizes.
