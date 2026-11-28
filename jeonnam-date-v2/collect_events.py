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
   desc=x.get('eventCo') or x.get('fstvlCo') or ''; price=str(next((x[k] for k in ('chrgeInfo','admfee','관람요금','요금정보') if k in x and x[k] not in (None,'')), '')).strip(); cat='축제' if source=='축제' else next((c for c,pat in [('전시','전시|서울라이트|미디어파사드|미술|갤러리|개인전|기획전|특별전|상설전|사진전|회화전|초대전'),('체험','체험|공예|만들기|원데이|클래스|스케이트장'),('축제','축제|페스티벌|마켓|플리마켓|팝업|빛축제|타종|빛초롱|윈터페스타|윈터페스티벌'),('공연','공연|콘서트|음악회|연극|뮤지컬|연주|무용|오페라|발레|버스킹|리사이틀|합창|국악|독주|교향악|재즈|마술')] if re.search(pat,name)), '기타 행사')
   if not eligible(dict(category=cat,name=name)): continue
   result.append(dict(source=source,name=name,province=province,region=region,address=addr,venue=venue,start=start,end=end,lat=lat,lon=lon,category=cat,price=price,free=price in ('무료','0','0원','무료입장','무료 관람','무료관람'),time=x.get('eventStartTime') or '',url=x.get('homepageUrl') or '',phone=x.get('phoneNumber') or '',description=desc))
  statuses[source]='성공'; print(source,len(rows),'raw records;',sum(x['source']==source for x in result),'current/future records',flush=True)
 except Exception as e:
  statuses[source]='실패: 기존 자료 유지'; print(source,type(e).__name__,str(e)[:250] if isinstance(e,ValueError) and not isinstance(e,UnicodeError) else (getattr(e,'code',None) or type(getattr(e,'reason',e)).__name__),flush=True); result.extend(x for x in old['events'] if x.get('source')==source)
# Korea Tourism Organization: nationwide event feed, using existing secret.
source='관광공사'
def tour_date(value):
 v=str(value or '').strip()
 try: return datetime.datetime.strptime(v,'%Y%m%d').date().isoformat()
 except ValueError:
  try: return datetime.date.fromisoformat(v).isoformat()
  except ValueError: return ''
try:
 rows=[]
 since=(datetime.date.fromisoformat(today)-datetime.timedelta(days=366)).strftime('%Y%m%d')
 for page in range(1,101):
  params=dict(serviceKey=urllib.parse.unquote(key),MobileOS='ETC',MobileApp='OurDate',_type='json',eventStartDate=since,pageNo=page,numOfRows=100)
  items,total=unpack(fetch_page('https://apis.data.go.kr/B551011/KorService2/searchFestival2?'+urllib.parse.urlencode(params)))
  rows.extend(items)
  if len(rows)>=total: break
  if not items: raise ValueError('Incomplete TourAPI response')
 else: raise ValueError('TourAPI page limit')
 for x in rows:
  name=str(x.get('title') or '').strip(); start=tour_date(x.get('eventstartdate')); end=tour_date(x.get('eventenddate')) or start
  if not name or not start or not end or end<today or excluded.search(name): continue
  addr=str(x.get('addr1') or '').strip(); province,region=location(addr)
  try:
   lat,lon=float(x.get('mapy')),float(x.get('mapx'))
   if not (33<=lat<39 and 124<lon<132): raise ValueError()
  except (ValueError,TypeError): lat=lon=None
  cat=next((c for c,pat in [('전시','전시|미술|사진전|미디어아트'),('체험','체험|공예|원데이|클래스'),('공연','공연|콘서트|음악회|연극|뮤지컬|버스킹|연주')] if re.search(pat,name)), '축제')
  cid=str(x.get('contentid') or '')
  result.append(dict(source=source,name=name,province=province,region=region,address=addr,venue=str(x.get('addr2') or ''),start=start,end=end,lat=lat,lon=lon,category=cat,price='',free=False,time='',url='https://korean.visitkorea.or.kr/search/search_list.do?keyword='+urllib.parse.quote(name),phone=str(x.get('tel') or ''),description='한국관광공사 관광행사 정보 · 요금 확인 필요',contentid=cid))
 statuses[source]='성공'; print(source,len(rows),'raw records;',sum(x['source']==source for x in result),'current/future records',flush=True)
except Exception as e:
 statuses[source]='실패: 기존 자료 유지'; print(source,type(e).__name__,str(e)[:200] if isinstance(e,ValueError) else (getattr(e,'code',None) or type(getattr(e,'reason',e)).__name__),flush=True)
 result.extend(x for x in old['events'] if x.get('source')==source)
