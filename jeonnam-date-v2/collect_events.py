import time,socket,urllib.error,os,json,datetime,urllib.request,urllib.parse,pathlib,re,xml.etree.ElementTree as ET
p=pathlib.Path('events.json'); old=json.loads(p.read_text()) if p.exists() else {'events':[]}; key=os.getenv('DATA_GO_KR_KEY','').strip(); today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
if not key: raise SystemExit('DATA_GO_KR_KEY missing')
provinces={'서울':'서울','부산':'부산','대구':'대구','인천':'인천','광주':'광주','대전':'대전','울산':'울산','세종':'세종','경기':'경기','강원':'강원','충북':'충북','충청북':'충북','충남':'충남','충청남':'충남','전북':'전북','전라북':'전북','전남':'전남','전라남':'전남','경북':'경북','경상북':'경북','경남':'경남','경상남':'경남','제주':'제주'}
def location(addr):
 first=addr.strip().split()[0] if addr.strip() else ''
 province=next((v for k,v in provinces.items() if first.startswith(k)), '지역 미확인')
 parts=addr.strip().split(); city=parts[1] if len(parts)>1 and re.search(r'(시|군|구)$',parts[1]) else ''
 return province, ' '.join(filter(None,[province,city]))
def fetch_page(url):
 for attempt in range(4):
  try:
   with urllib.request.urlopen(url,timeout=45) as f: return f.read()
  except (urllib.error.URLError,TimeoutError,ConnectionError) as e:
   code=getattr(e,'code',None)
   if code is not None and code not in (408,429,500,502,503,504): raise
   print('Network retry',attempt+1,'/4', 'HTTP '+str(code) if code else type(getattr(e,'reason',e)).__name__,flush=True)
   if attempt==3: raise
   time.sleep(2**(attempt+1))
def unpack(raw):
 # Support both gateway response formats and report errors without printing secrets.
 try: j=json.loads(raw)
 except (ValueError, UnicodeError):
  try:
   root=ET.fromstring(raw)
  except ET.ParseError: raise ValueError('Response is neither JSON nor XML') from None
  def convert(el):
   if not len(el): return el.text or ''
   out={}
   for ch in el:
    k=ch.tag.split('}')[-1]; v=convert(ch)
    if k in out: out[k]=out[k]+[v] if isinstance(out[k],list) else [out[k],v]
    else: out[k]=v
   return out
  j={root.tag.split('}')[-1]:convert(root)}
 if not isinstance(j,dict): raise ValueError('Unexpected response type')
 r=j.get('response',j.get('dataGrid',j))
 if not isinstance(r,dict): raise ValueError('Unexpected response wrapper')
 h=r.get('header',{}) or {}; h=h if isinstance(h,dict) else {}
 err=j.get('OpenAPI_ServiceResponse',{}) or {}; err=err.get('cmmMsgHeader',{}) if isinstance(err,dict) else {}
 code=h.get('resultCode',r.get('resultCode',err.get('returnReasonCode')))
 if code is not None and str(code) not in ('00','0','0000','200'):
  raise ValueError('API result code '+re.sub(r'[^0-9A-Za-z_-]','',str(code))[:24])
 b=r.get('body',r)
 if not isinstance(b,dict): raise ValueError('Missing response body')
 items=b.get('items',b.get('records',b.get('data')))
 if items is None and not any(k in b for k in ('items','records','data')):
  raise ValueError('Missing records; root fields: '+','.join(str(k)[:40] for k in j.keys())[:200])
 if isinstance(items,dict): items=items.get('item',items.get('record',items))
 if isinstance(items,dict): items=[items]
 if items in (None,''): items=[]
 if not isinstance(items,list) or any(not isinstance(x,dict) for x in items): raise ValueError('Invalid records')
 total=b.get('totalCount',b.get('total',r.get('totalCount')))
 if total is None: raise ValueError('Missing totalCount; body fields: '+','.join(str(k)[:40] for k in b.keys())[:200])
 return items,int(total)

