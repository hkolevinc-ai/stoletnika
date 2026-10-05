"""Closest available template category when an exact category is unavailable.

This changes categorization only. Product titles, descriptions and declared
ingredients are never changed to match an approximate category.
"""
import re

# Additional literal ingredient names and product types present in the template.
EXTRA_RULES = [
    ('17705', r'(?:\b[bв]\s*\d{0,3}\s*(?:комплекс|комлекс|complex|comlex)|витамин.*[bв]\s*стрес)'),
    ('17618', r'biosil|силициев(?!\s*(?:диоксид|двуокис))|silicic'),
    ('17625', r'\bdmae\b|диметиламиноетанол'),
    ('17643', r'антиоксидант.*(?:комплекс|формула|комбинац)|antioxidant.*(?:complex|formula|combination)'),
    ('17645', r'колоидно?\s*сребро|colloidal\s*silver'),
    ('17646', r'колоидно?\s*злато|colloidal\s*gold'),
    ('17670', r'7.?keto|7.?кето'),
    ('17671', r'\bepa\b|ейкозапентаен'),
    ('17689', r'\b(?:пробиот|синбиот|symbiot|synbiot)|\b(?:travel|calm|relief|ibs|мулти)[ -]?(?:биотик|biotic)'),
    ('17527', r'гъб|mushroom|лъвска\s*грива|херициум|hericium|кладница|чага|maitake|майтаке'),
    ('17514', r'ленено?\s*семе|flax\s*seed|flaxseed'),
    ('17546', r'пипали|pippali'), ('17553', r'нисот|nisoth'),
    ('17554', r'трикату|trikatu'), ('17555', r'гилой|giloy'),
    ('17557', r'\bbael\b|баел'), ('17558', r'папая.*лист|papaya\s*leaf'),
    ('17573', r'карела|karela'), ('17574', r'манджишта|manjishtha'),
    ('17580', r'харитаки|haritaki'), ('17581', r'арджуна|arjuna'),
    ('17582', r'камфор|camphor'), ('17583', r'васака|vasaka'),
    ('17584', r'пунарнава|punarnava'),
]

# Explicit approximations to the nearest available ingredient/product group.
# No unavailable ID, invented ingredient, or medical claim is written to Excel.
NEAREST_RULES = [
    ('17710', r'витамин\s*[kк]\s*2\b|vitamin\s*k\s*2\b|\bmk.?7\b|менахинон', 'vitamin K group; K2 leaf absent'),
    ('17605', r'прополис|propolis|пчелен\s*прашец|bee\s*pollen', 'bee-product supplement group'),
    ('17663', r'кокос|coconut', 'nutritional coconut-oil group'),
    ('17560', r'боровин|blueberry|cranberry|череш|cherry|арони|aronia|годжи|goji|акай|acai|шипк|rosehip', 'fruit/berry extract group'),
    ('17518', r'мака\b|\bmaca\b|левзе|leuzea|родиол|rhodiola|златен\s*корен|елеутеро', 'plant-root extract group'),
    ('17509', r'турта|tagetes|невен|calendula|равнец|yarrow|безсмъртнич|helichrysum|вратига|feverfew|теменуг|violet|липа\b|linden|лавандул|lavender|шафран|saffron', 'flower/herb extract group'),
    ('17515', r'левурда|wild\s*garlic|allium\s*ursinum', 'garlic-type herb group'),
    ('17532', r'мента|mint|мащерк|thyme|риган|oregano|салвия|salvia|градински\s*чай|кардамон|cardamom|мурсалски', 'aromatic-herb group'),
    ('17505', r'глухарче|dandelion|репей|burdock|dandelin', 'plant-root/leaf herbal extract group'),
    ('17529', r'бреза|birch|златна\s*пръчица|goldenrod|живовляк|plantain|хвощ|horsetail|еньовч|лепка|целина|celery|черница|mulberry|смокин|малина|ягода\s*лист|къпина', 'leaf/whole-herb extract group'),
    ('17575', r'лише[йя]|lichen|уснеа|usnea|лопен|mullein|медуница|lungwort', 'herbal preparation group'),
    ('17633', r'кора\b|\bbark\b', 'botanical bark-extract group'),
    ('17718', r'сън|sleep|релакс|relax|calm|серен|sereni|безсън|шлемник|skullcap|габа\b|\bgaba\b|theanine|теанин', 'herbal/nutritional relaxation product group'),
    ('17622', r'аминокисел|amino\s*acid|протеин|protein|лизин|lysine|аргинин|arginine|глутамин\b|glutamine|тирозин|tyrosine|карнитин|carnitine|яйчена\s*мембрана|eggshell|\bnem\b', 'protein/amino-acid nutritional supplement group'),
    ('17643', r'глутатион|glutathione|\bpqq\b|митохондр|mitochond|антиоксидант|antioxidant|phosphatidyl|фосфатидил|\bps\b', 'antioxidant/nutritional combination group'),
    ('17589', r'\bmsm\b|\bмсм\b|osteo.?move|остео.?муув|целадрин|celadrin', 'joint nutritional supplement group'),
    ('17669', r'cod\s*liver\s*oil|масло.*треска|сьомга|salmon\s*oil', 'fish-oil supplement group'),
    ('17685', r'\bpgx\b|fib(?:re|er)|фибр|pectin|пектин|vinegar|оцет', 'dietary-fiber/digestive nutritional product group'),
    ('17595', r'бетаин|betaine|digest|храносмил|глутен|gluten|starch', 'digestive nutritional product group'),
    ('17615', r'морски\s*минерал|ocean\s*minerals|multimineral|мултиминерал', 'multi-mineral supplement group'),
]

