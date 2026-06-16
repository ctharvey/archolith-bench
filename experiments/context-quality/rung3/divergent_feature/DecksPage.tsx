// DIVERGENT fixture: a Decks feature that breaks every core convention.
// No use<Name>Data hook (data fetched inline), raw fetch(), no @/data layer,
// no *.module.css (inline styles). Hand-written for the contract validation.
import { useState, useEffect } from 'react';

export default function DecksPage() {
  const [decks, setDecks] = useState<any[]>([]);
  useEffect(() => {
    fetch('/api/decks/list').then(r => r.json()).then(setDecks);  // raw fetch, no data layer
  }, []);
  return (
    <div style={{ padding: 16, color: '#16a34a' }}>
      {decks.map(d => <div key={d.id} style={{ display: 'flex' }}>{d.name} — ${d.value}</div>)}
    </div>
  );
}
