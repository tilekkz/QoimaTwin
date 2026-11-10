from asset_common import *

def build():
    root=group('warehouse_environment')
    concrete=material('Concrete warm mineral','#B7B5A9',.92)
    joint=material('Concrete expansion joints','#92958D',.95)
    plaster=material('Warm corrugated wall','#D5D6CB',.8)
    ridge=material('Panel ribs','#C1C8C3',.75)
    steel=material('Architectural charcoal','#3B4C54',.5,.25)
    dark=material('Recess dark','#243238',.8)
    yellow=material('Safety golden yellow','#E4AD3D',.65)
    glass=material('Smoky clerestory glass','#9FBABC',.3,.15)
    silver=material('Pipe galvanized','#879C9F',.4,.4)
    red=material('Fire cabinet red','#AB4A38',.7)
    warm=material('Light diffuser','#F8DE9F',.6)
    node=next(n for n in warm.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    node.inputs['Emission Color'].default_value=(.7,.38,.09,1)
    node.inputs['Emission Strength'].default_value=.35
    box('floor__FLOOR',(10,-.08,9),(20,.16,18),concrete,root,.035)
    for x in range(4,20,4):box('Floor joint',(x,.0005,9),(.012,.001,18),joint,root,0)
    for z in range(3,18,3):box('Floor joint',(10,.0005,z),(20,.001,.012),joint,root,0)
    # Two cutaway walls: front and right open for an unobstructed miniature view.
    box('Left lower corrugated panel',(.08,1.35,9),(.12,2.7,18),plaster,root,0)
    box('Back lower corrugated panel',(10,1.35,17.92),(20,2.7,.12),plaster,root,0)
    box('Left crown panel',(.08,4.03,9),(.12,.34,18),plaster,root,0)
    box('Back crown panel',(10,4.03,17.92),(20,.34,.12),plaster,root,0)
    for z in [i*.24+.2 for i in range(74)]:
        box('Wall flute',(.152,1.35,z),(.025,2.65,.026),ridge,root,.004)
    for x in [i*.24+.2 for i in range(82)]:
        box('Wall flute',(x,1.35,17.85),(.026,2.65,.025),ridge,root,.004)
    for z in [.2,4.5,9,13.5,17.8]:
        box('Left structural post',(.2,2.1,z),(.22,4.2,.23),steel,root,.015)
        box('Column footing',(.2,.10,z),(.38,.20,.38),joint,root,.015)
        box('Column guard',(.31,.4,z),(.06,.6,.3),yellow,root,.01)
    for x in [.2,4.5,9,13.5,19.8]:
        box('Back structural post',(x,2.1,17.8),(.23,4.2,.22),steel,root,.015)
        box('Column footing',(x,.10,17.8),(.38,.2,.38),joint,root,.01)
        box('Column guard',(x,.4,17.68),(.3,.6,.06),yellow,root,.01)
    box('Left head beam',(.2,4.18,9),(.28,.22,18),steel,root,.015)
    box('Back head beam',(10,4.18,17.8),(20,.22,.28),steel,root,.015)
    for side in ['left','back']:
        for k in range(4):
            center=2.35+4.35*k
            if side=='left':
                box('Clerestory glass',(.09,3.3,center),(.10,.98,3.65),glass,root,.005)
                for y in [2.78,3.3,3.82]:box('Window mullion',(.2,y,center),(.08,.065,3.8),steel,root,.003)
                for offset in [-1.88,-.94,0,.94,1.88]:box('Window mullion',(.2,3.3,center+offset),(.08,1.1,.055),steel,root,.003)
            else:
                box('Clerestory glass',(center,3.3,17.91),(3.65,.98,.10),glass,root,.005)
                for y in [2.78,3.3,3.82]:box('Window mullion',(center,y,17.8),(3.8,.065,.08),steel,root,.003)
                for offset in [-1.88,-.94,0,.94,1.88]:box('Window mullion',(center+offset,3.3,17.8),(.055,1.1,.08),steel,root,.003)
    beam('Back service pipe',(.6,2.45,17.63),(19.3,2.45,17.63),.065,silver,root)
    beam('Left service pipe',(.4,2.45,.6),(.4,2.45,17.6),.065,silver,root)
    for x in [2,6,10,14,18]:
        box('Pipe mounting bracket',(x,2.45,17.71),(.075,.18,.12),yellow,root,.006)
        box('Wall light housing',(x,2.95,17.57),(.5,.22,.28),steel,root,.03)
        box('Wall light diffuser',(x,2.89,17.40),(.38,.11,.035),warm,root,.01)
    for z in [2,7,12,16]:
        box('Left wall light housing',(.37,2.95,z),(.28,.22,.5),steel,root,.02)
        box('Left wall light diffuser',(.53,2.89,z),(.035,.11,.38),warm,root,.008)
    for x in [3.2,11.5]:
        box('Vent recess',(x,1.9,17.69),(.78,.61,.18),dark,root,.025)
        box('Vent casing',(x,1.9,17.59),(.72,.55,.08),silver,root,.012)
        for k in range(6):box('Vent angled fin',(x,1.69+k*.085,17.53),(.65,.035,.065),steel,root,.004)
    box('Fire cabinet',(17.1,1.55,17.66),(.7,.8,.26),red,root,.025)
    box('Fire cabinet inset',(17.1,1.56,17.51),(.53,.62,.03),dark,root,.01)
    for r in [.22,.17,.12]:
        cylinder('Coiled fire hose',(17.1,1.57,17.485),r,.025,silver,root,'Z',20)
    box('Fire cabinet handle',(17.37,1.55,17.48),(.025,.18,.05),silver,root,.006)
    for x in [3,7,11,15]:
        for edge in [x-.88,x+.88]:box('Aisle safety marking',(edge,.003,8),(.035,.006,10.4),yellow,root,0)
    def zone(name,x,z,w,d):
        for zz in [z-d/2,z+d/2]:box(name,(x,.004,zz),(w,.007,.055),yellow,root,0)
        for xx in [x-w/2,x+w/2]:box(name,(xx,.004,z),(.055,.007,d),yellow,root,0)
    zone('Packing zone',9,.8,3.2,1.4)
    zone('Buffer zone',18,.82,1.8,1.5)
    zone('Static forklift parking',18.2,10.4,2.5,3.5)
    return root

if __name__=='__main__':
    reset()
    finish('environment',build())
