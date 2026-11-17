import {describe, expect, it} from 'vitest';
import {existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {cropImageFor} from '../src/lib/crop-images';

describe('marketplace crop fallback matching', () => {
  // Wrong aliases or substring matching would put a different crop on a listing.
  it.each([
    ['Fresh TOMATOES — Gazipur', 'tomato'], ['পাকা টমেটো', 'tomato'],
    ['Local potatoes', 'potato'], ['দেশি আলু', 'potato'],
    ['Miniket rice', 'rice'], ['চাল', 'rice'], ['ধান', 'rice'],
    ['Sweet corn', 'maize'], ['ভুট্টা', 'maize'], ['Red onions', 'onion'], ['পেঁয়াজ', 'onion'],
    ['Carrots', 'carrot'], ['গাজর', 'carrot'], ['Brinjal', 'eggplant'], ['বেগুন', 'eggplant'],
    ['Cucumbers', 'cucumber'], ['শসা', 'cucumber'], ['Green chillies', 'chilli'], ['মরিচ', 'chilli'],
    ['Bell pepper', 'pepper'], ['ক্যাপসিকাম', 'pepper'], ['Bananas', 'banana'], ['কলা', 'banana'],
    ['Mangoes', 'mango'], ['আম', 'mango'], ['Pumpkins', 'pumpkin'], ['মিষ্টি কুমড়া', 'pumpkin'],
    ['Butternut squash', 'squash'], ['স্কোয়াশ', 'squash'], ['Apples', 'apple'], ['আপেল', 'apple'],
    ['Strawberries', 'strawberry'], ['স্ট্রবেরি', 'strawberry'], ['Grapes', 'grape'], ['আঙুর', 'grape'],
    ['Oranges', 'orange'], ['কমলা', 'orange'], ['Peaches', 'peach'], ['পীচ', 'peach'],
    ['Cherries', 'cherry'], ['চেরি', 'cherry'],
  ])('maps %s to matching %s produce', (name, crop) => {
    expect(cropImageFor(name)?.id).toBe(crop);
  });

  it.each(['Pineapple', 'Sweet potato', 'মিষ্টি আলু', 'চালকুমড়া', 'চাল কুমড়া', 'Bottle gourd',
    'Crabapple', 'Tomatometer', 'Tomato and potato mixed box', 'আমড়া', 'কলারমোচা', '', 'Organic vegetables'])
  ('keeps ambiguous or unknown %s generic instead of showing the wrong produce', name => {
    expect(cropImageFor(name)).toBeNull();
  });

  it('does not misread an unrecognised Bangla word as a short crop alias', () => {
    expect(cropImageFor('আমাদের খামারের সবজি')).toBeNull();
  });

  it('ships a local offline photo with usable attribution for every matched crop', () => {
    for (const name of ['tomato','potato','rice','maize','onion','carrot','eggplant','cucumber','chilli','pepper','banana','mango','pumpkin','squash','apple','strawberry','grape','orange','peach','cherry']) {
      const image=cropImageFor(name)!;
      expect(image.src).toMatch(/^\/crops\/[^/]+\.jpg$/);
      expect(existsSync(resolve('public',image.src.slice(1)))).toBe(true);
      expect(image.author.trim().length).toBeGreaterThan(0);
      expect(image.sourceUrl).toMatch(/^https:\/\/commons.wikimedia.org\/wiki\/File:/);
      expect(image.licenseUrl).toMatch(/^https:\/\//);
    }
  });
});
