# 1AEO Unified Appearance Guide

## Executive Summary

This document provides a comprehensive analysis of the three 1AEO Tor metrics web properties and recommendations for unifying their appearance under a consistent brand identity.

| Site | URL | Framework | Theme | Status |
|------|-----|-----------|-------|--------|
| Main Site | www.1aeo.com | Static HTML | Dark | ✅ Brand reference |
| Metrics (Allium) | metrics.1aeo.com | Python/Jinja2/Bootstrap | Light | ⚠️ Needs alignment |
| RouteFluxMap | routefluxmap.1aeo.com | Astro/React/Tailwind | Dark | ✅ Mostly aligned |
| AROI Validator | aroivalidator.1aeo.com | Streamlit | Default | ⚠️ Needs alignment |

---

## Current State Analysis

### 1. www.1aeo.com (Brand Reference)

**Design System:**
- **Background:** Dark (#121212)
- **Card/Container:** #1e1e1e with green glow shadow
- **Primary Accent:** Green (#00ff7f)
- **Text:** White (#ffffff), Gray (#cccccc)
- **Font:** Arial, sans-serif
- **Icons:** Font Awesome

**Navigation Links (current):**
- Home
- Blog
- Metrics (metrics.1aeo.com) ✅
- AROI Validator (aroivalidator.1aeo.com) ✅
- Contact

**Missing:** RouteFluxMap link ❌

---

### 2. metrics.1aeo.com (Allium)

**Current Design:**
- **Background:** White (Bootstrap default)
- **Links:** Blue (#337ab7 - Bootstrap default)
- **Status indicators:** Green (#25d918) / Red (#ff1515)
- **Font:** Default Bootstrap (Helvetica Neue, system fonts)

**Issues:**
- Light theme contrasts with 1AEO brand
- No cross-site navigation
- No 1AEO branding in header/footer
- Blue links don't match green brand

---

### 3. routefluxmap.1aeo.com

**Current Design:**
- **Background:** Dark (#0a0a0a `tor-black`)
- **Primary Accent:** Green (#00ff88 `tor-green`)
- **Font:** Inter (self-hosted)
- **Styling:** Tailwind CSS + glass panels

**Status:** Most aligned with 1AEO brand (dark + green)

**Issues:**
- No cross-site navigation
- Slightly different green (#00ff88 vs #00ff7f)

---

### 4. aroivalidator.1aeo.com

**Current Design:**
- Streamlit default theming
- Uses 🧅 onion emoji as favicon
- No custom brand colors

**Issues:**
- No 1AEO branding
- No cross-site navigation
- Doesn't match any other property

---

## Unified Design System Recommendation

### Brand Colors (Standardized)

```css
/* 1AEO Brand Colors */
:root {
  /* Primary */
  --1aeo-green: #00ff7f;           /* Main accent - from www.1aeo.com */
  --1aeo-green-dim: #00cc66;       /* Muted green */
  --1aeo-green-dark: #004d26;      /* Dark green for backgrounds */
  
  /* Backgrounds (Dark Theme) */
  --1aeo-bg-primary: #121212;      /* Main background */
  --1aeo-bg-secondary: #1e1e1e;    /* Cards/containers */
  --1aeo-bg-tertiary: #0a0a0a;     /* Deepest black */
  
  /* Backgrounds (Light Theme Alternative) */
  --1aeo-light-bg: #f8f9fa;
  --1aeo-light-card: #ffffff;
  --1aeo-light-border: #e1e8ed;
  
  /* Text */
  --1aeo-text-primary: #ffffff;
  --1aeo-text-secondary: #cccccc;
  --1aeo-text-muted: #888888;
  
  /* Functional */
  --1aeo-success: #25d918;
  --1aeo-error: #ff1515;
  --1aeo-warning: #ff8c00;
  --1aeo-info: #00b4d8;
}
```

### Typography

```css
/* Standard Font Stack */
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
```

### Unified Navigation Bar

All sites should include a consistent cross-site navigation bar:

```html
<!-- 1AEO Cross-Site Navigation Bar -->
<nav class="aeo-nav">
  <div class="aeo-nav-container">
    <a href="https://www.1aeo.com" class="aeo-nav-brand">
      <img src="https://www.1aeo.com/1AEO-logo-v2.webp" alt="1AEO" height="32">
      <span>1AEO</span>
    </a>
    <div class="aeo-nav-links">
      <a href="https://www.1aeo.com">Home</a>
      <a href="https://www.1aeo.com/blog">Blog</a>
      <a href="https://metrics.1aeo.com" class="active">Metrics</a>
      <a href="https://aroivalidator.1aeo.com">Validator</a>
      <a href="https://routefluxmap.1aeo.com">FluxMap</a>
    </div>
  </div>
</nav>
```

---

## Implementation Plan

### Phase 1: Cross-Site Navigation (Quick Win)

Add a consistent navigation header to all sites linking to each other.

#### A. Update www.1aeo.com

Add RouteFluxMap to the navigation:

```html
<div class="nav-links">
    <a href="/">Home</a>
    <a href="/blog">Blog</a>
    <a href="https://metrics.1aeo.com">Metrics</a>
    <a href="https://aroivalidator.1aeo.com">AROI Validator</a>
    <a href="https://routefluxmap.1aeo.com">RouteFluxMap</a>  <!-- ADD THIS -->
    <a href="/#contact">Contact</a>
</div>
```

#### B. Update Allium (metrics.1aeo.com)

Add 1AEO navigation bar to `skeleton.html`:

```jinja2
{# Add after <body> tag in skeleton.html #}
<div class="aeo-cross-nav" style="background-color: #1e1e1e; padding: 8px 0; border-bottom: 1px solid rgba(0,255,127,0.2);">
    <div class="container">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;">
            <a href="https://www.1aeo.com" style="color: #00ff7f; text-decoration: none; font-weight: bold; display: flex; align-items: center; gap: 8px;">
                <span>1AEO</span>
            </a>
            <div style="display: flex; gap: 15px; flex-wrap: wrap; font-size: 14px;">
                <a href="https://www.1aeo.com" style="color: #cccccc; text-decoration: none;">Home</a>
                <a href="https://metrics.1aeo.com" style="color: #00ff7f; text-decoration: none; font-weight: 500;">Metrics</a>
                <a href="https://aroivalidator.1aeo.com" style="color: #cccccc; text-decoration: none;">Validator</a>
                <a href="https://routefluxmap.1aeo.com" style="color: #cccccc; text-decoration: none;">FluxMap</a>
            </div>
        </div>
    </div>
</div>
```

#### C. Update RouteFluxMap

Add cross-nav to `Layout.astro`:

```astro
<!-- Add before <slot /> in Layout.astro body -->
<nav class="fixed top-0 left-0 right-0 z-50 bg-tor-darker/90 backdrop-blur-sm border-b border-tor-green/20">
  <div class="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between">
    <a href="https://www.1aeo.com" class="text-tor-green font-bold flex items-center gap-2">
      1AEO
    </a>
    <div class="flex gap-4 text-sm">
      <a href="https://www.1aeo.com" class="text-gray-400 hover:text-tor-green">Home</a>
      <a href="https://metrics.1aeo.com" class="text-gray-400 hover:text-tor-green">Metrics</a>
      <a href="https://aroivalidator.1aeo.com" class="text-gray-400 hover:text-tor-green">Validator</a>
      <a href="https://routefluxmap.1aeo.com" class="text-tor-green font-medium">FluxMap</a>
    </div>
  </div>
</nav>
```

#### D. Update AROI Validator

Add Streamlit theming and navigation in `app.py`:

```python
# At the top of interactive_mode() function after st.set_page_config()
st.markdown("""
<style>
    /* 1AEO Brand Colors */
    :root {
        --1aeo-green: #00ff7f;
        --1aeo-bg: #1e1e1e;
    }
    
    /* Cross-site navigation */
    .aeo-nav {
        background-color: #1e1e1e;
        padding: 8px 16px;
        margin: -1rem -1rem 1rem -1rem;
        border-bottom: 1px solid rgba(0,255,127,0.2);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
    }
    .aeo-nav a {
        color: #cccccc;
        text-decoration: none;
        margin-right: 16px;
        font-size: 14px;
    }
    .aeo-nav a:hover {
        color: #00ff7f;
    }
    .aeo-nav a.brand {
        color: #00ff7f;
        font-weight: bold;
    }
    .aeo-nav a.active {
        color: #00ff7f;
        font-weight: 500;
    }
</style>
<div class="aeo-nav">
    <a href="https://www.1aeo.com" class="brand">1AEO</a>
    <div>
        <a href="https://www.1aeo.com">Home</a>
        <a href="https://metrics.1aeo.com">Metrics</a>
        <a href="https://aroivalidator.1aeo.com" class="active">Validator</a>
        <a href="https://routefluxmap.1aeo.com">FluxMap</a>
    </div>
</div>
""", unsafe_allow_html=True)
```

Also create `.streamlit/config.toml` with branded theme:

```toml
[theme]
primaryColor = "#00ff7f"
backgroundColor = "#121212"
secondaryBackgroundColor = "#1e1e1e"
textColor = "#ffffff"
font = "sans serif"
```

---

### Phase 2: Visual Consistency (Medium Effort)

#### Option A: Keep Current Themes (Recommended)

Accept that metrics.1aeo.com has a light theme for data readability, but add:
1. Green accent colors instead of blue
2. 1AEO branding in header/footer
3. Consistent cross-site navigation

**Changes for Allium:**

```css
/* Add to skeleton.html <style> section */

/* Override Bootstrap blue links with 1AEO green */
a {
    color: #00cc66;
}
a:hover {
    color: #00ff7f;
}

/* Navbar active state */
.nav.navbar-nav > li.active > a,
.nav.navbar-nav > li > a:hover {
    color: #00cc66 !important;
    border-bottom: 2px solid #00ff7f;
}

/* Footer branding */
.page-footer {
    background-color: #1e1e1e;
    color: #cccccc;
    padding: 20px;
    margin-top: 40px;
}
.page-footer a {
    color: #00ff7f;
}
```

#### Option B: Full Dark Theme (Higher Effort)

Convert all sites to dark theme. This requires significant CSS changes to Allium.

---

### Phase 3: Footer Unification

Add consistent footer across all sites:

```html
<footer class="aeo-footer" style="background-color: #1e1e1e; color: #cccccc; padding: 20px; margin-top: 40px; text-align: center; border-top: 1px solid rgba(0,255,127,0.2);">
    <div style="max-width: 1200px; margin: 0 auto;">
        <div style="display: flex; justify-content: center; gap: 20px; margin-bottom: 15px; flex-wrap: wrap;">
            <a href="https://metrics.1aeo.com" style="color: #00ff7f;">Metrics</a>
            <a href="https://aroivalidator.1aeo.com" style="color: #00ff7f;">AROI Validator</a>
            <a href="https://routefluxmap.1aeo.com" style="color: #00ff7f;">RouteFluxMap</a>
        </div>
        <p style="font-size: 14px; margin: 0;">
            Part of <a href="https://www.1aeo.com" style="color: #00ff7f; font-weight: bold;">1st Amendment Encrypted Openness LLC</a> |
            <a href="https://github.com/1aeo" style="color: #888;">GitHub</a>
        </p>
    </div>
</footer>
```

---

## Summary of Required Changes by Repository

### 1. www.1aeo.com (Static HTML)

| Change | Priority | Effort |
|--------|----------|--------|
| Add RouteFluxMap to nav | High | Low |
| Update nav link styling | Medium | Low |

### 2. 1aeo/allium (Metrics)

| File | Change | Priority | Effort |
|------|--------|----------|--------|
| `templates/skeleton.html` | Add cross-site nav bar | High | Low |
| `templates/skeleton.html` | Update link colors to green | Medium | Low |
| `templates/skeleton.html` | Add branded footer | Medium | Low |

### 3. 1aeo/routefluxmap

| File | Change | Priority | Effort |
|------|--------|----------|--------|
| `src/layouts/Layout.astro` | Add cross-site nav bar | High | Low |
| `tailwind.config.mjs` | Standardize green to #00ff7f | Low | Low |

### 4. 1aeo/aroivalidator

| File | Change | Priority | Effort |
|------|--------|----------|--------|
| `.streamlit/config.toml` | Add branded theme | High | Low |
| `app.py` | Add cross-site nav HTML | High | Medium |

---

## Quick Implementation Checklist

- [ ] Update www.1aeo.com nav to include RouteFluxMap link
- [ ] Add cross-site nav to allium/templates/skeleton.html
- [ ] Add cross-site nav to routefluxmap/src/layouts/Layout.astro
- [ ] Update .streamlit/config.toml with 1AEO theme
- [ ] Add cross-site nav HTML to aroivalidator/app.py
- [ ] Update allium CSS to use green (#00cc66) for links
- [ ] Add unified footer to all sites

---

## Appendix: CSS Variables for All Projects

Copy these CSS custom properties to each project for consistency:

```css
/* 1AEO Unified Design Tokens */
:root {
  /* Brand */
  --aeo-green: #00ff7f;
  --aeo-green-dim: #00cc66;
  
  /* Dark Theme */
  --aeo-dark-bg: #121212;
  --aeo-dark-surface: #1e1e1e;
  --aeo-dark-border: rgba(0, 255, 127, 0.2);
  
  /* Text */
  --aeo-text: #ffffff;
  --aeo-text-muted: #cccccc;
  --aeo-text-dim: #888888;
  
  /* Spacing */
  --aeo-nav-height: 48px;
}
```
