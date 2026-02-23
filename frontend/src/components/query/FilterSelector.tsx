'use client';

import { useState, useMemo } from 'react';
import { useFilteringTerms } from '@/lib/hooks/useBeaconQuery';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Skeleton } from '@/components/ui/Skeleton';
import { Search, X } from 'lucide-react';

interface FilterSelectorProps {
  selected: string[];
  onChange: (filters: string[]) => void;
}

export function FilterSelector({ selected, onChange }: FilterSelectorProps) {
  const { data, isLoading } = useFilteringTerms();
  const [search, setSearch] = useState('');
  const [open, setOpen] = useState(false);

  const terms = useMemo(() => {
    const all = data?.response?.results ?? [];
    if (!search) return all.slice(0, 20);
    const q = search.toLowerCase();
    return all
      .filter(t => t.id.toLowerCase().includes(q) || t.label?.toLowerCase().includes(q))
      .slice(0, 20);
  }, [data, search]);

  const toggleFilter = (id: string) => {
    if (selected.includes(id)) {
      onChange(selected.filter(f => f !== id));
    } else {
      onChange([...selected, id]);
    }
  };

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">Filtering Terms (Optional)</label>

      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map(id => (
            <Badge key={id} variant="info" size="sm" className="gap-1 cursor-pointer" onClick={() => toggleFilter(id)}>
              {id}
              <X className="h-3 w-3" />
            </Badge>
          ))}
        </div>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search filters..."
          value={search}
          onChange={e => { setSearch(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          className="pl-10"
        />
      </div>

      {open && (
        <div className="border rounded-md max-h-48 overflow-auto bg-background shadow-md">
          {isLoading && (
            <div className="p-3 space-y-2">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-6 w-full" />)}
            </div>
          )}

          {!isLoading && terms.length === 0 && (
            <p className="text-sm text-muted-foreground p-3 text-center">
              {search ? 'No matching filters.' : 'No filters available.'}
            </p>
          )}

          {!isLoading && terms.map(term => (
            <button
              key={term.id}
              type="button"
              className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-muted/50 transition-colors text-left"
              onClick={() => { toggleFilter(term.id); setOpen(false); setSearch(''); }}
            >
              <div>
                <span className="font-medium">{term.label || term.id}</span>
                <span className="text-xs text-muted-foreground ml-2 font-mono">{term.id}</span>
              </div>
              {selected.includes(term.id) && (
                <Badge variant="success" size="sm">Selected</Badge>
              )}
            </button>
          ))}

          {open && terms.length > 0 && (
            <button
              type="button"
              className="w-full px-3 py-2 text-xs text-muted-foreground hover:bg-muted/50 border-t"
              onClick={() => setOpen(false)}
            >
              Close
            </button>
          )}
        </div>
      )}
    </div>
  );
}
