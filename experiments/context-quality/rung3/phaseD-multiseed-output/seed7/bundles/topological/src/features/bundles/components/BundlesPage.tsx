import { BundleList } from './BundleList';
import { PageMain, PageTitle } from '@/ui';

export function BundlesPage() {
  return (
    <PageMain>
      <PageTitle
        title="Bundles"
        subtitle="Save big with curated product bundles"
      />
      <BundleList />
    </PageMain>
  );
}
