import { Container } from '@/components/layout/Container';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';


export default function AboutPage() {
  return (
    <Container size="md" className="py-8">
      <h1 className="text-4xl font-bold mb-2">About GA4GH Beacon v2</h1>
      <p className="text-xl text-muted-foreground mb-8">
        Genomic Variant Discovery Service
      </p>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>What is Beacon?</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-muted-foreground">
            <p>
              Search and discover genomic variants through the GA4GH Beacon v2 API.
              Our Boolean mode provides privacy-preserving discovery by returning only YES/NO responses.
            </p>
            <p>
              The Global Alliance for Genomics and Health (GA4GH) Beacon is a standard for
              genomic data discovery. It provides a framework for sharing genetic information
              in a privacy-preserving manner.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Boolean Mode</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              This instance runs in Boolean mode, which provides public access while protecting
              privacy. Queries return only YES or NO responses, indicating whether a variant
              exists in the database without revealing sensitive information.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Resources</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              <li>
                <a href="https://beacon-project.io/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  GA4GH Beacon Project
                </a>
              </li>
              <li>
                <a href="https://h3abionet.org/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  H3Africa Bioinformatics Network
                </a>
              </li>
              <li>
                <a href="https://afrigen-d.org/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  Afrigen-D
                </a>
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </Container>
  );
}
