import Workspace from '@/components/workspace';
export default async function Page({params}:{params:Promise<{locale:string;page?:string[]}>}){const {locale,page}=await params;return <Workspace locale={locale==='bn'?'bn':'en'} page={page?.join('/')||'landing'}/>}
