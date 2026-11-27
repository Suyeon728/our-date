import os,json,datetime,urllib.request,urllib.parse,pathlib,re
p=pathlib.Path('events.json'); old=json.loads(p.read_text()) if p.exists() else {'events':[]}; key=os.getenv('DATA_GO_KR_KEY','').strip(); today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
if not key: raise SystemExit('DATA_GO_KR_KEY missing')
provinces={'서울':'서울','부산':'부산','대구':'대구','인천':'인천','광주':'광주','대전':'대전','울산':'울산','세종':'세종','경기':'경기','강원':'강원','충북':'충북','충청북':'충북','충남':'충남','충청남':'충남','전북':'전북','전라북':'전북','전남':'전남','전라남':'전남','경북':'경북','경상북':'경북','경남':'경남','경상남':'경남','제주':'제주'}
def location(addr):
 first=addr.strip().split()[0] if addr.strip() else ''
 province=next((v for k,v in provinces.items() if first.startswith(k)), '지역 미확인')
 parts=addr.strip().split(); city=parts[1] if len(parts)>1 and re.search(r'(시|군|구)$',parts[1]) else ''
 return province, ' '.join(filter(None,[province,city]))
result=[]; statuses={}
for source,endpoint in [('행사','tn_pubr_public_pblprfr_event_info_api'),('축제','tn_pubr_public_cltur_fstvl_api')]:
 try:
  rows=[]
  for page in range(1,101):
   url='https://api.data.go.kr/openapi/'+endpoint+'?'+urllib.parse.urlencode(dict(serviceKey=urllib.parse.unquote(key),type='json',pageNo=page,numOfRows=1000))
   with urllib.request.urlopen(url,timeout=45) as f: j=json.load(f)
   response=j['response']; header=response.get('header',{}); assert str(header.get('resultCode','')) in ('00','0','0000'), 'API response error' 
   body=response['body']; items=body.get('items') or []; items=items.get('item',[]) if isinstance(items,dict) else items; items=[items] if isinstance(items,dict) else items
   rows.extend(items)
   if len(rows)>=int(body['totalCount']): break
   if not items: raise ValueError('incomplete response')
  else: raise ValueError('page limit')
  for x in rows:
   name=x.get('eventNm') or x.get('fstvlNm'); addr=x.get('rdnmadr') or x.get('lnmadr') or ''; venue=x.get('opar') or ''; start=x.get('eventStartDate') or x.get('fstvlStartDate'); end=x.get('eventEndDate') or x.get('fstvlEndDate') or start
   if not name or not start or not end or end<today: continue
   province,region=location(addr)
   try: lat,lon=float(x.get('latitude')),float(x.get('longitude')); assert 33<lat<39 and 124<lon<132
   except: lat=lon=None
   desc=x.get('eventCo') or x.get('fstvlCo') or ''; price=str(next((x[k] for k in ('chrgeInfo','admfee') if k in x and x[k] not in (None,'')), '')).strip(); cat='축제' if source=='축제' else next((c for c,pat in [('전시','전시|미술|갤러리'),('체험','체험|공예|만들기|강좌'),('공연','공연|콘서트|음악회|연극|뮤지컬|연주|무용')] if re.search(pat,name)), '기타 행사')
   result.append(dict(source=source,name=name,province=province,region=region,address=addr,venue=venue,start=start,end=end,lat=lat,lon=lon,category=cat,price=price,free=price in ('무료','0','0원','무료입장','무료 관람','무료관람'),time=x.get('eventStartTime') or '',url=x.get('homepageUrl') or '',phone=x.get('phoneNumber') or '',description=desc))
  statuses[source]='성공'; print(source,len(rows),'raw records;',sum(x['source']==source for x in result),'current/future records',flush=True)
 except Exception as e:
  statuses[source]='실패: 기존 자료 유지'; print(source,type(e).__name__,getattr(e,'code',''),flush=True); result.extend(x for x in old['events'] if x.get('source')==source)
p.write_text(json.dumps(dict(updated=today,status=statuses,events=list({(x['name'],x['start'],x['region'],x['venue']):x for x in result}.values())),ensure_ascii=False),encoding='utf-8')

if not all(v=='성공' for v in statuses.values()): raise SystemExit('One or more event sources failed; previous records preserved')
