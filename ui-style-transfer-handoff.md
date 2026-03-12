# UI Style Transfer Handoff

Use this file as the copy-paste handoff for Codex in the other repo.

## Copy-paste prompt for the other repo

```md
Replicate the visual style of the WARP `cMAF-System` UI into this repo's UI without copying unrelated business logic.

Apply these exact design traits:

- Overall shell: full-height page with a soft gradient background using `from-background via-background to-muted/30`, outer page padding `p-6`, and vertical spacing `space-y-6`.
- Theme: premium, clean, slightly glassy control dashboard using a bright blue primary accent.
- Radius: large rounded surfaces, primarily `rounded-xl`.
- Cards: use a reusable card style equivalent to `premium-card`:
  - background: `bg-card`
  - border: `border border-border`
  - radius: `rounded-xl`
  - shadow: soft elevated shadow
  - hover: slightly stronger shadow
- Glass surfaces: support a `.glass` style with translucent background, blur, and subtle border.
- Color system: use these semantic tokens, not hardcoded one-off colors:
  - `background`, `foreground`
  - `card`, `card-foreground`
  - `primary`, `primary-foreground`
  - `secondary`, `secondary-foreground`
  - `muted`, `muted-foreground`
  - `accent`, `accent-foreground`
  - `success`, `success-foreground`
  - `destructive`, `destructive-foreground`
  - `border`, `input`, `ring`, `glass`
- Accent color direction:
  - primary/accent is a saturated blue
  - success is green
  - destructive is red
- Header layout:
  - place the header inside a large premium card with `p-6`
  - left side: gradient logo tile, big gradient title, smaller muted subtitle
  - right side: status pill plus theme toggle or equivalent utility action
  - keep the header spacious and horizontally balanced
- Header visual details:
  - logo tile: `w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-accent`
  - title: `text-3xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent`
  - status pill: rounded, lightly tinted success background with icon and two lines of text
- Section layout:
  - tabs/buttons should sit inside a `premium-card p-2`
  - active tab uses `bg-primary text-primary-foreground shadow-md shadow-primary/20`
  - inactive tab uses `bg-secondary text-secondary-foreground hover:bg-muted`
- Information panels:
  - use large cards with `p-6`
  - internal grouped rows can use `rounded-lg border border-border bg-secondary/30`
  - labels should be muted and compact, values stronger and semibold
- Motion:
  - keep subtle transitions
  - use `transition-all duration-300` on cards and `duration-200` on colors
  - allow a simple `animate-in fade-in duration-700` for page content if available

Implement this style using the current stack and component conventions in this repo. Reuse existing components where possible, but update spacing, card styling, color tokens, and header structure so the result clearly matches this reference UI.

If this repo does not use Tailwind, translate the same visual system into its styling approach while preserving the same spacing, color semantics, corner radius, shadows, and header composition.
```

## Source theme tokens

Use these tokens as the reference palette and surface system.

```css
:root {
  --background: oklch(0.98 0 0);
  --foreground: oklch(0.12 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.12 0 0);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.12 0 0);
  --primary: oklch(0.52 0.25 254);
  --primary-foreground: oklch(0.98 0 0);
  --secondary: oklch(0.96 0 0);
  --secondary-foreground: oklch(0.12 0 0);
  --muted: oklch(0.94 0 0);
  --muted-foreground: oklch(0.5 0 0);
  --accent: oklch(0.52 0.25 254);
  --accent-foreground: oklch(0.98 0 0);
  --destructive: oklch(0.6 0.25 15);
  --destructive-foreground: oklch(0.98 0 0);
  --success: oklch(0.6 0.2 140);
  --success-foreground: oklch(0.98 0 0);
  --border: oklch(0.9 0 0);
  --input: oklch(0.96 0 0);
  --ring: oklch(0.52 0.25 254);
  --radius: 1rem;
  --glass: oklch(1 0 0 / 0.6);
}

.dark {
  --background: oklch(0.08 0 0);
  --foreground: oklch(0.98 0 0);
  --card: oklch(0.12 0 0);
  --card-foreground: oklch(0.98 0 0);
  --popover: oklch(0.12 0 0);
  --popover-foreground: oklch(0.98 0 0);
  --primary: oklch(0.58 0.25 254);
  --primary-foreground: oklch(0.98 0 0);
  --secondary: oklch(0.14 0 0);
  --secondary-foreground: oklch(0.98 0 0);
  --muted: oklch(0.18 0 0);
  --muted-foreground: oklch(0.6 0 0);
  --accent: oklch(0.58 0.25 254);
  --accent-foreground: oklch(0.98 0 0);
  --destructive: oklch(0.65 0.25 15);
  --destructive-foreground: oklch(0.98 0 0);
  --success: oklch(0.65 0.2 140);
  --success-foreground: oklch(0.98 0 0);
  --border: oklch(0.2 0 0);
  --input: oklch(0.14 0 0);
  --ring: oklch(0.58 0.25 254);
  --glass: oklch(0.12 0 0 / 0.6);
}
```

## Reusable style primitives

```css
.glass {
  background: var(--glass);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border);
}

.premium-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 1rem;
  box-shadow: 0 10px 30px rgb(0 0 0 / 0.05);
  transition: all 300ms ease;
}

.premium-card:hover {
  box-shadow: 0 16px 40px rgb(0 0 0 / 0.1);
}
```

## Header reference

```tsx
<header className="premium-card p-6 backdrop-blur-xl">
  <div className="flex items-center justify-between">
    <div className="flex items-center gap-4">
      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20">
        <span className="text-2xl font-bold text-primary-foreground">W</span>
      </div>
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          cMAF Device 2
        </h1>
        <p className="text-sm text-muted-foreground font-medium">cMAF Control System</p>
      </div>
    </div>

    <div className="flex items-center gap-4">
      <div className="flex items-center gap-3 px-6 py-3 rounded-xl bg-success/10 border border-success/20">
        <div>
          <p className="text-xs text-muted-foreground font-medium">System Status</p>
          <p className="text-sm font-semibold text-success">Operational</p>
        </div>
      </div>
      <div>{/* theme toggle or utility action */}</div>
    </div>
  </div>
</header>
```

## Page shell reference

```tsx
<div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/30 p-6 space-y-6">
  <Header />

  <div className="space-y-6 animate-in fade-in duration-700">
    <div className="premium-card p-2">
      {/* tabs or primary mode switch */}
    </div>

    <div className="grid grid-cols-1 xl:grid-cols-[1fr_460px] gap-6 items-start">
      {/* main content */}
      {/* side panel */}
    </div>
  </div>
</div>
```

## Component treatment reference

```tsx
<div className="premium-card p-6 space-y-4">
  <div className="flex items-center justify-between">
    <h2 className="text-lg font-semibold text-foreground">Live Indicators</h2>
    <span className="text-xs text-muted-foreground">1s refresh</span>
  </div>

  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
    <div className="p-3 rounded-lg border border-border bg-secondary/30 space-y-2">
      <p className="text-xs text-muted-foreground uppercase tracking-wide font-semibold">
        Section Title
      </p>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">Label</span>
          <span className="text-xs font-semibold text-foreground text-right">Value</span>
        </div>
      </div>
    </div>
  </div>
</div>
```

## Notes for adaptation

- Preserve the roomy spacing. The visual identity depends as much on whitespace and surface treatment as on color.
- Keep semantic colors centralized. Do not hardcode blue/green/red repeatedly inside components.
- If the target repo already has a design system, map these tokens into that system rather than fighting it.
- If the target repo has no dark mode, use only the light token set first and leave the dark values ready for follow-up.
