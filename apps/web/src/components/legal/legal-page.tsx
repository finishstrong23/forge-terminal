import React from "react";
import Link from "next/link";

/**
 * Shared layout for the legal pages (/terms, /privacy, /disclaimer).
 *
 * IMPORTANT: the content rendered through this component is a TEMPLATE
 * drafted for launch preparation — it must be reviewed by qualified legal
 * counsel before public launch (ROADMAP M5).
 */

export interface LegalSection {
  heading: string;
  body: string[];
}

export function LegalPage({
  title,
  updated,
  sections,
}: {
  title: string;
  updated: string;
  sections: LegalSection[];
}) {
  return (
    <div className="mx-auto max-w-2xl py-6">
      <h1 className="mb-1 text-lg font-bold text-foreground">{title}</h1>
      <p className="mb-6 text-xs text-muted-foreground">Last updated: {updated}</p>

      <div className="space-y-6">
        {sections.map((section) => (
          <section key={section.heading}>
            <h2 className="mb-2 text-sm font-semibold text-foreground">
              {section.heading}
            </h2>
            {section.body.map((paragraph, i) => (
              <p key={i} className="mb-2 text-xs leading-relaxed text-muted-foreground">
                {paragraph}
              </p>
            ))}
          </section>
        ))}
      </div>

      <div className="mt-8 flex gap-4 border-t border-border pt-4 text-xs text-muted-foreground">
        <Link href="/terms" className="hover:text-foreground">Terms of Service</Link>
        <Link href="/privacy" className="hover:text-foreground">Privacy Policy</Link>
        <Link href="/disclaimer" className="hover:text-foreground">Risk Disclosure</Link>
      </div>
    </div>
  );
}