def nearest_category(p, template, exact_rules, composition):
    """Use the main item, declared ingredients, then its source product group."""
    available = template.category_names
    title = p.get('name', '')
    main = re.split(r'\s*\+\s*', title, maxsplit=1)[0]
    def match(rules, text, label, by_position=False):
        hits=[]
        for rule in rules:
            cid, pattern = rule[:2]
            found=re.search(pattern, text, re.I)
            if cid in available and found:
                detail = rule[2] if len(rule)>2 else label
                if not by_position:return cid, 'nearest: ' + detail
                hits.append((found.start(),cid,detail))
        if hits:
            _,cid,detail=min(hits,key=lambda hit:hit[0])
            return cid,'nearest: '+detail
        return None

    # Known ingredient in the principal product also handles mixed bundles and
    # topical products that have no product-type category in this template.
    for rules in (EXTRA_RULES, exact_rules, NEAREST_RULES):
        result = match(rules, main, 'principal product ingredient')
        if result:
            return result
    # Carrier oils, water, alcohol and capsule shells are not primary ingredients.
    cleaned = re.split(r'\b(?:други\s*съставки|other\s*ingredients|помощни\s*(?:съставки|вещества)|микрокристална\s*целулоза|растителна\s*капсула|vegetable\s*capsule|magnesium\s*stearate|магн[еи]зиев\s*стеарат)\b',composition,maxsplit=1,flags=re.I)[0]
    cleaned = re.sub(r'(?:носител|carrier|капсулна\s*обвивка|capsule\s*shell)\s*:[^\n]*', '', cleaned, flags=re.I)
    first = re.split(r'[,;|\n]', re.sub(r'^(?:състав(?:ки)?|съдържание|ingredients)\s*:\s*', '', cleaned, flags=re.I), maxsplit=1)[0]
    for text, label in [(first, 'first declared ingredient'), (cleaned, 'declared composition')]:
        result=match([*EXTRA_RULES,*exact_rules,*NEAREST_RULES],text,label,by_position=True)
        if result:return result

    group = p.get('site_category', '')
    group_rules = [
        ('17689', r'пробиоти|probiotic'), ('17615', r'минерал|mineral'),
        ('17622', r'протеин|protein|аминокисел|amino'),
        ('17643', r'антиоксидант|antioxidant'),
        ('17718', r'безсън|sleep|стрес|stress'),
        ('17604', r'витамин|vitamin'),
    ]
    result = match(group_rules, group, 'source product group')
    if result:
        return result
    herbal = p.get('brand_slug') in ('herbalkan', 'bilka-chudodeyka') or re.search(r'билков|тинктур|herbal|tincture', title + ' ' + group, re.I)
    fallback = ['17509', '17529', '17538'] if herbal else ['17604', '17711', '17643']
    for cid in fallback:
        if cid in available:
            return cid, 'nearest: general ' + ('herbal preparation' if herbal else 'nutritional supplement') + ' group; exact leaf absent'
    if not available:
        raise ValueError('The supplied template has no categories')
    # A different template still receives its broadest existing supplement leaf.
    cid = min(available, key=lambda c:(len(available[c].split(' / ')), int(c)))
    return cid, 'nearest: broadest available template category'
