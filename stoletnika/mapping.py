import re
from .template import colnum
from .category_fallback import nearest_category

# Ordered title/ingredient patterns, restricted to IDs in the supplied template.
# Combinations precede their individual ingredients.
CATEGORY_RULES=[
 ('17589',r'(?:глюкозамин.*хондроитин|хондроитин.*глюкозамин|glucosamine.*chondroitin|chondroitin.*glucosamine)'),
 ('17679',r'(?:omega|омега)\s*[- ]?3\s*[-–,/]\s*6\s*[-–,/]\s*9'),
 ('17705',r'(?:b|в)[ -]?(?:complex|комплекс)|комплекс.*(?:витамини?\s*в|vitamin\s*b)'),
 ('17712',r'prenatal|пренатал|витамини.*бремен'),
 ('17711',r'multivitamin|мултивитамин|мулти\s*витамин'),
 ('17604',r'витамини?\s+и\s+минерали|vitamins?\s*(?:&|and)\s*minerals?'),
 ('17615',r'multimineral|мулти\s*минерал'),
 ('17503',r'люцерна|alfalfa'),('17504',r'алое|aloe\s*vera'),('17505',r'артишок|artichoke'),
 ('17506',r'астрагал|astragal'),('17507',r'черен\s*кохош|black\s*cohosh|цимицифуга'),
 ('17508',r'кайен|cayenne'),('17509',r'лайка|chamomile'),('17510',r'канела|cinnamon'),
 ('17511',r'dong\s*quai|донг\s*куай'),('17512',r'ехинаце[яй]|echinacea'),
 ('17513',r'вечерна\s*иглика|evening\s*primrose'),('17515',r'чесън|garlic'),
 ('17516',r'джинджифил|ginger'),('17517',r'гинко|ginkgo'),('17518',r'женшен|ginseng'),
 ('17519',r'goldenseal|хидрастис'),('17520',r'зелен\s*чай|green\s*tea'),('17521',r'глог|hawthorn'),
 ('17522',r'epimedium|епимедиум|horny\s*goat'),('17523',r'kava\s*kava|кава'),
 ('17524',r'сладък\s*корен|женско\s*биле|licorice|glycyrrhiza'),('17525',r'muira\s*puama|муира'),
 ('17526',r'бял\s*трън|milk\s*thistle|silymarin|силимарин'),
 ('17527',r'рейши|шийтаке|гъб[аи]|reishi|shiitake|mushroom|кордицепс|cordyceps'),
 ('17528',r'\bneem\b|\bнийм\b'),('17529',r'коприва|nettle'),('17530',r'\bнони\b|\bnoni\b'),
 ('17531',r'маслинови?\s*лист|olive\s*leaf'),('17532',r'\bриган\b|oregano'),
 ('17533',r'червен\s*ориз|red\s*yeast\s*rice'),('17534',r'saw\s*palmetto|сао\s*палмето|палма\s*сабал|sabal'),
 ('17535',r'стевия|stevia'),('17536',r'жълт\s*кантарион|st.?\s*john|hypericum'),
 ('17537',r'бабини\s*зъби|tribulus|трибулус'),('17538',r'triphala|трифала'),
 ('17540',r'валериан|valerian'),('17541',r'yohimbe|йохимбе'),('17542',r'псилиум|psyllium|индийски\s*живовляк'),
 ('17543',r'bacopa|бакопа'),('17544',r'mucuna|мукуна'),('17545',r'gymnema|гимнема'),
 ('17547',r'хлорофил|chlorophyll'),('17548',r'shilajit|шилажит|мумийо'),('17549',r'cissus|цисус'),
 ('17550',r'тулси|tulsi|holy\s*basil|свещен\s*босилек'),
 ('17551',r'curcumin|куркумин'),('17539',r'куркума|turmeric|curcuma'),
 ('17552',r'хлорела|chlorella'),('17556',r'гугулу|guggul'),('17560',r'черна\s*боровинка|bilberry'),
 ('17567',r'ашваганда|ashwagandha|withania'),('17568',r'готу\s*кола|gotu\s*kola|centella'),
 ('17569',r'андро[гд]рафис|andrographis'),('17571',r'зелено\s*кафе|green\s*coffee'),
 ('17572',r'шатавари|shatavari'),('17575',r'бяла\s*ружа|marshmallow'),('17576',r'аир|calamus'),
 ('17577',r'гарциния|garcinia'),('17579',r'спирулина|spirulina'),('17585',r'босвелия|boswellia'),
 ('17587',r'хондроитин|chondroitin'),('17588',r'глюкозамин|glucosamine'),('17591',r'бромелаин|bromelain'),
 ('17593',r'лактаза|lactase'),('17594',r'липаза|lipase'),('17595',r'ензим|enzyme'),
 ('17605',r'пчелно\s*млечице|royal\s*jelly'),
 ('17608',r'калци[йя]|calcium'),('17609',r'хром\b|chromium'),('17610',r'мед\b|copper'),
 ('17611',r'йод|iodine|\bkelp\b|келп'),('17612',r'желязо|iron'),('17613',r'магнези[йя]|magnesium'),
 ('17614',r'манган|manganese'),('17616',r'кали[йя]|potassium'),('17617',r'селен|selenium'),
 ('17618',r'силици[йя]|silica'),('17621',r'цинк|zinc'),('17622',r'колаген|collagen'),
 ('17626',r'ресвератрол|resveratrol'),('17628',r'липо[еe]ва\s*киселина|lipoic'),
 ('17629',r'бета.?карот[еи]н|beta.?carotene'),('17630',r'коензим\s*q|coq\s*10|coenzyme\s*q'),
 ('17631',r'лутеин|lutein'),('17632',r'ликопен|lycopene'),('17633',r'пикногенол|pycnogenol|pine\s*bark'),
 ('17635',r'гроздов[оаи]\s*сем|grape\s*seed'),('17638',r'кверцетин|quercetin'),
 ('17639',r'биофлавоноид|bioflavonoid'),('17640',r'рутин|\brutin\b'),('17648',r'астаксантин|astaxanthin'),
 ('17663',r'\bmct\b|средноверижни\s*триглицериди'),('17665',r'\bdha\b'),
 ('17676',r'(?:omega|омега)[ -]?3'),('17677',r'(?:omega|омега)[ -]?6'),('17678',r'(?:omega|омега)[ -]?9'),
 ('17669',r'рибено\s*масло|fish\s*oil'),('17668',r'\bcla\b'),('17681',r'\bkrill\b|крил'),
 ('17682',r'черен\s*кимион|black\s*seed'),('17683',r'масло.*касис|black\s*currant'),
 ('17672',r'ленено\s*масло|flax\s*seed\s*oil|flaxseed\s*oil'),
 ('17685',r'фибри|pectin|пектин|dietary\s*fiber'),('17686',r'активен\s*въглен|charcoal'),
 ('17689',r'пробиотик|probiotic|acidophilus|ацидофилус'),('17691',r'пребиотик|prebiotic|инулин|inulin'),
 ('17692',r'хиалурон|hyaluron'),('17694',r'витамин\s*[aа]\b|vitamin\s*a\b'),
 ('17697',r'витамин\s*[bв]1\b|vitamin\s*b1\b|тиамин'),('17698',r'витамин\s*[bв]2\b|vitamin\s*b2\b|рибофлавин'),
 ('17699',r'витамин\s*[bв]3\b|vitamin\s*b3\b|ниацин|niacin'),
 ('17700',r'витамин\s*[bв]5\b|vitamin\s*b5\b|пантотен'),('17701',r'витамин\s*[bв]6\b|vitamin\s*b6\b|пиридоксин'),
 ('17702',r'фолиева|folic|витамин\s*[bв]9\b'),('17703',r'витамин\s*[bв]12\b|vitamin\s*b12\b|метилкобаламин'),
 ('17704',r'биотин|biotin|витамин\s*[bв]7\b'),('17706',r'инозитол|inositol'),
 ('17707',r'витамин\s*[cс]\b|vitamin\s*c\b|аскорбин'),('17708',r'витамин\s*[dд][ -]?[23]?\b|vitamin\s*d[ -]?[23]?\b'),
 ('17709',r'витамин\s*[eе]\b|vitamin\s*e\b'),('17710',r'витамин\s*[kк][ -]?1?\b|vitamin\s*k[ -]?1?\b'),
 ('17715',r'лецитин|lecithin'),('17716',r'холин\b|choline'),('17718',r'мелатонин|melatonin|sleep\s*aid')
]
OUTSIDE=r'спрей\s*за\s*(?:нос|крака|гърло)|вода\s*за\s*уста|мехлем|масажен\s*гел|интимен\s*гел|паста\s*за\s*зъби|крем\b'

