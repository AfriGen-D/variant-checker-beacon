'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/Button';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { Menu, X } from 'lucide-react';

const navLinks = [
  { href: '/', label: 'Check variant' },
  { href: '/datasets', label: 'Datasets' },
  { href: '/about', label: 'About' },
];

export function Header() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Two variants rather than a CSS filter: the artwork is ~60% black
              ink (the wordmark) plus saturated brand red/yellow/green. An
              invert would turn the red cyan, and a brightness filter would wash
              out the brand colours. The dark asset re-inks only the neutral
              dark pixels, leaving the brand palette untouched.
              Swapped by CSS class so there is no hydration flash. */}
          {/* The accessible name lives on the link, not the images: whichever
              variant is hidden is display:none and therefore absent from the
              accessibility tree, so putting alt text on the images would leave
              the link unnamed in one theme. Both images are decorative. */}
          <Link href="/" className="flex items-center" aria-label="Variant Checker — Beacon, home">
            <Image
              src="/afrigen-d-beacon.png"
              alt=""
              width={200}
              height={48}
              priority
              className="h-16 w-auto dark:hidden"
            />
            <Image
              src="/afrigen-d-beacon-dark.png"
              alt=""
              width={200}
              height={48}
              priority
              className="h-16 w-auto hidden dark:block"
            />
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center space-x-1">
            {navLinks.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  pathname === href
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                )}
              >
                {label}
              </Link>
            ))}
            <ThemeToggle />
          </div>

          {/* Mobile: theme toggle + menu button */}
          <div className="flex items-center md:hidden">
            <ThemeToggle />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle navigation menu"
              aria-expanded={mobileOpen}
              aria-controls="mobile-nav"
            >
              {mobileOpen ? (
                <X className="h-5 w-5" aria-hidden="true" />
              ) : (
                <Menu className="h-5 w-5" aria-hidden="true" />
              )}
            </Button>
          </div>
        </div>

        {/* Mobile nav */}
        {mobileOpen && (
          <div id="mobile-nav" className="md:hidden pb-4 space-y-1">
            {navLinks.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  'block px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  pathname === href
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                )}
                onClick={() => setMobileOpen(false)}
              >
                {label}
              </Link>
            ))}
          </div>
        )}
      </nav>
    </header>
  );
}
