# 1AEO Unified Appearance Guide

## Current Implementation Status (Updated December 2024)

### Summary Dashboard

| Site | URL | Cross-Site Nav | Footer | Brand Colors | Status |
|------|-----|----------------|--------|--------------|--------|
| **Main Site** | www.1aeo.com | ✅ Complete | ❌ Basic | ✅ Dark + Green | **DONE** |
| **Metrics** | metrics.1aeo.com | ✅ Complete | ✅ Complete | ✅ Green | **DONE** |
| **AROI Validator** | aroivalidator.1aeo.com | ✅ Complete | ✅ Complete | ✅ Dark + Green | **DONE** |
| **RouteFluxMap** | routefluxmap.1aeo.com | ❌ Missing | ⚠️ Minimal | ✅ Dark + Green | Needs Work |

---

## Detailed Status by Site

### 1. metrics.1aeo.com ✅ IMPLEMENTED

**What's Working:**
- ✅ Cross-site navigation bar with 1AEO branding (dark header)
- ✅ Links to: Home, Metrics (active), AROI Validator, RouteFluxMap
- ✅ Unified footer with all site links + GitHub
- ✅ 1AEO brand footer text
- ✅ Green accent colors (#00cc66) replacing Bootstrap blue
- ✅ CSS variables for brand consistency

**Navigation Bar Content:**
```
1AEO | Home | Metrics (active) | AROI Validator | RouteFluxMap
```

**Footer Content:**
```
Metrics | AROI Validator | RouteFluxMap | GitHub
Part of 1st Amendment Encrypted Openness LLC
```

---

### 2. aroivalidator.1aeo.com ✅ IMPLEMENTED

**What's Working:**
- ✅ Full dark theme matching 1AEO brand (#121212 background)
- ✅ Cross-site navigation bar with 1AEO branding
- ✅ Links to: Home, Metrics, AROI Validator (active), RouteFluxMap
- ✅ Unified footer matching metrics.1aeo.com
- ✅ Green accent colors (#00ff7f)
- ✅ CSS variables for brand consistency

**Navigation Bar Content:**
```
1AEO | Home | Metrics | AROI Validator (active) | RouteFluxMap
```

**Footer Content:**
```
Metrics | AROI Validator | RouteFluxMap | GitHub
Part of 1st Amendment Encrypted Openness LLC
```

---

### 3. routefluxmap.1aeo.com ⚠️ PARTIAL

**What's Working:**
- ✅ Dark theme matching 1AEO brand
- ✅ Green accent color (`tor-green: #00ff88`)
- ✅ Link to metrics.1aeo.com in footer

**What's Missing:**
- ❌ No cross-site navigation bar
- ❌ No links to: Home (www.1aeo.com), AROI Validator
- ❌ No unified footer with all sites
- ❌ No 1AEO branding text

**Current Footer (minimal):**
```
Data from Tor Project • Metrics
```

**Needed Footer:**
```
Metrics | AROI Validator | RouteFluxMap | GitHub
Part of 1st Amendment Encrypted Openness LLC
```

---

### 4. www.1aeo.com ✅ IMPLEMENTED

**What's Working:**
- ✅ Dark theme (#121212 background)
- ✅ Green accent color (#00ff7f)
- ✅ Navigation includes: Home, Blog, Metrics, AROI Validator, RouteFluxMap, Contact

**Navigation:**
```
Home | Blog | Metrics | AROI Validator | RouteFluxMap | Contact
```

---

## Required Changes

### ~~Priority 1: www.1aeo.com~~ ✅ COMPLETED

RouteFluxMap link has been added to navigation.

---

### Priority 1: RouteFluxMap (Medium Effort)

**Repository:** `1aeo/routefluxmap`
**File to Update:** `src/layouts/Layout.astro`

**Add Cross-Site Navigation:**

```astro
---
// ... existing frontmatter ...
---

<!doctype html>
<html lang="en">
  <head>
    <!-- ... existing head content ... -->
    <style is:global>
      /* Add 1AEO Cross-Site Nav Styles */
      .aeo-cross-nav {
        background-color: #1e1e1e;
        padding: 10px 0;
        border-bottom: 1px solid rgba(0, 255, 127, 0.2);
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 100;
      }
      
      .aeo-cross-nav .aeo-nav-container {
        max-width: 1400px;
        margin: 0 auto;
        padding: 0 15px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 10px;
      }
      
      .aeo-cross-nav .aeo-nav-brand {
        color: #00ff88;
        text-decoration: none;
        font-weight: bold;
        font-size: 16px;
      }
      
      .aeo-cross-nav .aeo-nav-links {
        display: flex;
        gap: 20px;
        font-size: 14px;
      }
      
      .aeo-cross-nav .aeo-nav-links a {
        color: #cccccc;
        text-decoration: none;
        transition: color 0.2s ease;
      }
      
      .aeo-cross-nav .aeo-nav-links a:hover {
        color: #00ff88;
      }
      
      .aeo-cross-nav .aeo-nav-links a.active {
        color: #00ff88;
        font-weight: 500;
      }
      
      /* Push content below fixed nav */
      body {
        padding-top: 48px;
      }
      
      /* ... existing global styles ... */
    </style>
  </head>
  <body class="bg-tor-dark text-white antialiased">
    <!-- 1AEO Cross-Site Navigation -->
    <nav class="aeo-cross-nav">
      <div class="aeo-nav-container">
        <a href="https://www.1aeo.com" class="aeo-nav-brand">1AEO</a>
        <div class="aeo-nav-links">
          <a href="https://www.1aeo.com">Home</a>
          <a href="https://metrics.1aeo.com">Metrics</a>
          <a href="https://aroivalidator.1aeo.com">Validator</a>
          <a href="https://routefluxmap.1aeo.com" class="active">FluxMap</a>
        </div>
      </div>
    </nav>
    
    <slot />
  </body>
</html>
```

**Update Footer in `src/pages/index.astro`:**

Replace the minimal footer with:

```astro
<footer class="absolute bottom-4 left-4 z-20 pointer-events-none">
  <div class="text-gray-500 text-xs pointer-events-auto">
    <div class="flex gap-3 mb-1">
      <a href="https://metrics.1aeo.com" class="text-tor-green hover:underline">Metrics</a>
      <a href="https://aroivalidator.1aeo.com" class="text-tor-green hover:underline">Validator</a>
      <a href="https://github.com/1aeo" class="text-tor-green hover:underline">GitHub</a>
    </div>
    <div>
      Part of <a href="https://www.1aeo.com" class="text-tor-green hover:underline font-medium">1AEO</a>
      • Data from <a href="https://www.torproject.org" target="_blank" rel="noopener" class="text-tor-green hover:underline">Tor Project</a>
    </div>
  </div>
</footer>
```

---

## Brand Design System (Reference)

### Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--aeo-green` | #00ff7f | Primary accent |
| `--aeo-green-dim` | #00cc66 | Links, secondary accent |
| `--aeo-dark-bg` | #121212 | Main background |
| `--aeo-dark-surface` | #1e1e1e | Cards, nav bars |
| `--aeo-dark-border` | rgba(0,255,127,0.2) | Subtle borders |
| `--aeo-text` | #ffffff | Primary text |
| `--aeo-text-muted` | #cccccc | Secondary text |
| `--aeo-text-dim` | #888888 | Tertiary text |

### Navigation Structure

All sites should have:
1. **Cross-Site Nav Bar** (dark background, top of page)
   - 1AEO brand link → www.1aeo.com
   - Home → www.1aeo.com
   - Metrics → metrics.1aeo.com
   - Validator → aroivalidator.1aeo.com
   - FluxMap → routefluxmap.1aeo.com

2. **Footer** (dark background)
   - Links to all sites + GitHub
   - "Part of 1st Amendment Encrypted Openness LLC"

---

## Implementation Checklist

### Completed ✅

- [x] metrics.1aeo.com - Cross-site navigation bar
- [x] metrics.1aeo.com - Unified footer
- [x] metrics.1aeo.com - Green accent colors
- [x] metrics.1aeo.com - CSS brand variables
- [x] aroivalidator.1aeo.com - Dark theme
- [x] aroivalidator.1aeo.com - Cross-site navigation bar
- [x] aroivalidator.1aeo.com - Unified footer
- [x] aroivalidator.1aeo.com - Green accent colors
- [x] routefluxmap.1aeo.com - Dark theme with green accent
- [x] routefluxmap.1aeo.com - Link to metrics.1aeo.com

### Remaining 🔲

- [x] ~~**www.1aeo.com** - Add RouteFluxMap to navigation~~ ✅ DONE
- [ ] **routefluxmap.1aeo.com** - Add cross-site navigation bar
- [ ] **routefluxmap.1aeo.com** - Add unified footer with all links
- [ ] **routefluxmap.1aeo.com** - Add 1AEO branding text

---

## Summary

**90% Complete** - The unification effort is nearly complete:

| Component | Allium | Validator | FluxMap | Main Site |
|-----------|--------|-----------|---------|-----------|
| Cross-Site Nav | ✅ | ✅ | ❌ | ✅ |
| Footer Links | ✅ | ✅ | ⚠️ | N/A |
| Brand Colors | ✅ | ✅ | ✅ | ✅ |
| Dark Theme | ⚠️ Light | ✅ | ✅ | ✅ |
| Links All Sites | ✅ | ✅ | ❌ | ✅ |

The only outstanding work is:
1. ~~Add RouteFluxMap link to www.1aeo.com~~ ✅ DONE
2. Add cross-site nav + footer to routefluxmap.1aeo.com (45 minutes)
