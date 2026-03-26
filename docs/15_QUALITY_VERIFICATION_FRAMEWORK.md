# QUALITY VERIFICATION FRAMEWORK — Output Standards Per Feature

> This document defines the **minimum acceptable output quality** for every feature in the v2.0 system. Each feature has clear pass/fail criteria. If any feature doesn't meet its defined standard, it is not done.

---

## Verification Method Key

| Code | Method |
|---|---|
| **AT** | Automated Test (pytest) |
| **BT** | Browser Test (visual inspection) |
| **API** | API call with curl / Postman / test client |
| **DP** | Data Pattern verification (query database, check patterns) |
| **UX** | User Experience standard (would a real user find this acceptable?) |

---

## 1. DATABASE (Phase 1)

| Feature | Pass Criteria | Method | Quality Level |
|---|---|---|---|
| Schema creation | All 14 tables created on fresh init. `sqlite_master` query returns 14 table names. | AT | Binary pass/fail |
| Location data | 5 locations exist with correct names, capacities, addresses, coordinates, pricing. | AT | Check every field |
| Foreign keys | All FK relationships enforced. Inserting a booking with nonexistent user_id fails. | AT | Must raise error |
| WAL mode | Database operates in WAL mode. Concurrent API reads don't block serial writes. | AT | Verified under load |
| Upsert status | `update_status()` correctly computes available_slots, utilization_%, is_full for all locations. Edge cases: count=0, count=max, count>max (rejected). | AT | 5 test cases per location |
| Event logging | Events stored with correct parking_id, event_type, occupancy_after, timestamp. Invalid event_type rejected by CHECK constraint. | AT | Validated |

**Total Phase 1 Tests Required: ≥15**

---

## 2. SYNTHETIC DATA (Phase 2)

| Feature | Pass Criteria | Method | Quality Level |
|---|---|---|---|
| Volume | ≥40,000 total events across all 5 locations. | DP | count(*) ≥ 40,000 |
| Duration | 30 days of data per location. | DP | min(date) to max(date) ≥ 30 |
| Pattern realism: Corporate | Weekday occupancy peaks at 85-95% between 09-17. Weekend stays below 10%. | DP | Query hourly averages, verify ranges |
| Pattern realism: Mall | Weekend occupancy 20-30% higher than weekday. Evening peak (18-20) higher than morning. | DP | Compare weekday vs weekend averages |
| Pattern realism: Airport | Never below 30% occupancy (24/7 operation). Dual peaks at 07-09 and 18-20. | DP | Query min occupancy ≥ 30% of capacity |
| Pattern realism: University | Dead on weekends (<10%). Sharp ramp 07-09 on weekdays. | DP | Weekend avg below 10% |
| Pattern realism: Hospital | Never truly empty (>10% always, even at 3 AM). OPD peak 09-12. | DP | Query min occupancy > 10% |
| Event surges | At least 3 "special event" days per location where occupancy exceeds normal peak by 20%+. | DP | Identify outlier days, verify count ≥ 3 |
| Capacity bounds | No event ever has occupancy_after > max_capacity for that location. No negatives. | AT | Full table scan |
| Day consistency | Total entries ≈ total exits per day (±2 for end-of-day residual). | DP | GROUP BY date, check balance |

**Total Phase 2 Tests Required: ≥10**

---

## 3. AI / ML ENGINE (Phase 3)

| Feature | Pass Criteria | Method | Quality Level |
|---|---|---|---|
| Per-location models | 5 separate trained models exist (one per location). Each has MAE < 2.0 vehicles. | AT | Train + evaluate each |
| Random Forest vs Linear | Random Forest MAE < Linear Regression MAE for at least 3/5 locations (non-linear patterns). | AT | Compare MAE values |
| Prediction clamping | All predictions clamped to [0, location_max_capacity]. No negatives, no exceeding capacity. | AT | Predict all 24 hours, check bounds |
| Peak detection | Peak hours identified correctly per location. Corporate peak ≠ Mall peak ≠ Airport peak. | AT | Verify distinct peaks |
| Recommendation messages | 6 utilization tiers produce correct message category. `get_recommendation(90%)` returns "urgent" category. | AT | Test each tier boundary |
| Anomaly detection | Z-score flags occupancy > 2σ from mean for that hour. Injecting a 3 AM spike at corporate lot triggers alert. | AT | Inject anomaly, verify detection |
| Best time finder | For each location, returns the hour with lowest predicted occupancy. Result is a valid hour (0-23). | AT | Verify output |
| Chatbot: availability query | "Is the mall full?" → Response contains location name, current count, capacity, availability status. | AT | Assert key fields in response |
| Chatbot: prediction query | "Will airport be full tomorrow at 8 AM?" → Response contains predicted occupancy for that hour. | AT | Assert prediction value |
| Chatbot: unknown query | "What is the meaning of life?" → Response is graceful fallback, not a crash. | AT | Assert fallback response |

**Total Phase 3 Tests Required: ≥15**

---

## 4. USER SYSTEM + BOOKING + PAYMENTS (Phase 4)