# Officially verified seasonal event supplement; expires automatically.
if today <= '2026-12-25':
 name='크리스마스 빌리지 부산 2026'
 dates=[]
 for n in range(30):
  d=datetime.date(2026,11,26)+datetime.timedelta(days=n)
  if d.weekday()>=3 or d>=datetime.date(2026,12,21): dates.append(d.isoformat())
 result=[x for x in result if not ('크리스마스' in x['name'] and '빌리지' in x['name'] and ('부산' in x['name'] or x.get('province')=='부산'))]
 result.append(dict(source='공식 일정 보완',name=name,province='부산',region='부산 해운대구',address='부산 해운대구 수영강변대로 120',venue='영화의전당 야외광장',start='2026-11-26',end='2026-12-25',dates=dates,lat=None,lon=None,category='축제',price='유료 (예매처 확인)',free=False,time='',url='https://m.ticket.yes24.com/Notice/Detail.aspx?bid=18725',phone='',description='크리스마스 마켓 · 공식 예매 공지 기준 운영일만 표시'))
# Seasonal supplement: user-provided schedule, cross-check official Seoul notice before visiting.
seoul_url='https://tv.seoul.go.kr/v/38e3d3d0d17e4151a1bfadaf19fa271c'
seasonal=[
 ('서울빛초롱축제','2026-12-11','2027-01-31','중구','청계광장~삼일교','축제','18:00~23:00','청계광장'),
 ('청계천의 빛','2026-12-11','2026-12-31','중구','청계광장 일대','전시','18:00~22:00','청계광장'),
 ('광화문 마켓','2026-12-11','2027-01-10','종로구','광화문광장·세종로공원','축제','17:30~23:00','광화문광장'),
 ('서울라이트 광화문','2026-12-11','2027-01-10','종로구','광화문 및 광화문광장 북측','전시','공식 안내 확인','광화문광장'),
 ('서울광장 스케이트장','2026-12-18','2027-02-09','중구','서울광장','체험','공식 안내 확인','서울광장'),
 ('제야의 종 타종행사','2026-12-31','2027-01-01','종로구','보신각 일대','축제','공식 안내 확인','보신각')]
for name,start,end,district,venue,cat,hours,place in seasonal:
 if end<today: continue
 norm=lambda s: re.sub(r'[^가-힣A-Za-z]','',s).lower()
 result=[x for x in result if not (x.get('province')=='서울' and norm(name)==norm(x.get('name','')) and x.get('start','')<=end and x.get('end','')>=start)]
 result.append(dict(source='시즌 일정 보완',name=name,province='서울',region='서울 '+district,address='서울 '+district+' '+place,venue=venue,start=start,end=end,lat=None,lon=None,category=cat,price='',free=False,time=hours,url=seoul_url,phone='',description='제공된 시즌 일정 기준 · 세부 운영 및 요금은 공식 안내 확인'))

# Regional feeds: official open data, no HTML scraping or invented schedules.
def dated(value):
 m=re.match(r'^(\d{4})[-./]?(\d{2})[-./]?(\d{2})',str(value or '').strip())
 if not m:return ''
 try:return datetime.date(*map(int,m.groups())).isoformat()
 except ValueError:return ''
def coords(a,b):
 try:
  a,b=float(a),float(b)
  if 33<=a<39 and 124<b<132:return a,b
 except (TypeError,ValueError):pass
 return None,None
def region_category(name,code=''):
 if excluded.search(name):return ''
 for cat,pattern in [('전시','전시|미술|사진전|미디어아트|서울라이트'),('체험','체험|공예|원데이|스케이트|클래스'),('축제','축제|마켓|페스티벌|팝업|크리스마스|빛초롱'),('공연','공연|콘서트|음악|연극|뮤지컬|국악|무용|발레|오페라|연주|버스킹|클래식|독주|합창')]:
  if re.search(pattern,name+' '+code):return cat
 return ''
def regional_record(source,name,province,district,venue,start,end,lat,lon,cat,price,free,url,phone='',hours='',address=''):
 return dict(source=source,name=name,province=province,region=' '.join(filter(None,[province,district])),address=address or ' '.join(filter(None,[province,district,venue])),venue=venue,start=start,end=end,lat=lat,lon=lon,category=cat,price=price,free=free,time=hours,url=url,phone=phone,description=source+' 제공 · 세부 운영일 확인 필요')
