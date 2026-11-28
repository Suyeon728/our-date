"""Build a national offline POI database from the South Korea OSM extract.
Run with Python 3.12, osmium and shapely installed. Data: ODbL.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
from collections import Counter

PROVINCES = dict(zip('11 26 27 28 29 30 31 36 41 42 43 44 45 46 47 48 49 51 52'.split(), '서울 부산 대구 인천 광주 대전 울산 세종 경기 강원 충북 충남 전북 전남 경북 경남 제주 강원 전북'.split()))
FULL = dict(zip('서울 부산 대구 인천 광주 대전 울산 세종 경기 강원 충북 충남 전북 전남 경북 경남 제주'.split(), '서울특별시 부산광역시 대구광역시 인천광역시 광주광역시 대전광역시 울산광역시 세종특별자치시 경기도 강원특별자치도 충청북도 충청남도 전북특별자치도 전라남도 경상북도 경상남도 제주특별자치도'.split()))

def place_kind(t):
    a=t.get('amenity',''); s=t.get('shop','')
    if a in ('cafe','library','restaurant','ice_cream'): return a
    if s in ('bakery','confectionery','pastry'): return 'bakery' if s=='pastry' else s
    return None

def province_name(t):
    iso=t.get('ISO3166-2','')
    if iso.startswith('KR-') and iso[3:] in PROVINCES: return PROVINCES[iso[3:]]
    name=t.get('name:ko') or t.get('name','')
    for p,full in FULL.items():
        if name in (p,full) or name in {'강원':('강원도',),'전북':('전라북도',)}.get(p,()): return p
    return ''

def assign(rows, provinces, districts):
    from shapely.geometry import Point
    from shapely.strtree import STRtree
    from shapely import make_valid
    provinces=[(p,make_valid(g)) for p,g in provinces if not g.is_empty]
    districts=[(d,make_valid(g)) for d,g in districts if not g.is_empty]
    p_tree=STRtree([g for _,g in provinces]); d_tree=STRtree([g for _,g in districts]); counts=Counter(); centers={}
    def province_at(pt):
        hits=p_tree.query(pt,predicate='intersects')
        return provinces[min(hits,key=lambda i:provinces[i][1].area)][0] if len(hits) else ''
    for d,g in districts:
        pt=g.representative_point(); p=province_at(pt)
        if p: centers.setdefault(p+' '+d,{'lat':round(pt.y,6),'lon':round(pt.x,6)})
    for p,g in provinces:
        pt=g.representative_point(); centers.setdefault(p,{'lat':round(pt.y,6),'lon':round(pt.x,6)})
    for x in rows.values():
        pt=Point(x['lon'],x['lat']); p=province_at(pt)
        if not p: continue
        hits=d_tree.query(pt,predicate='intersects')
        # A city-level district takes precedence over its subordinate gu where both exist.
        names=[districts[i][0] for i in hits]
        cities=[n for n in names if n.endswith(('시','군'))]
        d=sorted(cities or names)[0] if names else ('세종시' if p=='세종' else '')
        x.update(province=p,district=d,region=(p+' '+d).strip());counts[p]+=1
    return counts,centers

def build(pbf,output):
    import osmium
    from shapely import wkb
    from shapely.geometry import Point
    factory=osmium.geom.WKBFactory()
    rows={}; provinces=[];districts=[]
    def add(t,ident,lat,lon):
        kind=place_kind(t); name=t.get('name:ko') or t.get('name','')
        if not kind or not name or not (32<lat<40 and 124<lon<132):return
        x={'id':ident,'name':name,'kind':kind,'lat':round(lat,6),'lon':round(lon,6)}
        for src,dst in [('cuisine','cuisine'),('opening_hours','open'),('brand','brand'),('operator','operator'),('brand:wikidata','brand_wikidata'),('franchise','franchise'),('description','description'),('internet_access','wifi'),('power_supply','power')]:
            v=t.get(src,'')
            if v: x[dst]=v[:250]
        rows[ident]=x
    class Handler(osmium.SimpleHandler):
        def node(self,n):
            if place_kind(n.tags) and n.location.valid():add(n.tags,'node/'+str(n.id),n.location.lat,n.location.lon)
        def way(self,w):
            if not place_kind(w.tags):return
            coords=[(n.location.lon,n.location.lat) for n in w.nodes if n.location.valid()]
            if coords:add(w.tags,'way/'+str(w.id),sum(y for x,y in coords)/len(coords),sum(x for x,y in coords)/len(coords))
        def area(self,a):
            t=a.tags; boundary=t.get('boundary')=='administrative'; level=t.get('admin_level',''); k=place_kind(t)
            if not k and not (boundary and level in ('4','5','6','7','8')):return
            try:g=wkb.loads(factory.create_multipolygon(a),hex=True)
            except Exception:return
            if g.is_empty:return
            if k:
                pt=g.representative_point();add(t,('way/' if a.from_way() else 'relation/')+str(a.orig_id()),pt.y,pt.x)
            if boundary:
                name=t.get('name:ko') or t.get('name','');p=province_name(t)
                if level=='4' and p:provinces.append((p,g))
                elif level in ('5','6','7','8') and re.fullmatch(r'[가-힣]+[시군구]',name):districts.append((name,g))
    Handler().apply_file(str(pbf),locations=True,idx='flex_mem')
    counts,centers=assign(rows,provinces,districts)
    # Never replace a usable DB with a corrupt/empty or geographically incomplete extract.
    if len(counts)<14 or len(rows)<5000 or len(centers)<100:raise RuntimeError(f'Incomplete national extract: {dict(counts)}, {len(rows)} places, {len(centers)} centers')
    # Keep valid points even when a boundary is missing; spatial queries can still find them.
    output=Path(output);tmp=output.with_suffix('.tmp');payload={'updated':dt.datetime.now(dt.timezone.utc).isoformat(),'coverage':'national-osm','source':'OpenStreetMap contributors / Geofabrik','license':'ODbL-1.0','regions':sorted(counts),'region_counts':dict(counts),'centers':centers,'places':list(rows.values())}
    tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    if tmp.stat().st_size>90_000_000:tmp.unlink();raise RuntimeError('DB exceeds safe GitHub file size')
    os.replace(tmp,output);print('Nationwide places:',len(rows),'by province:',dict(counts),'centers:',len(centers),flush=True)

if __name__=='__main__':
    build(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else 'places.json')
