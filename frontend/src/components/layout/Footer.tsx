import Link from 'next/link';

export function Footer() {
  return (
    <footer className="border-t bg-muted/40 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          <div>
            <h3 className="text-sm font-semibold mb-3">GA4GH Beacon v2</h3>
            <p className="text-sm text-muted-foreground">
              Genomic data discovery service implementing the GA4GH Beacon v2 specification.
            </p>
          </div>

          <div>
            <h3 className="text-sm font-semibold mb-3">Links</h3>
            <ul className="space-y-2">
              <li>
                <Link href="/" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                  Query Interface
                </Link>
              </li>
              <li>
                <Link href="/datasets" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                  Datasets
                </Link>
              </li>
              <li>
                <Link href="/about" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                  About
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold mb-3">Resources</h3>
            <ul className="space-y-2">
              <li>
                <a
                  href="https://beacon-project.io/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  GA4GH Beacon Project
                </a>
              </li>
              <li>
                <a
                  href="https://h3abionet.org/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  H3Africa Bioinformatics Network
                </a>
              </li>
              <li>
                <a
                  href="https://afrigen-d.org/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  Afrigen-D
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold mb-3">Legal</h3>
            <ul className="space-y-2">
              <li>
                <a
                  href="https://fedimpute.afrigen-d.org/terms"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  Terms of Service
                </a>
              </li>
              <li>
                <a
                  href="https://fedimpute.afrigen-d.org/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  Privacy Policy
                </a>
              </li>
              <li>
                <a
                  href="https://fedimpute.afrigen-d.org/cookies"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  Cookie Policy
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>
      <div className="w-full bg-muted/40 py-4 px-4">
        <p className="text-xs text-muted-foreground text-center leading-relaxed">
          Copyright &copy; {new Date().getFullYear()}{' '}
          <a href="https://afrigen-d.org" target="_blank" rel="noopener noreferrer" className="hover:text-primary transition-colors underline">
            Afrigen-D - African Genomics Data Hub
          </a>{' '}
          (NIH grant number U24HG012750). Governed by the{' '}
          <a href="https://uct.ac.za" target="_blank" rel="noopener noreferrer" className="hover:text-primary transition-colors underline">
            University of Cape Town
          </a>{' '}
          Human Research Ethics Committee, Approval No: HREC R043/2018. For support, contact{' '}
          <a href="mailto:support@bioinformaticsinstitute.africa" className="hover:text-primary transition-colors underline">
            support@bioinformaticsinstitute.africa
          </a>.
        </p>
      </div>
    </footer>
  );
}
