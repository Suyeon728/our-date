import json, urllib.request, urllib.parse, time, pathlib, datetime
P=pathlib.Path('places.json'); old=json.loads(P.read_text()) if P.exists() else {'places':[],'regions':[]}; data={x['id']:x for x in old['places']}; done=set(old['regions']); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
regions='여수 순천 광양 목포 나주 담양 곡성 구례 고흥 보성 화순 장흥 강진 해남 영암 무안 함평 영광 장성 완도 진도 신안'.split()+['광주','남원','하동','진주','사천','산청','남해','임실','순창']; success=0
for i,r in enumerate(regions):
 suffix={'광주':'광역시','남원':'시','하동':'군','진주':'시','사천':'시','산청':'군','남해':'군','임실':'군','순창':'군'}; name=r+suffix.get(r,'시' if i<5 else '군'); province={'광주':'KR-29','남원':'KR-45','임실':'KR-45','순창':'KR-45','하동':'KR-48','진주':'KR-48','사천':'KR-48','산청':'KR-48','남해':'KR-48'}.get(r,'KR-46'); area=f'area["ISO3166-2"="{province}"]->.a;' if r=='광주' else f'area["ISO3166-2"="{province}"]->.province;rel(area.province)["boundary"="administrative"]["name"="{name}"];map_to_area->.a;'; q=f'[out:json][timeout:90];{area}(nwr(area.a)["amenity"~"^(cafe|library|restaurant|theatre|arts_centre)$"]["name"];nwr(area.a)["tourism"~"^(museum|gallery)$"]["name"];);out center;' 
 try:
  req=urllib.request.Request('https://overpass-api.de/api/interpreter',data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'JeonnamDatePersonal/1.0'})
  with urllib.request.urlopen(req,timeout=120) as f: j=json.load(f)
  if j.get('remark'): raise ValueError(j['remark'])
  rows={}
  for e in j['elements']:
   t=e['tags']; c=e.get('center',e); id=e['type']+'/'+str(e['id'])
   if 'lat' not in c: continue
   rows[id]=dict(id=id,region=r,name=t.get('name:ko',t['name']),kind=t.get('tourism') if t.get('tourism') in ('museum','gallery') else t.get('amenity'),lat=c['lat'],lon=c['lon'],fee=t.get('fee',''),cuisine=t.get('cuisine',''),open=t.get('opening_hours',''),wifi=t.get('internet_access',''),power=t.get('power_supply',''),first_seen=data.get(id,{}).get('first_seen',now))
  if not rows: raise ValueError('empty response')
  data={k:v for k,v in data.items() if v['region']!=r}; data.update(rows); done.add(r); success+=1; print(r,len(rows),flush=True)
 except Exception as e: print(r,e,flush=True)
 time.sleep(12)
if not success: raise SystemExit('No successful regions; keeping previous database')
P.write_text(json.dumps(dict(updated=now,regions=sorted(done),places=sorted(data.values(),key=lambda x:x['id'])),ensure_ascii=False),encoding='utf-8')