def components(p):
    lines=p['description_lines'];result=[]
    for i,line in enumerate(lines):
        if re.match(r'^(?:състав(?:ки)?|съдържание|ingredients)\s*[:(]',line,re.I):
            result.append(line)
            for nxt in lines[i+1:]:
                if re.match(r'^(?:не съдържа|приложение|забележка|съхранение|производител|дозировка|начин|прием|действие|препоръ)',nxt,re.I):break
                result.append(nxt)
    return '\n'.join(dict.fromkeys(result))

def pick_category(p,template,override=None):
    if override:return str(override),'configured'
    title=p['name'].lower(); comp=components(p).lower()
    if re.search(OUTSIDE,title):return nearest_category(p,template,CATEGORY_RULES,comp)
    if re.search(r'билкова\s*програма',title) or (re.search(r'промо\s*пакет|комплект',title) and '+' in title):
        return nearest_category(p,template,CATEGORY_RULES,comp)
    minerals=[pat for _,pat in CATEGORY_RULES if re.search(r'калци|магнези|желяз|цинк|potassium',pat)]
    mineral_count=sum(bool(re.search(pat,title,re.I)) for pat in minerals)
    if mineral_count>=2:
        cid='17604' if re.search(r'витамин|vitamin',title,re.I) else '17615'
        return cid,'title combination'
    for cid,pat in CATEGORY_RULES:
        if cid in template.category_names and re.search(pat,title,re.I):return cid,'title'
    # Identify only the named active ingredient, not health claims or recommendations.
    match=re.match(r'^(?:състав(?:ки)?|съдържание|ingredients)\s*:\s*([^,;|]+)',comp,re.I)
    if match and p['brand_slug'] in ('herbalkan','bilka-chudodeyka'):
        for cid,pat in CATEGORY_RULES:
            if cid in template.category_names and re.search(pat,match[1],re.I):return cid,'first declared ingredient'
    return nearest_category(p,template,CATEGORY_RULES,comp)

