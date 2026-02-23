import { Container } from '@/components/layout/Container';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';

export default function DocsPage() {
  const apiUrl = process.env.NEXT_PUBLIC_BEACON_API_URL || 'http://localhost:8000';

  return (
    <Container size="md" className="py-8">
      <h1 className="text-4xl font-bold mb-2">API Documentation</h1>
      <p className="text-muted-foreground mb-8">
        Explore the Beacon v2 API documentation using the interactive tools below.
      </p>
      <div className="grid gap-4">
        <a href={`${apiUrl}/api/redoc/`} target="_blank" rel="noopener noreferrer">
          <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
            <CardHeader>
              <CardTitle>ReDoc Documentation</CardTitle>
              <CardDescription>
                Comprehensive API documentation with detailed endpoint descriptions
              </CardDescription>
            </CardHeader>
          </Card>
        </a>
        <a href={`${apiUrl}/api/docs/`} target="_blank" rel="noopener noreferrer">
          <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
            <CardHeader>
              <CardTitle>Swagger UI</CardTitle>
              <CardDescription>
                Interactive API explorer to test endpoints directly from your browser
              </CardDescription>
            </CardHeader>
          </Card>
        </a>
      </div>
    </Container>
  );
}
