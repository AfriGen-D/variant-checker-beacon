import { Container } from '@/components/layout/Container';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';


export default function AboutPage() {
  return (
    <Container size="md" className="py-8">
      <h1 className="text-4xl font-bold mb-2">About the AfriGen-D Genomic Beacon</h1>
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
              Search and discover genomic variants through the{' '}
              <a href="https://beacon-project.io/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                GA4GH Beacon API
              </a>.
            </p>
            <p>
              The{' '}
              <a href="https://www.ga4gh.org/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                Global Alliance for Genomics and Health (GA4GH)
              </a>{' '}
              Beacon is a standard for genomic data discovery. It provides a framework for sharing genetic information in a privacy-preserving manner.
            </p>
            <p>
              <strong className="text-foreground">Boolean Mode</strong> — This instance runs in Boolean mode, which provides public access while protecting privacy. Queries return only YES or NO responses, indicating whether a variant exists in the database without revealing sensitive information.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>About AfriGen-D</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-muted-foreground">
            <p>
              The{' '}
              <a href="https://afrigen-d.org" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                African Genomics Data Hub (AfriGen-D)
              </a>{' '}
              offers a suite of interconnected resources and services to facilitate the implementation of African genomics research throughout the research data life cycle — from data generation and discovery, to analysis and long-term archiving. AfriGen-D reflects the value and application of African genomics to the world, and the growing integration of genetics and genomics in healthcare and biomedical research globally.
            </p>
            <p>
              AfriGen-D is a multi-PI project led from three sites across Africa — the{' '}
              <a href="https://www.uct.ac.za/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                University of Cape Town
              </a>{' '}
              (Prof. Nicola Mulder, South Africa), the{' '}
              <a href="https://www.pasteur.tn/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                Institut Pasteur de Tunis
              </a>{' '}
              (Assoc. Prof. Kais Ghedira, Tunisia), and the{' '}
              <a href="https://www.uom.ac.mu/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                University of Mauritius
              </a>{' '}
              (Prof. Yasmina Jaufeerally-Fakim, Mauritius), with key partners in additional African countries.
            </p>
            <p>
              Headline resources include the{' '}
              <a href="https://afrigen-d.org/data-resources/#agmp" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                African Genomic Medicine Portal (AGMP)
              </a>, the{' '}
              <a href="https://afrigen-d.org/data-resources/#agvd" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                African Genome Variation Database (AGVD)
              </a>, the{' '}
              <a href="https://afrigen-d.org/data-resources/#afpo" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                African Population Ontology (AfPO)
              </a>, a federated{' '}
              <a href="https://afrigen-d.org/data-resources/#data-catalogue" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                Data Catalogue
              </a>,{' '}
              <a href="https://afrigen-d.org/data-resources/#data-collection-toolkits" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                Data Collection Toolkits
              </a>, an online{' '}
              <a href="https://afrigen-d.org/services/#imputation-service" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                Imputation Service
              </a>, the{' '}
              <a href="/" className="text-primary hover:underline">
                AfriGen-D Genomic Beacon
              </a>, and the{' '}
              <a href="https://beacon-network-dev.afrigen-d.dev" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                African Beacon Network
              </a>.
            </p>
            <p>
              AfriGen-D is supported by the U.S.{' '}
              <a href="https://www.genome.gov/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                National Human Genome Research Institute
              </a>{' '}
              (NIH grant <strong className="text-foreground">U24HG012750</strong>) and governed by the University of Cape Town Human Research Ethics Committee (Approval No: <strong className="text-foreground">HREC R043/2018</strong>). Visit{' '}
              <a href="https://afrigen-d.org" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                afrigen-d.org
              </a>{' '}
              for project details, partners, and team.
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
                <a href="https://github.com/AfriGen-D/african-beacon-network" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  African Beacon Network
                </a>
              </li>
              <li>
                <a href="https://afrigen-d.org" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  AfriGen-D
                </a>
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </Container>
  );
}