| Feature | Pass Criteria | Method | Quality Level |
|---|---|---|---|
| Registration | POST /api/auth/register with valid fields → 201, user created. Duplicate email → 409 error. | AT | Two test cases |
| Login | POST /api/auth/login with correct credentials → 200, token returned. Wrong password → 401. | AT | Two test cases |
| Profile | GET /api/auth/profile with valid token → user data. Invalid token → 403. | AT | Two test cases |
| Create booking | POST /api/bookings/create with valid location + time → 201, booking created. Full lot → 409 error. | AT | Two test cases |
| View bookings | GET /api/bookings/my returns list of user's bookings. Empty list for new user. | AT | One test case |
| Cancel booking | DELETE /api/bookings/:id → booking status changes to CANCELLED. | AT | One test case |
| Process payment | POST /api/payments/process with booking_id → payment record created, status PAID. | AT | One test case |
| Payment history | GET /api/payments/history → list of user's payments with amounts and dates. | AT | One test case |

**Total Phase 4 Tests Required: ≥12**

---

## 5. FRONTEND (Phase 5)

| Feature | Pass Criteria | Method | Quality Level |
|---|---|---|---|
| Landing: Hero | Hero section fills viewport. Headline visible within 1 second. Gradient background animates. | BT | Screenshot verification |
| Landing: Stats | 4 counters animate from 0 to target when scrolled into view. Animation duration ~2s. | BT | Visual |
| Landing: Features | 6 feature cards render in 3×2 grid. Each has icon, title, description. Hover lifts card. | BT | Visual + interaction |
| Landing: Locations | 5 location cards with live occupancy percentage. Color-coded (green/amber/red). | BT | Visual + data accuracy |
| Navigation | Navbar present on all pages. Active page highlighted. Links work. Mobile hamburger works. | BT | Click through all pages |
| Dark/Light toggle | Toggle switches all colors. No flicker. Preference saved to localStorage. | BT | Toggle + reload |
| Locations page | 5 location cards with: name, type badge, address, capacity, live occupancy, rate/hr, "View" + "Book" buttons. | BT | All fields populated |
| Dashboard page | Loads for specific location. All 7 cards show data for THAT location (not global). WebSocket updates. | BT | Select different location, verify data changes |
| AI Assistant | Chat interface renders. User can type. Response appears within 2 seconds. Quick-action buttons work. | BT | Send 3 different queries |
| Auth page | Login and Register forms render. Tab switching works. Validation on empty fields. | BT | Submit empty, submit valid |
| Profile page | Shows user name, email, vehicle plate, bookings list, payment history. | BT | Login → navigate to profile |
| Responsive | All pages work on mobile viewport (375px width). No horizontal scroll. Readable text. | BT | Resize browser to 375px |
| Performance | Page load < 3 seconds. No jank on scroll. Charts render within 1 second. | BT | Lighthouse / visual |

**Total Phase 5 Checks Required: ≥13**

---

## 6. API (Phase 6)

| Endpoint | Pass Criteria | Method |
|---|---|---|
| GET `/api/locations` | Returns array of 5 locations with all fields | AT |
| GET `/api/locations/:id` | Returns single location detail | AT |
| GET `/api/locations/:id/status` | Returns live status for specific location | AT |
| POST `/api/auth/register` | Creates user, returns token | AT |
| POST `/api/auth/login` | Returns token for valid credentials | AT |
| GET `/api/auth/profile` | Returns user data with token | AT |
| GET `/api/dashboard/:id/history` | Returns events for specific location | AT |
| GET `/api/dashboard/:id/predictions` | Returns prediction for specific location | AT |
| POST `/api/chatbot/query` | Returns AI response for text query | AT |
| POST `/api/bookings/create` | Creates booking | AT |
| GET `/api/bookings/my` | Returns user's bookings | AT |
| POST `/api/payments/process` | Creates payment record | AT |
| GET `/api/recommendations/:id` | Returns smart recommendation for location | AT |

**Total Phase 6 Tests Required: ≥13**

---

## SUMMARY

| Phase | Feature Area | Tests Required | Quality Standard |
|---|---|---|---|
| 1 | Database | ≥15 | All 14 tables functional, FK enforcement, edge cases |
| 2 | Data Generation | ≥10 | 40K+ events, 5 distinct patterns verified, surge events confirmed |
| 3 | AI/ML | ≥15 | Per-location models, chatbot responds to 10+ intents, anomaly detection works |
| 4 | User System | ≥12 | Full auth + booking + payment flow |
| 5 | Frontend | ≥13 | Landing page WOWs, 7 pages work, responsive, dark/light mode |
| 6 | API | ≥13 | All 20+ endpoints return valid JSON |
| **TOTAL** | | **≥78 tests** | **Production-grade verified** |

---

## VISUAL QUALITY BAR

The frontend design must meet this standard. If an evaluator opens the website, their reaction should be:

| Reaction | Quality Level | Acceptable? |
|---|---|---|
| "A student made this" | ❌ Reject | NO |
| "This is a decent project" | ⚠️ Mediocre | NO |
| "This looks professional" | ✅ Good | MINIMUM |
| "This could be a real product" | ✅✅ Excellent | TARGET |
| "This is better than most real parking apps" | ✅✅✅ Outstanding | IDEAL |

---

*Document Version: 1.0 | Date: 2026-03-26 | Author: Piyush Kumar*
