import credits from '../../public/crops/credits.json';

export type CropImage = {id:string;src:string;author:string;sourceUrl:string;license:string;licenseUrl:string};

// Unicode letters AND marks stay together: JS \b would split Bangla vowel signs.
function words(value:string):string[] {
  return value.normalize('NFKC').toLocaleLowerCase('en').match(/[\p{L}\p{M}\p{N}]+/gu)||[];
}
const aliases:Record<string,string[]>={
  tomato:['tomato','tomatoes','cherry tomato','cherry tomatoes','টমেটো'],
  potato:['potato','potatoes','আলু'],
  rice:['rice','paddy','চাল','ধান'],
  maize:['maize','corn','ভুট্টা'],
  onion:['onion','onions','পেঁয়াজ','পিঁয়াজ','পেঁয়াজ'],
  carrot:['carrot','carrots','গাজর'],
  eggplant:['eggplant','eggplants','aubergine','aubergines','brinjal','brinjals','বেগুন'],
  cucumber:['cucumber','cucumbers','শসা'],
  chilli:['chilli','chillies','chili','chilies','chili pepper','chilli pepper','chili peppers','chilli peppers','মরিচ','মরিচের','লঙ্কা'],
  pepper:['pepper','peppers','bell pepper','bell peppers','capsicum','ক্যাপসিকাম'],
  banana:['banana','bananas','কলা'],
  mango:['mango','mangoes','mangos','আম'],
  pumpkin:['pumpkin','pumpkins','কুমড়া','কুমড়া','মিষ্টি কুমড়া','মিষ্টি কুমড়া'],
  squash:['squash','butternut squash','স্কোয়াশ','স্কোয়াশ'],
  apple:['apple','apples','আপেল'],
  strawberry:['strawberry','strawberries','স্ট্রবেরি'],
  grape:['grape','grapes','আঙুর','আঙ্গুর'],
  orange:['orange','oranges','কমলা'],
  peach:['peach','peaches','পীচ','পিচ'],
  cherry:['cherry','cherries','চেরি'],
};
const phrases=Object.entries(aliases).flatMap(([id,names])=>names.map(name=>({id,tokens:words(name)})))
  .sort((a,b)=>b.tokens.length-a.tokens.length);
// Unsupported distinct produce/processed goods must not inherit a similar name.
const excluded=['sweet potato','sweet potatoes','মিষ্টি আলু','চাল কুমড়া','চাল কুমড়া','wax gourd','bottle gourd',
  'sugar apple','custard apple','rose apple','wood apple','star apple','banana pepper','black pepper','white pepper',
  'juice','jam','sauce','ketchup','powder','flour','chips','seed','seeds','চারা','বীজ','রস','আচার'].map(words);
function hasAt(tokens:string[],phrase:string[],start:number):boolean {
  return phrase.every((part,offset)=>tokens[start+offset]===part);
}

/** Names are hints only. Mixed/unknown listings keep the neutral placeholder. */
export function cropImageFor(name:string):CropImage|null {
  const tokens=words(name);
  if(excluded.some(phrase=>tokens.some((_,i)=>hasAt(tokens,phrase,i))))return null;
  const used=new Set<number>();
  const matches=new Set<string>();
  for(const phrase of phrases) {
    for(let i=0;i<tokens.length;i++) {
      if(hasAt(tokens,phrase.tokens,i)&&phrase.tokens.every((_,j)=>!used.has(i+j))) {
        matches.add(phrase.id);
        phrase.tokens.forEach((_,j)=>used.add(i+j));
      }
    }
  }
  if(matches.size!==1)return null;
  return credits.find(image=>image.id===[...matches][0])||null;
}
