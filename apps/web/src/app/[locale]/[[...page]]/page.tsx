import {notFound} from 'next/navigation';
import Workspace from '@/components/workspace';

const VALID_LOCALES = new Set(['en', 'bn']);
const VALID_PAGES = new Set([
  'dashboard','agrodoctor','floodcrop','market','agrorescue','action-center',
  'marketplace','farms','history','transparency','devices','settings','landing',
]);

export default async function Page({
  params,
}: {
  params: Promise<{locale: string; page?: string[]}>;
}) {
  const {locale, page} = await params;

  if (!VALID_LOCALES.has(locale)) notFound();
  const loc = locale as 'en' | 'bn';

  const segments = page ?? [];
  if (segments.length === 0) {
    // root → landing
  } else {
    const root = segments[0];
    if (VALID_PAGES.has(root)) {
      // ok — single-segment page
    } else if (root === 'agrodoctor' && segments.length === 2 && segments[1]) {
      // agrodoctor/[id] detail view — ok
    } else {
      notFound();
    }
  }

  return (
    <Workspace locale={loc} page={segments.join('/') || 'landing'} />
  );
}
