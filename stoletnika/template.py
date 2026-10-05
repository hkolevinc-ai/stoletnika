"""Read Temu metadata and preserve every native Excel part when filling rows.

Only Template/sheetData is patched. No third-party spreadsheet library is
required on GitHub, and the original dropdowns and merchant settings survive.
"""
import zipfile,xml.etree.ElementTree as E,re,posixpath
from xml.sax.saxutils import escape

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
N={'m':NS}
def colnum(col):
    n=0
    for c in col:n=n*26+ord(c)-64
    return n
def colname(n):
    s=''
    while n:n,r=divmod(n-1,26);s=chr(65+r)+s
    return s

class Template:
    def __init__(self,path):
        self.path=path;self.zip=zipfile.ZipFile(path)
        self.strings=[''.join(x.itertext()) for x in E.fromstring(self.zip.read('xl/sharedStrings.xml')).findall('m:si',N)] if 'xl/sharedStrings.xml' in self.zip.namelist() else []
        w=E.fromstring(self.zip.read('xl/workbook.xml'))
        rels={x.get('Id'):x.get('Target') for x in E.fromstring(self.zip.read('xl/_rels/workbook.xml.rels'))}
        self.sheets={s.get('name'):posixpath.normpath(posixpath.join('xl',rels[s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')])) for s in w.find('m:sheets',N)}
        self.sheets={k:(v.lstrip('/') if v.startswith('/xl/') else v) for k,v in self.sheets.items()}
        self.sheet_xml=self.zip.read(self.sheets['Template']).decode('utf-8')
        root=E.fromstring(self.sheet_xml);self.rows=root.find('m:sheetData',N)
        self.headers={re.sub(r'\d+$','',c.get('r')):self.value(c) for c in self.rows.find("m:row[@r='2']",N)}
        self.keys={re.sub(r'\d+$','',c.get('r')):self.value(c) for c in self.rows.find("m:row[@r='4']",N)}
        self.category_names={str(v[0]):v[1] for v in self.values('Category Name') if len(v)>1}
        self.dropdowns={v[0]:list(dict.fromkeys(v[2:])) for v in self.values('Dropdown Lists') if len(v)>2}
        self.rules={}
        for row in self.read_rows('GoodsLevelMode'):
            key=row.get('A','')
            if '_' in key:self.rules[key]=row
        self.start_row=5
        self.styles={re.sub(r'\d+$','',c.get('r')):c.get('s','') for c in self.rows.find("m:row[@r='5']",N)}
    def value(self,c):
        v=c.find('m:v',N)
        if c.get('t')=='s':return self.strings[int(v.text)] if v is not None else ''
        if c.get('t')=='inlineStr':return ''.join(c.find('m:is',N).itertext())
        return v.text if v is not None else ''
    def read_rows(self,name):
        root=E.fromstring(self.zip.read(self.sheets[name]))
        return [{re.sub(r'\d+$','',c.get('r')):self.value(c) for c in r} for r in root.findall('m:sheetData/m:row',N)]
    def values(self,name):return [list(r.values()) for r in self.read_rows(name)]
    def choices(self,col,category='',row=None):
        row=row or {};header=self.headers.get(col,'');key=self.keys.get(col,'')
        prefix=key.split('_',2)[:2];base='_'.join(prefix)+'_'
        candidates=[]
        if category:
            # Conditional fields use the parent selection in their lookup key.
            parents={'HW':['HX','HY','HZ','IA','IB','IC','ID','IE','IF','IG'],'IH':['II','IJ','IK','IL','IM','IN','IO','IP','IQ','IR'],'IS':['IT','IU','IV','IW','IX','IY','IZ','JA','JB','JC'],'JD':['JE','JF','JG','JH','JI','JJ','JK','JL','JM','JN'],'JO':['JP','JQ','JR','JS','JT','JU','JV','JW','JX','JY']}
            for parent,children in parents.items():
                if col in children and row.get(parent):candidates.append(base+category+'_'+row[parent]+'_'+header)
            if col=='KA' and row.get('JZ'):candidates.append(base+category+'_'+row['JZ']+'_'+header)
            candidates.append(base+category+'_'+header)
        if col=='S' and row.get('R'):candidates.append(base+row['R']+'_'+header)
        candidates.append(base+header)
        for candidate in candidates:
            if candidate in self.dropdowns:return self.dropdowns[candidate]
        return []
    def columns(self,header):return [c for c,h in self.headers.items() if h==header]
    def write(self,out,records):
        if len(records)>4996:raise ValueError('Temu template supports at most 4996 variant rows')
        # Preserve the original top four header/technical rows byte for byte.
        match=re.search(r'(<sheetData[^>]*>)(.*?)(</sheetData>)',self.sheet_xml,re.S)
        if not match:raise ValueError('Unrecognized native Temu worksheet format')
        header=''.join(m.group(0) for m in re.finditer(r'<row\b[^>]*\br="(\d+)"[^>]*>.*?</row>',match[2],re.S) if int(m[1])<5)
        new=[]
        for i,row in enumerate(records,5):
            cells=[]
            for col,value in sorted(row.items(),key=lambda kv:colnum(kv[0])):
                if value is None or value=='':continue
                ref=col+str(i);style=f' s="{self.styles[col]}"' if self.styles.get(col) else ''
                if isinstance(value,(int,float)) and not isinstance(value,bool):cells.append(f'<c r="{ref}"{style}><v>{value}</v></c>')
                else:
                    text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value))[:32767]
                    cells.append(f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>')
            # The native Category Name formula remains live.
            if 'E' in row and 'F' not in row:
                formula=f'IFERROR(VLOOKUP(E{i},\'Browse Data\'!A:B,2,FALSE),"")'
                formula_style=f' s="{self.styles["F"]}"' if self.styles.get('F') else ''
                cells.append(f'<c r="F{i}"{formula_style} t="str"><f>{escape(formula)}</f><v>{escape(self.category_names.get(str(row["E"]),""))}</v></c>')
            # Excel cells must stay in column order even when Category is blank.
            cells.sort(key=lambda cell:colnum(re.search(r'\br="([A-Z]+)\d+"',cell)[1]))
            new.append(f'<row r="{i}">'+''.join(cells)+'</row>')
        # Blank rows need not be serialized. Native validation ranges stay at 5000.
        data=match[1]+header+''.join(new)+match[3]
        result=self.sheet_xml[:match.start()]+data+self.sheet_xml[match.end():]
        result=re.sub(r'<dimension\b[^>]*/>',f'<dimension ref="A1:OA{max(4,len(records)+4)}"/>',result,count=1)
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as output:
            for info in self.zip.infolist():output.writestr(info.filename,result.encode('utf-8') if info.filename==self.sheets['Template'] else self.zip.read(info.filename))
