import { useLoaderData } from 'react-router-dom';
import type { PromosPageData } from '../types';
import { PromoGrid } from './PromoGrid';
import { PageMain, PageTitle } from '@/ui/layout';
import { SkeletonRow } from '@/ui/feedback';

export function PromosPage() {
  const data = useLoaderData() as PromosPageData | undefined;

  if (!data) {
    return (
      <PageMain>
        <PageTitle>Promos</PageTitle>
        <SkeletonRow count={8} />
      </PageMain>
    );
  }

  return (
    <PageMain>
      <PageTitle>
        Promos
        <span className="ml-2 text-sm font-normal text-gray-500">
          {data.totalCount} cards
        </span>
      </PageTitle>
      <PromoGrid promos={data.promos} />
    </PageMain>
  );
}
