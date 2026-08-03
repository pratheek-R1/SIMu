/** The app's icons.
 *
 *  These replace the emoji and dingbats the prototype used inline (🔒 📎 ⚠ ✕ ✓
 *  ★ → ●◆○). Emoji render from the OS colour font, so they arrived at their own
 *  size, their own weight and their own hue -- a full-colour padlock next to
 *  10.5px navy text is the single loudest thing on that row, and it is loud
 *  about nothing.
 *
 *  Every icon here is a 24-box stroked path drawn on `currentColor` at 1em, so
 *  it inherits the colour and optical size of whatever text it sits in.
 *  Decorative by default; pass a `title` when the icon is the only label. */

interface IconProps {
  /** Overrides the 1em default. Number is px. */
  size?: number | string;
  className?: string;
  /** Accessible name. Omit for icons that sit beside a visible text label. */
  title?: string;
  style?: React.CSSProperties;
  strokeWidth?: number;
}

function svg(path: React.ReactNode, extra?: { solid?: boolean; box?: string }) {
  return function IconComponent({ size, className, title, style, strokeWidth }: IconProps) {
    return (
      <svg
        viewBox={extra?.box ?? "0 0 24 24"}
        className={`icon${extra?.solid ? " icon-solid" : ""}${className ? ` ${className}` : ""}`}
        style={size ? { width: size, height: size, ...style } : style}
        strokeWidth={strokeWidth}
        role={title ? "img" : undefined}
        aria-label={title}
        aria-hidden={title ? undefined : true}
        focusable="false"
      >
        {title ? <title>{title}</title> : null}
        {path}
      </svg>
    );
  };
}

// Wide, short body with a tall narrow shackle. The first pass used a tall body
// and a shallow shackle, which at 11px collapsed into an indistinct blob --
// at this size the silhouette is doing all the work, so it has to be extreme.
export const IconLock = svg(
  <>
    <rect x="3.5" y="11" width="17" height="9.5" rx="2.2" />
    <path d="M7.75 11V7.25a4.25 4.25 0 0 1 8.5 0V11" />
  </>,
);

export const IconUnlock = svg(
  <>
    <rect x="3.5" y="11" width="17" height="9.5" rx="2.2" />
    <path d="M7.75 11V7.25a4.25 4.25 0 0 1 8.25-1.25" />
  </>,
);

export const IconPaperclip = svg(
  <path d="M20 11.5 12.2 19.3a4.6 4.6 0 0 1-6.5-6.5l8-8a3 3 0 0 1 4.3 4.3l-8 8a1.5 1.5 0 0 1-2.1-2.1l7.3-7.3" />,
);

export const IconClose = svg(
  <>
    <path d="M6 6l12 12" />
    <path d="M18 6 6 18" />
  </>,
);

export const IconCheck = svg(<path d="M4.5 12.5 9.5 17.5 19.5 6.5" />);

export const IconDash = svg(<path d="M6 12h12" />);

export const IconArrowRight = svg(
  <>
    <path d="M4 12h15" />
    <path d="m13 6 6 6-6 6" />
  </>,
);

export const IconSearch = svg(
  <>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4 4" />
  </>,
);

export const IconChevronDown = svg(<path d="m6 9.5 6 6 6-6" />);

export const IconAlert = svg(
  <>
    <path d="M12 4.5 21 20H3z" />
    <path d="M12 10v4.5" />
    <path d="M12 17.4v.1" />
  </>,
);

export const IconStar = svg(
  <path d="m12 3.8 2.6 5.4 5.9.85-4.25 4.15 1 5.9L12 17.3l-5.25 2.8 1-5.9L3.5 10.05l5.9-.85z" />,
);

export const IconStarFilled = svg(
  <path d="m12 3.8 2.6 5.4 5.9.85-4.25 4.15 1 5.9L12 17.3l-5.25 2.8 1-5.9L3.5 10.05l5.9-.85z" />,
  { solid: true },
);

/** A row of `max` stars with `n` filled. Used for the reference-call ratings. */
export function StarRating({ n, max = 5, size = 12 }: { n: number; max?: number; size?: number }) {
  return (
    <span
      style={{ display: "inline-flex", gap: 2, color: "var(--orange)" }}
      role="img"
      aria-label={`${n} out of ${max}`}
    >
      {Array.from({ length: max }, (_, i) =>
        i < n ? <IconStarFilled key={i} size={size} /> : <IconStar key={i} size={size} />,
      )}
    </span>
  );
}