def dosage_form(p):
    text=p['name']+' '+next((x for x in p['description_lines'] if x.lower().startswith('опаковка')), '')
    for pattern,form in [(r'gummies|гъми|желиран','Gummies'),(r'капсул|capsul|softgel|софтгел','Capsules'),(r'таблет|tablet','Tablets'),(r'прах|powder','Powder'),(r'тинктур|tincture|капки|drops|спрей|течност|масло|oil|\bмл\b|\bml\b','Liquid')]:
        if re.search(pattern,text,re.I):return form
    return ''

def neutral_description(p):
    # Preserve factual labels and instructions. Keep full source text in products.json.
    lines=[]
    for line in p['description_lines']:
        if re.match(r'^(?:опаковка|производител|състав(?:ки)?|други съставки|не съдържа|начин на|прием\s*:|дозировка|дневен прием|препоръчителна доза|съхранение|забележка|да не |възможно е да образува|продуктът е регистриран)',line,re.I):lines.append(line)
    comp=components(p)
    if comp:lines.append(comp)
    text=p['name']+'. '+' '.join(dict.fromkeys(lines))
    return re.sub(r'\s+',' ',text).strip()[:10000]

INGREDIENT_PATTERNS=[
 ('Vitamin B','Vitamin B12 (Cobalamin)',r'витамин\s*[bв]12|метилкобаламин|b12'),
 ('Vitamin B','Vitamin B9 (Folic Acid)',r'фолиева|folic|b9'),
 ('Vitamin B','Vitamin B6 (pyridoxine)',r'витамин\s*[bв]6\b|b6\b'),
 ('Vitamin B','Vitamin B7 (Biotin)',r'биотин|biotin'),
 ('Vitamin C','',r'витамин\s*[cс]\b|vitamin\s*c\b|аскорбин'),('Vitamin D','',r'витамин\s*[dд]3?\b|vitamin\s*d3?\b|холекалциферол'),
 ('Vitamin E','',r'витамин\s*[eе]\b|vitamin\s*e\b'),('Vitamin K','',r'витамин\s*[kк]2?\b|vitamin\s*k2?\b'),
 ('Plant-based Ingredients','Milk Thistle',r'бял\s*трън|milk\s*thistle'),('Plant-based Ingredients','Huang Qi',r'астрагал|astragal'),
 ('Plant-based Ingredients','Spirulina',r'спирулина|spirulina'),('Plant-based Ingredients','Curcumin',r'куркум|turmeric|curcumin'),
 ('Plant-based Ingredients','Chamomile',r'лайка|chamomile'),('Plant-based Ingredients','Caltrop',r'бабини\s*зъби|tribulus'),
 ('Plant-based Ingredients','Echinacea',r'ехинацея|echinacea'),('Plant-based Ingredients','Valerian',r'валериан|valerian'),
 ('Plant-based Ingredients','Hawthorn',r'глог|hawthorn'),('Plant-based Ingredients',"St. John's Wort",r'жълт\s*кантарион'),
 ('Plant-based Ingredients','Licorice Root',r'сладък\s*корен|женско\s*биле|licorice'),('Plant-based Ingredients','Grape Seeds',r'гроздов[оиа]\s*сем|grape\s*seed'),
 ('Plant-based Ingredients','Reishi Mushroom',r'рейши|reishi'),('Plant-based Ingredients','Sleeping Eggplant',r'ашваганда|ashwagandha'),
 ('Plant-based Ingredients','Ginger',r'джинджифил|ginger'),('Plant-based Ingredients','Olive Green Leaves',r'маслинови\s*лист'),
 ('Minerals','Calcium',r'калци[йя]|calcium'),('Minerals','Magnesium',r'магнези[йя]|magnesium'),('Minerals','Zinc',r'цинк|zinc'),
 ('Minerals','Iron',r'желязо|iron'),('Minerals','Selenium',r'селен|selenium'),('Minerals','Potassium',r'кали[йя]|potassium'),
 ('Coenzyme','Coenzyme Q10',r'коензим\s*q|coq10|coenzyme\s*q'),('Animal-derived Ingredients','Fish Oil',r'рибено\s*масло|fish\s*oil'),
 ('Fatty Acid','Docosahexaenoic Acid',r'\bdha\b'),('Fatty Acid','MCT',r'\bmct\b'),('Collagen','',r'колаген|collagen'),
 ('Probiotics','',r'пробиотик|probiotic'),('Dietary Fiber','',r'пектин|pectin|фибри'),('melatonin','',r'мелатонин|melatonin')
]

