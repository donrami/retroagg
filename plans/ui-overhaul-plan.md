# RetroAgg UI Overhaul Plan

## Current State Analysis

### Existing UI
- **Style**: Windows 98 brutalist aesthetic using 98.css library
- **Layout**: Fixed-width desktop with window chrome, status bars, title bars
- **Colors**: Teal background (#008080), gray windows (#c0c0c0), blue accents (#000080)
- **Typography**: Segoe UI, Tahoma, MS Sans Serif (system fonts)
- **Components**: Fieldset-based filters, tree-view sources, iframe reader pane

### Application Structure
- **Framework**: FastAPI with Jinja2 templates
- **Database**: SQLite with SQLAlchemy async
- **Pages**: 
  - `/` - Main article feed with filters
  - `/sources` - Source registry by region
  - `/api/*` - JSON API endpoints

---

## Design Direction: Modern Minimalist

### Core Principles
1. **Clean whitespace** - Generous padding and margins
2. **Subtle shadows** - Soft elevation effects instead of harsh borders
3. **Modern typography** - System font stack with Inter/San Francisco
4. **Card-based layout** - Articles as distinct cards with hover states
5. **Responsive** - Works on mobile, tablet, and desktop
6. **Information density** - Maintain high content-to-noise ratio

### Color Palette
```
--bg-primary: #f8f9fa (light gray background)
--bg-secondary: #ffffff (white cards)
--bg-tertiary: #e9ecef (subtle sections)
--text-primary: #212529 (dark gray text)
--text-secondary: #6c757d (muted text)
--text-tertiary: #adb5bd (subtle metadata)
--accent-primary: #0d6efd (blue links/actions)
--accent-secondary: #6c757d (secondary actions)
--border-color: #dee2e6 (subtle borders)
--shadow-sm: 0 1px 3px rgba(0,0,0,0.08)
--shadow-md: 0 4px 12px rgba(0,0,0,0.1)
--shadow-lg: 0 8px 24px rgba(0,0,0,0.12)
--radius-sm: 6px
--radius-md: 12px
--radius-lg: 16px
```

### Typography
```
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif
--font-mono: 'JetBrains Mono', 'Fira Code', monospace

--text-xs: 0.75rem (12px)
--text-sm: 0.875rem (14px)
--text-base: 1rem (16px)
--text-lg: 1.125rem (18px)
--text-xl: 1.25rem (20px)
--text-2xl: 1.5rem (24px)
```

---

## Implementation Plan

### Phase 1: Base Template (base.html)

**Changes:**
- Remove 98.css dependency
- Add Google Fonts (Inter)
- Create CSS custom properties
- Replace window chrome with clean header/main/footer structure
- Add responsive viewport meta

**New Structure:**
```html
<header class="site-header">
  <nav class="main-nav">
    <logo>
    <nav-links>
  </nav>
</header>

<main class="main-content">
  {% block content %}{% endblock %}
</main>

<footer class="site-footer">
  <status-bar>
</footer>
```

### Phase 2: Main Feed (index.html)

**Changes:**
- Replace fieldset filters with modern pill/chip selectors
- Replace article list with card grid layout
- Add article thumbnails (if available)
- Modernize pagination with numbered pages
- Keep split-pane reader but improve styling

**Article Card Design:**
```
┌─────────────────────────────────────┐
│ [Thumbnail Image - optional]        │
├─────────────────────────────────────┤
│ Source Tag    Region Tag            │
│ Article Title (bold, blue)          │
│ Summary text (2-3 lines max)        │
│ Meta: Date | Author | Read time     │
└─────────────────────────────────────┘
```

**Filter Section:**
- Horizontal pill buttons for regions
- Active state with accent color
- Clear all button

### Phase 3: Sources Page (sources.html)

**Changes:**
- Replace tree-view with clean card grid by region
- Add source cards with logo placeholder, description, bias indicator
- Better visual hierarchy

**Source Card Design:**
```
┌─────────────────────────────────────┐
│ [Logo] Source Name                  │
│ [Bias Badge]                        │
│ Description text...                 │
│ url.com                    [ACTIVE] │
└─────────────────────────────────────┘
```

### Phase 4: CSS (custom.css)

**Complete rewrite with:**
- CSS custom properties for theming
- Modern reset
- Utility classes for common patterns
- Card, button, input, badge components
- Responsive breakpoints (mobile < 640px, tablet < 1024px)
- Smooth transitions and hover states

### Phase 5: Reader Pane Improvements

**Changes:**
- Modern iframe styling
- Loading skeleton states
- Error states with retry option
- Smooth transitions when switching articles

---

## File Changes Summary

| File | Action |
|------|--------|
| `app/templates/base.html` | Complete rewrite |
| `app/templates/index.html` | Redesign with cards |
| `app/templates/sources.html` | Modernize layout |
| `app/static/css/custom.css` | Complete rewrite |

---

## Mermaid: New Layout Structure

```mermaid
graph TB
    subgraph "Header"
        A[Logo: RetroAgg] --> B[Nav: Home | Sources | API | Status]
    end
    
    subgraph "Main Content - Index"
        C[Filter Bar: Region Pills] --> D[Article Grid]
        D --> E[Article Card]
        E --> F[Reader Pane]
    end
    
    subgraph "Main Content - Sources"
        G[Region Tabs] --> H[Source Cards Grid]
    end
    
    subgraph "Footer"
        I[Status: Version | Last Refresh | Stats]
    end
    
    style A fill:#fff,stroke:#dee2e6
    style C fill:#fff,stroke:#dee2e6
    style E fill:#fff,stroke:#dee2e6
    style H fill:#fff,stroke:#dee2e6
```

---

## Acceptance Criteria

1. ✅ All pages load without errors
2. ✅ Responsive on mobile (320px+), tablet (768px+), desktop (1024px+)
3. ✅ Article cards display all metadata clearly
4. ✅ Filters work correctly with URL state
5. ✅ Reader pane loads articles smoothly
6. ✅ Sources page shows all sources grouped by region
7. ✅ No JavaScript errors in console
8. ✅ Accessible (proper ARIA labels, keyboard navigation)
9. ✅ Fast loading (minimal CSS, no heavy frameworks)
10. ✅ Maintains the app's core philosophy: information pluralism, no tracking, no algorithms