def seoul_records():
 sk=os.getenv('SEOUL_API_KEY','').strip()
 if not sk:raise RuntimeError('SEOUL_API_KEY missing')
 rows=[]
 for i in range(1,100001,1000):
  # Official Seoul Open Data API uses a separate key.
  u='http://openapi.seoul.go.kr:8088/'+urllib.parse.quote(sk,safe='')+'/json/culturalEventInfo/'+str(i)+'/'+str(i+999)
  j=json.loads(fetch_page(u)); b=j.get('culturalEventInfo',{}); h=b.get('RESULT',j.get('RESULT',{})); code=h.get('CODE','')
  if code!='INFO-000':raise ValueError('Seoul API code '+re.sub(r'[^A-Za-z0-9_-]','',str(code))[:30])
  batch=b.get('row',[]); rows.extend(batch)
  if len(rows)>=int(b['list_total_count']):break
  if not batch:raise ValueError('Incomplete Seoul feed')
 else:raise ValueError('Seoul page limit')
 out=[]
 for x in rows:
  name=str(x.get('TITLE') or '').strip(); start=dated(x.get('STRTDATE')); end=dated(x.get('END_DATE')) or start; cat=region_category(name,str(x.get('CODENAME') or ''))
  if not name or not cat or not start or end<today or end<start:continue
  a,b=coords(x.get('LAT'),x.get('LOT')); venue=str(x.get('PLACE') or ''); district=str(x.get('GUNAME') or ''); price=str(x.get('USE_FEE') or ''); free=str(x.get('IS_FREE') or '').strip()=='무료' or price.strip() in ('무료','0원','0')
  out.append(regional_record('서울문화포털',name,'서울',district,venue,start,end,a,b,cat,price,free,str(x.get('HMPG_ADDR') or x.get('ORG_LINK') or 'https://culture.seoul.go.kr/'),str(x.get('INQUIRY') or ''),str(x.get('TIME') or '')))
 return out

def busan_records():
 rows=[]
 for page in range(1,101):
  u='https://apis.data.go.kr/6260000/FestivalService/getFestivalKr?'+urllib.parse.urlencode(dict(ServiceKey=urllib.parse.unquote(key),pageNo=page,numOfRows=100,resultType='json'))
  j=json.loads(fetch_page(u)); b=j.get('getFestivalKr')
  if isinstance(b,dict):
   h=b.get('header',{}); code=str(h.get('code',h.get('resultCode','00')))
   if code not in ('00','0','0000'):raise ValueError('Busan API code '+re.sub(r'[^A-Za-z0-9_-]','',code)[:30])
   batch=b.get('item',[]); total=b.get('totalCount')
   if isinstance(batch,dict):batch=[batch]
   if not isinstance(batch,list) or total is None:raise ValueError('Unknown Busan response')
   total=int(total)
  else:batch,total=unpack(json.dumps(j).encode())
  rows.extend(batch)
  if len(rows)>=total:break
  if not batch:raise ValueError('Incomplete Busan feed')
 else:raise ValueError('Busan page limit')
 out=[]; undated=0
 for x in rows:
  name=str(x.get('MAIN_TITLE') or '').strip(); period=str(x.get('USAGE_DAY') or '')
  # Never infer the year of recurring festivals. Require explicit full dates.
  # Normalize single-digit components separately.
  ds=[]
  for y,m,d in re.findall(r'(20\d{2})\s*(?:년|[.\-/])\s*(\d{1,2})\s*(?:월|[.\-/])\s*(\d{1,2})',period):
   try:ds.append(datetime.date(int(y),int(m),int(d)).isoformat())
   except ValueError:pass
  if len(ds)!=2:undated+=1;continue
  start,end=ds
  if not name or end<today or end<start or excluded.search(name):continue
  a,b=coords(x.get('LAT'),x.get('LNG')); price=str(x.get('USAGE_AMOUNT') or '')
  out.append(regional_record('부산축제정보',name,'부산',str(x.get('GUGUN_NM') or ''),str(x.get('MAIN_PLACE') or x.get('PLACE') or ''),start,end,a,b,'축제',price,price.strip() in ('무료','0원','0'),str(x.get('HOMEPAGE_URL') or 'https://www.visitbusan.net/'),str(x.get('CNTCT_TEL') or ''),str(x.get('USAGE_DAY_WEEK_AND_TIME') or ''),'부산 '+str(x.get('ADDR1') or '')))
 print('부산축제정보: 날짜 불명확 제외',undated,flush=True)
 return out
for src,fn in [('서울문화포털',seoul_records),('부산축제정보',busan_records)]:
 if src=='서울문화포털' and not os.getenv('SEOUL_API_KEY','').strip() or src=='부산축제정보' and os.getenv('BUSAN_ENABLED','').lower()!='true':
  statuses[src]='미연결';result.extend(x for x in old['events'] if x.get('source')==src);continue
 try:
  fresh=fn(); result.extend(fresh);statuses[src]='성공';print(src,len(fresh),'current/future records',flush=True)
 except Exception as e:
  statuses[src]='실패: 기존 자료 유지';print(src,type(e).__name__,getattr(e,'code',None) or (str(e)[:120] if isinstance(e,ValueError) else ''),flush=True);result.extend(x for x in old['events'] if x.get('source')==src)

# Preserve only unexpired records, including fallback records.
result=[x for x in result if x.get("end", "")>=today]
p.write_text(json.dumps(dict(updated=today,status=statuses,events=list({(x['name'],x['start'],x['region'],x['venue']):x for x in result if eligible(x)}.values())),ensure_ascii=False),encoding='utf-8')

if any(v.startswith('실패') for v in statuses.values()): raise SystemExit('One or more event sources failed; previous records preserved')