excluded=re.compile(r'산업안전|안전보건|법정의무|직무교육|직원교육|근로자.{0,12}교육|정기교육|보수교육|교직원.{0,8}연수|사내교육|워크숍|워크샵|세미나|정기총회|이사회|간담회|회의|채용|시험|입학식|졸업식|수료식|기념식|시상식|설명회|보고회|발대식|위촉식|교육청.{0,8}연수')
def eligible(e):
 return e.get('category') in ('전시','공연','체험','축제') and not excluded.search(e.get('name') or '')
result=[]; statuses={}
for source,endpoint in [('행사','tn_pubr_public_pblprfr_event_info_api'),('축제','tn_pubr_public_cltur_fstvl_api')]:
 try:
  rows=[]
  for page in range(1,101):
   url='https://api.data.go.kr/openapi/'+endpoint+'?'+urllib.parse.urlencode(dict(serviceKey=urllib.parse.unquote(key),type='json',pageNo=page,numOfRows=1000))
   raw=fetch_page(url)
   items,total=unpack(raw)
   rows.extend(items)
   if len(rows)>=total: break
   if not items: raise ValueError('incomplete response')
  else: raise ValueError('page limit')
  for x in rows:
   aliases={'행사명':'eventNm','축제명':'fstvlNm','장소':'opar','개최장소':'opar','행사시작일자':'eventStartDate','행사종료일자':'eventEndDate','축제시작일자':'fstvlStartDate','축제종료일자':'fstvlEndDate','소재지도로명주소':'rdnmadr','소재지지번주소':'lnmadr','위도':'latitude','경도':'longitude','행사내용':'eventCo','축제내용':'fstvlCo','홈페이지주소':'homepageUrl','전화번호':'phoneNumber','행사시작시각':'eventStartTime'}; x={aliases.get(k,k):v for k,v in x.items()}; name=x.get('eventNm') or x.get('fstvlNm'); addr=x.get('rdnmadr') or x.get('lnmadr') or ''; venue=x.get('opar') or ''; start=x.get('eventStartDate') or x.get('fstvlStartDate'); end=x.get('eventEndDate') or x.get('fstvlEndDate') or start
   if not name or not start or not end or end<today: continue
   province,region=location(addr)
   try: lat,lon=float(x.get('latitude')),float(x.get('longitude')); assert 33<lat<39 and 124<lon<132
   except: lat=lon=None
   desc=x.get('eventCo') or x.get('fstvlCo') or ''; price=str(next((x[k] for k in ('chrgeInfo','admfee','관람요금','요금정보') if k in x and x[k] not in (None,'')), '')).strip(); cat='축제' if source=='축제' else next((c for c,pat in [('전시','전시|미술|갤러리|개인전|기획전|특별전|상설전|사진전|회화전|초대전'),('체험','체험|공예|만들기|원데이|클래스'),('공연','공연|콘서트|음악회|연극|뮤지컬|연주|무용|오페라|발레|버스킹|리사이틀|합창|국악|독주|교향악|재즈|마술')] if re.search(pat,name)), '기타 행사')
   if not eligible(dict(category=cat,name=name)): continue
   result.append(dict(source=source,name=name,province=province,region=region,address=addr,venue=venue,start=start,end=end,lat=lat,lon=lon,category=cat,price=price,free=price in ('무료','0','0원','무료입장','무료 관람','무료관람'),time=x.get('eventStartTime') or '',url=x.get('homepageUrl') or '',phone=x.get('phoneNumber') or '',description=desc))
  statuses[source]='성공'; print(source,len(rows),'raw records;',sum(x['source']==source for x in result),'current/future records',flush=True)
 except Exception as e:
  statuses[source]='실패: 기존 자료 유지'; print(source,type(e).__name__,str(e)[:250] if isinstance(e,ValueError) and not isinstance(e,UnicodeError) else (getattr(e,'code',None) or type(getattr(e,'reason',e)).__name__),flush=True); result.extend(x for x in old['events'] if x.get('source')==source)
p.write_text(json.dumps(dict(updated=today,status=statuses,events=list({(x['name'],x['start'],x['region'],x['venue']):x for x in result if eligible(x)}.values())),ensure_ascii=False),encoding='utf-8')

if not all(v=='성공' for v in statuses.values()): raise SystemExit('One or more event sources failed; previous records preserved')
