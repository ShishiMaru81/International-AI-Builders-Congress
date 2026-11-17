'use client';
import {use, useEffect} from 'react';

/** Sets document.documentElement.lang from the locale segment.
 *  Root layout has <html lang="en"> as a static default; this client
 *  component updates it after hydration so screen-readers see the right language. */
export default function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{locale: string}>;
}) {
  const {locale} = use(params);
  const lang = locale === 'bn' ? 'bn' : 'en';
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  return <>{children}</>;
}
