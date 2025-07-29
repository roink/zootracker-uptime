# Zoo Tracker – UI Page‑Flow & Layout Spec

> **Purpose** – A concise, implementation‑ready reference of every screen in the MVP web app (also 100 % reusable for mobile). For each page you’ll find **what’s shown**, **actionable controls**, and **navigation outcome** so that designers & developers share the same map.

---

## 0 · Global Navigation & UI Conventions

* **Top nav‑bar** (desktop) / **bottom tab‑bar** (mobile)

  * **Home** 🏠 (Dashboard/Feed)
  * **Zoos** 🏛️ (directory)
  * **Animals** 🐾 (directory)
  * **Add** ➕ (fab / opens quick‑add menu)
  * **Badges** 🎖️
  * **Profile** 👤
* **Floating "➕" Quick‑Add** (every signed‑in screen)

  * *Log Zoo Visit* → *New Visit* modal
  * *Log Animal Sighting* → *New Sighting* modal
* **Auth‑guard** – unauthenticated users are routed to **Landing / Login**.
* **Breadcrumbs** on desktop, **back‑arrow** on mobile.

---

## 1 · Landing / Marketing (Signed‑out)

| Section     | Contents                                                     |
| ----------- | ------------------------------------------------------------ |
| Hero        | App tagline, screenshot collage                              |
| Value Props | 3‑column icons (Track Visits, Earn Badges, Discover Animals) |
| CTA Buttons | **"Sign Up"** → *Register* · **"Log In"** → *Login*          |

---

## 2 · Register

* **Fields** · Name, E‑mail, Password, Confirm Password
* **Buttons**

  * **Create Account** → if success: *Dashboard*
  * **Back to Log In** → *Login*

---

## 3 · Login

* **Fields** · E‑mail, Password
* **Buttons**

  * **Log In** → *Dashboard* (store JWT)
  * **Forgot Password?** → *Reset Password* (future)
  * **Sign Up** → *Register*

---

## 4 · Dashboard / Home Feed

| Region                | What you see                                            |
| --------------------- | ------------------------------------------------------- |
| Stats Bar             | *Zoos visited*, *Animals seen*, current *Badge* count   |
| Activity Feed         | Latest visits & sightings from **you** (later: friends) |
| Achievements Carousel | Recently earned badges                                  |
| Quick Actions         | ➕ **Log Sighting**                                  |

### Buttons & Flow

* **Log Sighting** → *New Sighting*
* Tap feed item (zoo card) → *Zoo Detail*
* Tap feed item (animal chip) → *Animal Detail*

---

## 5 · Zoo Directory

* **Search box**, region/continent filter, *Visited* toggle
* **Zoo cards list** (name, city, tiny map pin, visited badge)
* **Buttons**

  * Card click or **Details** → *Zoo Detail*

---

## 6 · Zoo Detail

`/zoos/{id}`

| Block                    | Elements                                                 |
| ------------------------ | -------------------------------------------------------- |
| Header                   | Banner photo, Name, Address, mini‑map (pin)              |
| Visit Status             | Visited? ☐ Yes/✘ No (auto)                               |
| Animals Tab              | Table – animal name, *Seen?* pill, **➕** sighting button |
| Upcoming Events (future) | Placeholder                                              |

### Buttons & Flow

* **➕** beside animal row → *New Sighting* (zoo & animal pre‑filled)
* Click animal row → *Animal Detail*

---

## 7 · Animal Directory

* **Search box**, category chips (Mammal, Bird…)
* **Animal cards grid** (photo, common & scientific name, seen badge)
* **Buttons**

  * Card click → *Animal Detail*

---

## 8 · Animal Detail

`/animals/{id}`

| Block        | Elements                                        |
| ------------ | ----------------------------------------------- |
| Header       | Hero image, common + Latin name, category badge |
| Status       | Seen ✔️ / Not seen 🚫, first‑seen date          |
| Gallery      | user photos (horizontal scroll)                 |
| Where to See | Table of zoos (distance from user if available) |

### Buttons & Flow

* **Log Sighting** (top)

  * If user location on: defaults nearest zoo else lets user choose → *New Sighting*
* Zoo row click → *Zoo Detail*
* **Add to Wishlist** (future) → updates DB, stays

---

## 9 · New Visit (Modal / Stand‑alone `/visits/new`)

* **Fields** · Zoo (select), Date (default today), Notes
* **Buttons**

  * **Save Visit** → POST `/visits`, then route to *Zoo Detail* (if came from zoo) else *Dashboard*
  * **Cancel** → previous page

---

## 10 · New Sighting (Modal / `/sightings/new`)

* **Fields** · Zoo (select), Animal (select), Date+Time (now default), Photo upload, Notes
* **Buttons**

  * **Save Sighting** → POST `/sightings`, then to *Animal Detail*
  * **Cancel**

---

## 11 · Achievements

* **Earned Badges grid** (colored)
* **Locked Badges grid** (grey)
* **Buttons**

  * Tap badge → Badge Detail popup (shows criteria, award date)

---

## 12 · Map / Recommendations

* **Search animal** autocomplete
* **Interactive map** (markers = zoos that host animal)
* **Sidebar list** sorted by distance
* **Buttons**

  * Marker click or list row → *Zoo Detail*
  * **Use My Location** toggle (browser geolocation)

---

## 13 · Profile

| Block             | Elements                                                      |
| ----------------- | ------------------------------------------------------------- |
| Avatar & name     | edit icon                                                     |
| Stats             | Cards: Animals Seen, Zoos Visited, Badges                     |
| Sightings Gallery | masonry grid                                                  |
| Visit Timeline    | chronological list                                            |
| **Buttons**       | **Edit Profile** → *Profile Edit* · **Settings** → *Settings* |

---

## 14 · Profile Edit

* Fields: display name, avatar upload
* **Save** → *Profile*
* **Cancel** → *Profile*

---

## 15 · Settings

* Toggles: Public profile, Email notifications, Dark mode
* **Change Password** (future)
* **Log Out** → clear auth, route to *Landing*

---

## 16 · Forgot / Reset Password (future placeholder)

---

### Appendices

* **Modal vs. page** – For desktop we prefer modals for quick add; on mobile they are full‑screen pages but keep same route names.
* **State after save** – on success, always update client‑side stores (Redux/React Query) so dashboards reflect instantly.
* **Error states** – show toast + keep user on form.

---

© 2025 Zoo Tracker Product Design

