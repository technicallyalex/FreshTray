"""Rounded nine-slice surfaces; native ttk inputs retain keyboard/edit behavior."""
import tkinter as tk

from functools import lru_cache

@lru_cache(maxsize=8)
def corner_coverage(radius,size=20):
    def inside(x,y,inset):
        lo,hi=inset,size-inset;r=max(0,radius-inset)
        dx=max(lo+r-x,0,x-(hi-r));dy=max(lo+r-y,0,y-(hi-r))
        return lo<=x<hi and lo<=y<hi and dx*dx+dy*dy<=r*r
    result=[]
    for y in range(size):
        row=[]
        for x in range(size):
            counts=[0,0,0]
            for a in (.125,.375,.625,.875):
                for b in (.125,.375,.625,.875):
                    counts[0 if inside(x+a,y+b,1) else 1 if inside(x+a,y+b,0) else 2]+=1
            row.append(tuple(counts))
        result.append(tuple(row))
    return tuple(result)

def rounded_image(root, fill, border, outside, radius=6):
    image=tk.PhotoImage(master=root,width=20,height=20)
    colors=[tuple(int(c[i:i+2],16) for i in (1,3,5)) for c in (fill,border,outside)]
    rows=[]
    for row in corner_coverage(radius):
        pixels=['#'+''.join(f'{round(sum(colors[i][k]*counts[i] for i in range(3))/16):02x}' for k in range(3)) for counts in row]
        rows.append('{'+ ' '.join(pixels)+'}')
    image.put(' '.join(rows))
    return image


def apply_refinement(appearance):
    s,p=appearance.style,appearance.palette
    if not hasattr(appearance,'surface_cache'):
        appearance.surface_cache={}
        appearance.native_button_layout=s.layout('TButton')
        appearance.native_fields={n:s.layout(n) for n in ('TEntry','TCombobox','TSpinbox')}
        appearance.native_check_layout=s.layout('TCheckbutton')
    key=appearance.current
    if key not in appearance.surface_cache:
        images=[]
        def element(label,fill,border,host,hover=None,focus=None):
            name=f'Refined.{key}.{label}'
            base=rounded_image(appearance.root,fill,border,host);images.append(base)
            states=[]
            for state,color,edge in [('disabled',p['subtle'],p['border']),('pressed',hover or p['selection'],border),('active',hover or p['hover'],border),('focus',fill,focus or p['blue'])]:
                im=rounded_image(appearance.root,color,edge,host);images.append(im);states.append((state,im))
            s.element_create(name,'image',base,*states,border=4,sticky='nsew')
            return name
        specs={}
        specs['TButton']=element('button',p['panel'],p['border'],p['panel'])
        specs['Accent.TButton']=element('primary',p['accent'],p['accent'],p['panel'],p['accent_hover'])
        specs['Nav.TButton']=element('nav',p['panel'],p['panel'],p['panel'])
        specs['NavActive.TButton']=element('selectednav',p['blue'],p['blue'],p['panel'],p['blue'])
        specs['SelectedDay.TButton']=element('date',p['blue'],p['blue'],p['panel'],p['blue'])
        specs['field']=element('field',p['field'],p['border'],p['panel'],p['field'])
        card=rounded_image(appearance.root,p['panel'],p['border'],p['bg'],7);images.append(card)
        cardname=f'Refined.{key}.card'
        s.element_create(cardname,'image',card,border=7,sticky='nsew')
        unchecked=rounded_image(appearance.root,p['field'],p['border'],p['panel'],4)
        checked=rounded_image(appearance.root,p['blue'],p['blue'],p['panel'],4)
        for x,y in [(6,10),(7,11),(8,12),(9,13),(10,12),(11,11),(12,10),(13,9),(14,8)]:
            for dx,dy in ((0,0),(1,0),(0,1)):
                checked.put('#FFFFFF',to=(x+dx,y+dy))
        images.extend((unchecked,checked))
        checkname=f'Refined.{key}.check'
        s.element_create(checkname,'image',unchecked,('selected',checked),sticky='')
        specs['check']=checkname
        appearance.surface_cache[key]=(images,specs,cardname)
    images,specs,cardname=appearance.surface_cache[key]
    for style in ('TButton','Accent.TButton','Nav.TButton','NavActive.TButton','SelectedDay.TButton'):
        s.layout(style,[(specs[style],{'sticky':'nsew','children':[('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})])
    for style in ('MonthDay.TButton','SelectedMonthDay.TButton'):
        s.layout(style,appearance.native_button_layout)
    def fields(layout):
        result=[]
        for name,opts in layout:
            opts=dict(opts)
            if name.endswith('.field'):name=specs['field']
            if 'children' in opts:opts['children']=fields(opts['children'])
            result.append((name,opts))
        return result
    for name in appearance.native_fields:
        s.layout(name,fields(appearance.native_fields[name]))
        s.configure(name,padding=3)
    s.layout('Card.TFrame',[(cardname,{'sticky':'nsew'})])
    s.configure('TButton',padding=(10,3))
    s.configure('Nav.TButton',padding=(12,3),foreground=p['muted'])
    s.configure('NavActive.TButton',padding=(12,3),foreground='#FFFFFF')
    s.map('NavActive.TButton',foreground=[('!disabled','#FFFFFF')])
    s.configure('Navigation.TFrame',background=p['panel'])

    def checks(layout):
        result=[]
        for name,opts in layout:
            opts=dict(opts)
            if name.endswith('.indicator'):name=specs['check']
            if 'children' in opts:opts['children']=checks(opts['children'])
            result.append((name,opts))
        return result
    s.layout('TCheckbutton',checks(appearance.native_check_layout))
    s.configure('TCombobox',background=p['field'])
    s.configure('TSpinbox',background=p['field'])