def map_row(p,t,config):
    override=config.get('overrides',{}).get(p['id'],{})
    cid,reason=pick_category(p,t,override.get('category_id'))
    warnings=[]
    if cid and cid not in t.category_names:raise ValueError('Configured category not in supplied template: '+cid)
    row={'E':cid,'G':'Normal product','L':re.sub(r'\s+',' ',p['name']).strip()[:500],'M':'ST-'+p['id'],'N':p['sku'],'O':'Add','T':neutral_description(p),
         'LA':p['stock'] if p['stock'] is not None else config.get('stock_if_unknown'),
         'LB':p['price_eur'],'LC':p['url'],'LD':p['list_price_eur'],'LE':'N/A' if p['list_price_eur'] is None else '',
         'LF':p['weight_g'] or config.get('default_weight_g'),
         'LJ':'Single set','LK':'No','LL':1,'LM':'piece','LU':config.get('shipping_template') or next(iter(t.choices('LU')),''),
         'LV':config.get('handling_time'),'LW':'I will ship this item myself'}
    dim=config.get('default_dimensions_cm')
    if dim:row.update(dict(zip(['LG','LH','LI'],dim)))
    if not cid:warnings.append(reason)
    elif reason.startswith('nearest:'):warnings.append('Closest available template category selected: '+t.category_names[cid])
    elif reason=='first declared ingredient':warnings.append('Confirm category selected by the first declared ingredient')
    for col,img in zip(t.columns('Detail Images URL'),p['images']):row[col]=img
    for col,img in zip(t.columns('SKU Images URL'),p['images']):row[col]=img
    brand=config.get('brands',{}).get(p['brand_slug'],{})
    if brand.get('brand') in t.choices('R',cid):
        row['R']=brand['brand'];tr=t.choices('S',cid,row)
        if len(tr)==1:row['S']=tr[0]
    manufacturer=brand.get('manufacturer')
    if not manufacturer:
        declared=' '.join(x for x in p['description_lines'] if x.lower().startswith('производител:'))
        manufacturer=next((m for m in t.choices('NY',cid) if m.lower() in declared.lower()),'')
    if manufacturer and manufacturer in t.choices('NY',cid):row['NY']=manufacturer
    elif cid:warnings.append('Manufacturer not confirmed against template choices')
    if brand.get('eu_responsible_person'):
        if brand['eu_responsible_person'] in t.choices('NZ',cid):row['NZ']=brand['eu_responsible_person']
        else:warnings.append('Configured EU responsible person not in template choices')
    declared=' '.join(x for x in p['description_lines'] if re.match(r'^(?:производител|произход|държава на произход)',x,re.I))
    country=brand.get('country_of_origin')
    for pat,c in [(r'Canada|Канада','Canada'),(r'България|Bulgaria','Bulgaria'),(r'Германия|Germany','Germany')]:
        if not country and re.search(pat,declared,re.I):country=c
    if country in t.choices('LY',cid):row['LY']=country
    form=dosage_form(p)
    if form in t.choices('HT',cid):row['HT']=form
    final='Liquid' if form=='Liquid' else ('Solid' if form in ('Capsules','Tablets','Gummies','Powder') else '')
    if final in t.choices('JZ',cid):row['JZ']=final
    comp=components(p)
    text=comp or p['name']
    if sum(bool(re.match(r'^(?:състав(?:ки)?|съдържание)\s*[:(]',line,re.I)) for line in p['description_lines'])>1:
        warnings.append('Multiple composition sections in source: verify against the label')
    # Place the title ingredient first, followed by other declared ingredients.
    prioritized=sorted(INGREDIENT_PATTERNS,key=lambda rule:0 if re.search(rule[2],p['name'],re.I) else 1)
    ingredients=[]
    for group,main,pat in prioritized:
        if re.search(pat,text,re.I):
            if group not in [g for g,_ in ingredients]:ingredients.append((group,[]))
            if main:next(v for g,v in ingredients if g==group).append(main)
    for (g,values),base,cols in zip(ingredients,['HW','IH','IS','JD','JO'],[['HX','HY','HZ','IA','IB','IC','ID','IE','IF','IG'],['II','IJ','IK','IL','IM','IN','IO','IP','IQ','IR'],['IT','IU','IV','IW','IX','IY','IZ','JA','JB','JC'],['JE','JF','JG','JH','JI','JJ','JK','JL','JM','JN'],['JP','JQ','JR','JS','JT','JU','JV','JW','JX','JY']]):
        if g in t.choices(base,cid,row):row[base]=g
        for col,v in zip(cols,values):
            if v in t.choices(col,cid,row):row[col]=v
    # Only assert sugar/cocoa absence with an explicit source statement.
    sugar=bool(re.search(r'захарна\s*тръстика|глюкозен\s*сироп|глюкозо.?фруктоз|\bsucrose\b|sugar\s*cane',comp,re.I))
    if sugar:row['KA']='Yes'
    elif any(re.match(r'^не съдържа',x,re.I) and re.search(r'захар|подсладител',x,re.I) for x in p['description_lines']):row['KA']='No'
    if re.search(r'какао|cocoa|chocolate',comp,re.I):row['KB']='Yes'
    # Net content comes from the sale name/packaging line, never a daily dose.
    size_text=p['name']+' '+next((x for x in p['description_lines'] if x.lower().startswith('опаковка:')),'')
    net=re.search(r'(\d+(?:[.,]\d+)?)\s*(мл|ml|литра|litre|\bg\b|\bгр\b|\bkg\b|\bкг\b)',size_text,re.I)
    count=re.search(r'(\d+)\s*(?:v.?капсул|растителни\s*капсул|софтгел\s*капсул|желирани\s*таблет|капс\.|капсул|таблет)',size_text,re.I)
    row['KC']='Size';row['KE']=p['variant_label'] or (net[0] if net else (count[0] if count else '1 опаковка'))
    if net:
        val=float(net[1].replace(',','.'));unit={'мл':'ml','ml':'ml','гр':'g','g':'g','kg':'kg','кг':'kg','литра':'l','litre':'l'}[net[2].lower()]
        row.update({'LP':val,'LQ':val,'LR':unit})
    elif count:row.update({'LP':int(count[1]),'LQ':int(count[1]),'LR':'count','LN':int(count[1]),'LO':'piece'})
    if re.search(r'(?:промо\s*пакет|комплект|\d+\s*броя|билкова\s*програма)',p['name'],re.I):
        pieces=re.search(r'(\d+)\s*броя',p['name'],re.I)
        if pieces and '+' not in p['name']:
            row['LJ']='Multi-piece set';row['LK']='Yes';row['LL']=int(pieces[1]);row['LM']='pack'
            if row.get('LP') is not None:row['LQ']=row['LP']*int(pieces[1])
        else:
            row['LJ']='Mixed set of different products';warnings.append('Mixed promotional bundle: verify category, component labels and quantities')
            pieces=re.search(r'(\d+)\s*(?:билкови\s*)?продукта',p['name'],re.I)
            if pieces:row.update({'LK':'Yes','LL':int(pieces[1]),'LM':'pack','LN':int(pieces[1]),'LO':'piece'})
    if p['barcode']:
        types=t.choices('LS',cid)
        typ='EAN' if len(p['barcode'])==13 else ('UPC' if len(p['barcode'])==12 else '')
        if typ in types:row['LS']=typ;row['LT']=p['barcode']
        else:warnings.append('Unsupported barcode format: '+p['barcode'])
    if row['LF'] is not None and p['weight_g'] is None:warnings.append('Configured default weight used')
    if dim:warnings.append('Configured default package dimensions used')
    row.update(override.get('cells',{}))
    # Every selected dropdown must match an actual allowed value.
    for col,value in list(row.items()):
        if value in (None,''):continue
        choices=t.choices(col,cid,row)
        if choices and str(value) not in choices:
            warnings.append('Invalid dropdown '+col+': '+str(value));row.pop(col,None)
    required=t.rules.get(cid+'_require',{})
    missing=[];seen=set()
    for col,state in required.items():
        if state!='require':continue
        header=t.headers.get(col,col)
        if header in seen:continue
        seen.add(header)
        same=t.columns(header)
        if header=='List Price - EUR' and row.get('LE')=='N/A':continue
        if not any(row.get(c) is not None and row.get(c)!='' for c in same):missing.append(col+' '+header)
    for important in ['LG','LH','LI']:
        if row.get(important) in (None,'') and not any(x.startswith(important+' ') for x in missing):missing.append(important+' '+t.headers[important])
    if not p['images']:warnings.append('No product photos found')
    if not cid:missing.insert(0,'E Category')
    return row,{'category_id':cid,'category_reason':reason,'missing_fields':missing,'warnings':warnings}
