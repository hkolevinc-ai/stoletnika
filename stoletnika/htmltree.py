"""Small, dependency-free HTML tree for the public CloudCart pages."""
from html.parser import HTMLParser
import re

class Node:
    def __init__(self, tag='', attrs=None, parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs or []), parent, []
    def get(self, key, default=''):
        return self.attrs.get(key, default)
    def has(self, cls):
        return cls in self.get('class').split()
    def all(self, tag=None, cls=None, attr=None):
        found=[]
        for c in self.children:
            if isinstance(c, Node):
                if (tag is None or c.tag==tag) and (cls is None or c.has(cls)) and (attr is None or attr in c.attrs): found.append(c)
                found.extend(c.all(tag,cls,attr))
        return found
    def first(self, tag=None, cls=None, attr=None):
        return next(iter(self.all(tag,cls,attr)),None)
    def text(self, sep=' '):
        parts=[]
        for c in self.children:
            parts.append(c.text(sep) if isinstance(c,Node) else c)
        return sep.join(parts)
    def clean(self):
        return re.sub(r'\s+',' ',self.text()).strip()

class Parser(HTMLParser):
    VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root=Node('root'); self.stack=[self.root]; self.feed(text)
    def handle_starttag(self, tag, attrs):
        n=Node(tag,attrs,self.stack[-1]); self.stack[-1].children.append(n)
        if tag not in self.VOID: self.stack.append(n)
    def handle_startendtag(self,tag,attrs):
        n=Node(tag,attrs,self.stack[-1]); self.stack[-1].children.append(n)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:
                del self.stack[i:]; break
    def handle_data(self,text):
        self.stack[-1].children.append(text)

def parse(text): return Parser(text).root
