/** Critical farmer-facing EN/BN strings (FE-10). Expand as modules are translated. Not agronomist-reviewed. */
export type Locale = 'en' | 'bn';

const catalog = {
  'nav.dashboard': {en: 'Dashboard', bn: 'ড্যাশবোর্ড'},
  'nav.doctor': {en: 'AgroDoctor', bn: 'অ্যাগ্রোডক্টর'},
  'nav.flood': {en: 'FloodCrop', bn: 'ফ্লাডক্রপ'},
  'nav.market': {en: 'KrishiMarket', bn: 'কৃষিমার্কেট'},
  'nav.actions': {en: 'Action Center', bn: 'অ্যাকশন সেন্টার'},
  'nav.settings': {en: 'Settings', bn: 'সেটিংস'},
  'session.checking': {en: 'Checking your workspace…', bn: 'আপনার ওয়ার্কস্পেস যাচাই হচ্ছে…'},
  'session.serviceError': {en: 'Service unavailable. Retry when the backend is reachable.', bn: 'সেবা এখন পাওয়া যাচ্ছে না। ব্যাকএন্ড চালু থাকলে আবার চেষ্টা করুন।'},
  'session.retry': {en: 'Retry', bn: 'আবার চেষ্টা'},
  'doctor.upload': {en: 'Upload a tomato leaf photo', bn: 'টমেটো পাতার ছবি আপলোড করুন'},
  'doctor.busy': {en: 'Screening in progress…', bn: 'পরীক্ষা চলছে…'},
  'doctor.ood': {
    en: 'Research screening only. This model does not reliably reject non-tomato or out-of-scope images.',
    bn: 'শুধু গবেষণাধর্মী স্ক্রিনিং। এই মডেল টমেটো ছাড়া বা অজানা ছবি নির্ভরযোগ্যভাবে বাতিল করে না।',
  },
  'market.stale': {
    en: 'Inputs changed — results below are from the previous calculation. Run Compare again to update.',
    bn: 'ইনপুট বদলেছে — নিচের ফল আগের হিসাবের। হালনাগাদ করতে আবার তুলনা করুন।',
  },
  'market.watchNotice': {
    en: 'Saved price target only. Automatic monitoring and alerts are not active.',
    bn: 'শুধু সংরক্ষিত মূল্য লক্ষ্য। স্বয়ংক্রিয় নজরদারি বা অ্যালার্ট চালু নেই।',
  },
  'privacy.exportNote': {
    en: 'Export includes settings and sensor history. Case images download separately.',
    bn: 'এক্সপোর্টে সেটিংস ও সেন্সর ইতিহাস থাকে। কেস ছবি আলাদাভাবে ডাউনলোড হয়।',
  },
  'consent.location': {
    en: 'I consent to saving these precise coordinates for weather outlooks on my plots.',
    bn: 'আমার প্লটের আবহাওয়ার জন্য এই সঠিক স্থানাঙ্ক সংরক্ষণে সম্মতি দিচ্ছি।',
  },
} as const;

export type MessageKey = keyof typeof catalog;

export function msg(key: MessageKey, locale: Locale): string {
  const entry = catalog[key];
  return locale === 'bn' ? entry.bn : entry.en;
}

export function hasMessage(key: string): key is MessageKey {
  return key in catalog;
}
