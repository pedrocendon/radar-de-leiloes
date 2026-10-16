"""Public-source collectors. No login, bids, CAPTCHA solving or private APIs."""
import re, json, time, hashlib, unicodedata, urllib.request, urllib.error, urllib.parse, urllib.robotparser
from html.parser import HTMLParser
from datetime import datetime, timezone, timedelta

AGENT = 'LeiloesMonitor/0.1 (personal research; low frequency)'
TZ = timezone(timedelta(hours=-3))
def now(): return datetime.now(TZ).isoformat(timespec='seconds')
def norm(s): return ''.join(c for c in unicodedata.normalize('NFD',str(s or '').lower()) if unicodedata.category(c)!='Mn')
def canonical(url):
    p=urllib.parse.urlsplit(url.strip())
    if p.scheme not in ('http','https') or not p.hostname or p.username: raise ValueError('Use um link público http/https.')
    q=urllib.parse.urlencode([(k,v) for k,v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith('utm_') and k not in ('fbclid','gclid')])
    return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip('/') or '/',q,''))
def money(s):
    if s is None:return None
    if isinstance(s,(int,float)):return float(s)
    s=re.sub(r'[^\d,.-]','',s)
    if ',' in s:s=s.replace('.','').replace(',','.')
    try:return float(s)
    except ValueError:return None
def match(pattern,text,group=1):
    m=re.search(pattern,text,re.I|re.S)
    return m[group].strip() if m else None
def brdate(s):
    if not s:return None
    m=re.search(r'(\d{2}/\d{2}/\d{4})(?:[^\d]{1,30}(\d{2}:\d{2}))?',s)
    if not m:return None
    try:return datetime.strptime(m[1],'%d/%m/%Y').date().isoformat()+('T'+m[2]+':00-03:00' if m[2] else '')
    except ValueError:return None

class Node:
    def __init__(self,tag='',attrs=None):self.tag=tag;self.attrs=dict(attrs or []);self.children=[]
    def text(self):return re.sub(r'\s+',' ',' '.join(c if isinstance(c,str) else c.text() for c in self.children if isinstance(c,str) or c.tag not in ('script','style','noscript'))).strip()
    def all(self,tag=None,cls=None,id=None):
        out=[]
        if (not tag or self.tag==tag) and (not cls or cls in self.attrs.get('class','').split()) and (not id or self.attrs.get('id')==id):out.append(self)
        for c in self.children:
            if isinstance(c,Node):out.extend(c.all(tag,cls,id))
        return out
    def first(self,**kw):
        a=self.all(**kw);return a[0] if a else Node()
class DOM(HTMLParser):
    VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self,html):
        super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root];self.feed(html)
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs);self.stack[-1].children.append(n)
        if tag not in self.VOID:self.stack.append(n)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];break
    def handle_data(self,data):self.stack[-1].children.append(data)

class CollectError(Exception):
    def __init__(self,status,detail):super().__init__(detail);self.status=status
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
class Client:
    def __init__(self):self.robots={};self.last={};self.blocked={};self.wildcards={};self.opener=urllib.request.build_opener(NoRedirect)
    def raw(self,url):
        host=urllib.parse.urlsplit(url).netloc
        if host in self.blocked:raise CollectError('bloqueado',self.blocked[host])
        delay=2-(time.monotonic()-self.last.get(host,0))
        if delay>0:time.sleep(delay)
        self.last[host]=time.monotonic()
        try:
            req=urllib.request.Request(url,headers={'User-Agent':AGENT,'Accept':'text/html,application/json,text/plain'})
            with self.opener.open(req,timeout=25) as r:
                body=r.read(6000001)
                if len(body)>6000000:raise CollectError('limite_tamanho','Resposta maior que 6 MB.')
                return body.decode(r.headers.get_content_charset() or 'utf-8',errors='replace')
        except urllib.error.HTTPError as e:
            if e.code in (301,302,303,307,308):
                location=urllib.parse.urljoin(url,e.headers.get('Location',''))
                raise CollectError('redirecionado','Destino: '+location)
            if e.code in (401,403,429):self.blocked[host]='HTTP '+str(e.code)+'; demais consultas ao domínio suspensas nesta rodada.'
            raise CollectError('bloqueado' if e.code in (401,403,429) else 'http_'+str(e.code),'HTTP '+str(e.code))
        except (urllib.error.URLError,TimeoutError,OSError) as e:raise CollectError('falha_rede',str(e))
    def get(self,url):
        url=canonical(url);p=urllib.parse.urlsplit(url);root=p.scheme+'://'+p.netloc
        if root not in self.robots:
            try:
                txt=self.raw(root+'/robots.txt')
                if '<html' in txt.lower():raise CollectError('politica_indisponivel','robots.txt devolveu uma página HTML; usar consulta assistida.')
                rp=urllib.robotparser.RobotFileParser();rp.parse(txt.splitlines());self.robots[root]=rp
                self.wildcards[root]=[re.escape(x.rstrip('$')).replace(r'\*','.*')+('$' if x.endswith('$') else '') for x in re.findall(r'^Disallow:\s*(/[^\s#]*\*[^\s#]*)',txt,re.I|re.M)]
            except CollectError as e:
                if e.status=='http_404':self.robots[root]=None
                else:raise
        rp=self.robots[root]
        if rp and not rp.can_fetch(AGENT,url):raise CollectError('robots_restrito','Caminho não permitido pelo robots.txt.')
        if any(re.match(pattern,p.path+('?' +p.query if p.query else '')) for pattern in self.wildcards.get(root,[])):raise CollectError('robots_restrito','Regra com curinga no robots.txt.')
        txt=self.raw(url)
        if re.search(r'<title>\s*(Just a moment|Access denied|Attention Required)',txt,re.I):raise CollectError('bloqueado','Página de desafio; coleta interrompida.')
        return txt

def basics(d,description):
    d['description']=description
    t=d.get('title','')
    d['type']=next((kind for pattern,kind in [(r'\b(apartamento|apto|duplex|triplex)\b','apartamento'),(r'\bcasa\b','casa'),(r'\b(terreno|lote)\b','terreno'),(r'\b(rural|fazenda|sitio)\b','rural')] if re.search(pattern,norm(t))),None)
    d['subtype']=next((x for x in ['duplex','triplex','cobertura'] if x in norm(t)),None)
    d['areas']=[]
    for m in re.finditer(r'área\s+(privativa|útil|total|aproximada)(?:\s+de)?\s*([\d.,]+)\s*(?:m[²2]|metros quadrados)',description,re.I):
        d['areas'].append({'kind':norm(m[1]),'m2':money(m[2]),'origin':'fonte','context':description[max(0,m.start()-80):m.end()+20]})
    if not d['areas']:
        m=re.search(r'([\d.,]+)\s*m[²2]',t)
        if m:d['areas']=[{'kind':'total' if 'área total' in t else 'não especificada','m2':money(m[1]),'origin':'fonte: título'}]
    # Only explicit occupancy statements, never references to potential occupation.
    d['occupancy']=None
    for pattern,value in [(r'\bdesocupado\b','desocupado'),(r'\bimóvel\s+(?:encontra-se\s+)?ocupado\b|(?:^|[.!]\s*)Ocupado\b','ocupado')]:
        if re.search(pattern,description,re.I):d['occupancy']=value
    d['registry']=match(r'MATR[IÍ]CULA\s*(?:N[º°o.]*)?\s*([\d.]+)\s+DO\s+([^:]+?)(?:\s*-\s*IM[ÓO]VEL|\s+atualizada|:)',description)
    d['registry_office']=match(r'MATR[IÍ]CULA\s*(?:N[º°o.]*)?\s*[\d.]+\s+DO\s+([^:]+?)(?:\s*-\s*IM[ÓO]VEL|\s+atualizada|:)',description)
    d.setdefault('warnings',[])
    d['asset_scope']='direitos sobre o imóvel' if re.search(r'direitos sobre o im[oó]vel',description,re.I) else 'não especificado'
    d['registry_numbers']=list(dict.fromkeys(re.findall(r'MATR[IÍ]CULA\s*(?:N[º°o.]*)?\s*(\d[\d.]*)',description,re.I)))
    if len(d['registry_numbers'])>1:d['warnings'].append('Lote reúne mais de uma matrícula; áreas podem pertencer a apartamento e garagens. Mantidos os trechos de origem.')
    d['provenance']={k:'fonte' for k in d if k not in ('warnings','provenance')}
    return d
def documents(root,url):
    found=[]
    for a in root.all(tag='a'):
        href=a.attrs.get('href','').strip()
        if href and ('edital' in norm(a.text()) or 'edital' in norm(href)):
            u=urllib.parse.urljoin(url,href)
            if urllib.parse.urlsplit(u).scheme in ('http','https'):found.append(u)
    return list(dict.fromkeys(found))
def mega(html,url):
    root=DOM(html).root
    title=root.first(tag='h1').text()
    if not title:raise CollectError('estrutura_alterada','Título de imóvel não encontrado.')
    def val(cls):return root.first(cls=cls).first(cls='value').text()
    main=root.first(cls='main-info').text()
    description=root.first(id='tab-description').text()
    if not description:raise CollectError('estrutura_alterada','Descrição do lote ausente.')
    parts=title.split(' - ')
    d={'title':title,'url':url,'external_id':match(r'([jx]\d+)$',url),'auction_external_id':match(r'Leilão\s+(ML\d+)',root.text()),'address':val('locality') or None,'city':parts[-2] if len(parts)>=3 else None,'uf':parts[-1] if re.fullmatch('[A-Z]{2}',parts[-1]) else None,'auctioneer':val('author') or None,'valuation':money(match(r'Valor de Avaliação\s*R\$\s*([\d.,]+)',main)),'initial_bid':money(match(r'Valor inicial\s*R\$\s*([\d.,]+)',root.text())),'status':None,'notice_links':documents(root,url),'stages':[]}
    # Date and price stay linked to the same numbered stage, including third rounds.
    contract=root.first(id='tab-contract').text()
    for n in range(1,5):
        m=re.search(str(n)+r'[ºªo]\s*Leilão(?:,)?\s+(?:que\s+)?terá início(.*?)(?=(?:[1-4][ºªo]\s*Leilão(?:,)?\s+(?:que\s+)?terá início)|DO CONDUTOR|DO LEILOEIRO|DO VALOR|DOS LANCES|$)',contract,re.I)
        if not m:continue
        part=m[1][:1300]
        start=brdate(match(r'(\d{2}/\d{2}/\d{4}.*?\d{2}:\d{2})',part))
        endmatch=match(r'encerrar[áa](?:\s+no)?(?:\s+dia)?\s+(\d{2}/\d{2}/\d{4}[^;]{0,60}?\d{2}:\d{2})',part)
        if not endmatch:endmatch=match(r'encerrar[áa](?:\s+no)?(?:\s+dia)?\s+(\d{2}/\d{2}/\d{4})',part)
        pct=match(r'mínimo\s+(\d+(?:,\d+)?)\s*%',part)
        bid=None;origin='ausente'
        if d['valuation'] and re.search(r'lances iguais ou superiores ao valor da avaliação',part,re.I):bid=d['valuation'];origin='calculado: 100% da avaliação, conforme regra da fonte'
        elif d['valuation'] and pct:bid=round(d['valuation']*money(pct)/100,2);origin='calculado: '+pct+'% da avaliação, conforme regra da fonte'
        d['stages'].append({'number':n,'starts_at':start,'date':brdate(endmatch),'date_kind':'encerramento','minimum_bid':bid,'bid_origin':origin,'rule':match(r'(onde serão aceitos[^.]+)',part),'source':'contrato publicado no HTML'})
    panel=[]
    summary=root.first(cls='summary-info')
    for instance in summary.all(cls='instance'):
        tx=instance.text();n=match(r'(\d)[ªº]\s*Praça',tx)
        if not n:continue
        old=next((s for s in d['stages'] if s['number']==int(n)),{})
        panel.append({**old,'number':int(n),'date':brdate(tx),'date_kind':'data da praça no painel','minimum_bid':money(instance.first(cls='card-instance-value').text()),'bid_origin':'fonte: painel da praça','source':'HTML da página'})
    if panel:d['stages']=panel+[s for s in d['stages'] if s['number'] not in [x['number'] for x in panel]]
    d['status']=summary.first(cls='instance-text').text() or None
    if not d['valuation']:
        d['valuation']=None;d.setdefault('warnings',[]).append('Avaliação ausente ou exibida como zero; desconto sobre avaliação não calculado.')
    if not d['stages']:d.setdefault('warnings',[]).append('Etapas não interpretadas; consultar edital.')
    d=basics(d,description)
    if d['initial_bid'] and d['stages'] and not any(s['minimum_bid'] and abs(s['minimum_bid']-d['initial_bid'])<1 for s in d['stages']):d['warnings'].append('Valor inicial do painel difere dos valores calculados pela avaliação; conferir edital e atualização monetária.')
    if d['address'] and 'Pedro Doll' in d['address'] and '503' in description and '485' in d['address']:d['warnings'].append('Endereço divergente na fonte: painel nº 485; descrição nº 503. Agrupamento automático por endereço desativado.')
    return d

def saraiva(html,url):
    m=re.search(r'var lote\s*=\s*(\{.*?\});',html,re.S)
    if not m:raise CollectError('estrutura_alterada','Dados estruturados do lote ausentes.')
    x=json.loads(m[1]);root=DOM(html).root;txt=root.text();a=x['leilao']
    desc=match(r'Descrição\s+(.*?)\s+Direito de Prefer',txt) or ''
    d={'title':x['descricao'],'external_id':str(x['id']),'auction_external_id':str(a['id']),'url':url,'city':match(r'[,|]\s*([^,|]+?)/\s*[A-Z]{2}\s*$',x['descricao']),'uf':match(r'/\s*([A-Z]{2})\s*$',x['descricao']),'address':match(r'Localização:\s*(.*)',desc),'valuation':money(x.get('valorAvaliacao')),'initial_bid':money(x.get('valorInicialAtual')),'status':'inativo' if not x.get('active') or x.get('deleted') else None,'status_code':x.get('status'),'auctioneer':match(r'Leiloeiro\s+(.*?)\s+Comitente',txt),'notice_links':documents(root,url),'stages':[]}
    for n in range(1,4):
        dt=a.get('data'+str(n));b=x.get('valorInicial'+(str(n) if n>1 else ''))
        if dt:d['stages'].append({'number':n,'date':dt['date'][:19].replace(' ','T')+'-03:00','date_kind':'data da praça','minimum_bid':money(b) if b else None,'bid_origin':'fonte','source':'JSON incorporado na página','timezone_source':dt.get('timezone')})
    return basics(d,desc)

def generic(html,url):
    root=DOM(html).root
    for script in root.all(tag='script'):
        if script.attrs.get('type')!='application/ld+json':continue
        try:obj=json.loads(''.join(x for x in script.children if isinstance(x,str)))
        except (ValueError,TypeError):continue
        items=obj if isinstance(obj,list) else obj.get('@graph',[obj])
        for x in items:
            if not isinstance(x,dict) or x.get('@type') not in ('Product','Apartment','House','RealEstateListing'):continue
            address=x.get('address') or {};address=address if isinstance(address,dict) else {'streetAddress':address}
            # Generic offers are not necessarily auction minimums. Preserve raw price separately.
            offers=x.get('offers') or {};offers=offers[0] if isinstance(offers,list) and offers else offers
            d={'title':x.get('name') or root.first(tag='h1').text(),'url':url,'external_id':str(x.get('sku') or x.get('productID') or url),'auction_external_id':'desconhecido','address':address.get('streetAddress'),'city':address.get('addressLocality'),'uf':address.get('addressRegion'),'valuation':None,'initial_bid':None,'advertised_price':money(offers.get('price')) if isinstance(offers,dict) else None,'auctioneer':None,'notice_links':documents(root,url),'status':None,'stages':[],'warnings':['Leitura genérica: preço anunciado não interpretado como lance; praças não confirmadas.']}
            return basics(d,x.get('description') or '')
    raise CollectError('estrutura_nao_suportada','Nenhum dado estruturado de imóvel reconhecido. Consulta assistida necessária.')

def zuk(html,url):
    root=DOM(html).root;txt=root.text();title=root.first(tag='h1').text();eid=url.rstrip('/').split('-')[-1]
    if not title or not re.search(r'cod:\s*'+re.escape(eid)+r'\b',root.first(tag='title').text(),re.I):raise CollectError('identidade_nao_confirmada','Página não confirma o código do imóvel solicitado.')
    address=match(re.escape(title)+r'\s+(.*?)(?:Entre em nosso canal|Relação completa do leilão|Encerra em)',txt)
    d={'title':title+(' — '+address if address else ''),'url':url,'external_id':eid,'auction_external_id':url.rstrip('/').split('/')[-1].split('-')[0],'address':address,'city':match(r'\s-\s([^-]+?)\s*/\s*[A-Z]{2}\s*$',address or ''),'uf':match(r'/\s*([A-Z]{2})\s*$',address or ''),'valuation':None,'initial_bid':None,'auctioneer':None,'status':None,'notice_links':documents(root,url),'stages':[],'warnings':['Avaliação e leiloeiro não identificados no painel; primeiro lance não convertido em avaliação.']}
    for n in root.all(cls='card-action-item'):
        number=match(r'(\d)[ºª]\s*Leilão',n.text())
        if not number:continue
        date=n.first(cls='card-action-item-date').text();m=re.search(r'(\d{2})/(\d{2})/(\d{2}|\d{4})\s+às\s+(\d{2})h(\d{2})',date)
        dt=(('20'+m[3] if len(m[3])==2 else m[3])+'-'+m[2]+'-'+m[1]+'T'+m[4]+':'+m[5]+':00-03:00') if m else None
        price=money(match(r'R\$\s*([\d.,]+)',n.first(cls='card-action-item-value').text()))
        d['stages'].append({'number':int(number),'date':dt,'date_kind':'data da praça','minimum_bid':price,'bid_origin':'fonte: painel','source':'HTML da página'})
    d=basics(d,root.first(cls='property-info').text())
    if 'Imóvel ocupado' in txt:d['occupancy']='ocupado'
    elif 'Imóvel desocupado' in txt:d['occupancy']='desocupado'
    return d

def browser_text(text,url):
    """Parses visible text from Top/Krobel. Can be supplied by optional Playwright collector."""
    desc=match(r'Descrição do bem\s*(?:Favoritos\s*(?:star\s*)?)?(.*?)\s*(?:Características do Imóvel|Pagamento|Dados do leilão)',text)
    if not desc:raise CollectError('estrutura_alterada','Descrição do bem não encontrada no texto visível.')
    title=match(r'VISITAS:\s*[\d.,]+\s+(.*?)\s+Valor:',text)
    d={'title':title or 'Imóvel em pregão','url':url,'external_id':url.rstrip('/').split('/')[-1],'auction_external_id':url.rstrip('/').split('/')[-2],'address':match(r'Endereço:\s*(.*?)\s*Visitação:',text),'city':match(r'Cidade/UF:\s*([^/]+)/[A-Z]{2}',text),'uf':match(r'Cidade/UF:\s*[^/]+/([A-Z]{2})',text),'valuation':money(match(r'Valor avaliação:\s*R\$\s*([\d.,]+)',text)),'initial_bid':money(match(r'Valor:\s*R\$\s*([\d.,]+)',text)),'status':match(r'Disponibilidade:\s*(\w+)',text),'auctioneer':match(r'Krobel Leilões\s+(.*?)\s+Leiloeira Pública',text),'notice_links':[],'stages':[],'warnings':['Edital acionado por botão: link não extraído nesta versão.']}
    section=match(r'Datas dos Leilões(.*?)Dados do Processo',text) or ''
    for m in re.finditer(r'(\d)[ºª]\s*Leilão:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})\s*Valor leilão:\s*R\$\s*([\d.,]+)',section,re.I):d['stages'].append({'number':int(m[1]),'date':brdate(m[2]),'date_kind':'data da praça','minimum_bid':money(m[3]),'bid_origin':'fonte','source':'texto visível do navegador'})
    if d['address'] in ('-',''):d['address']=None
    return basics(d,desc)

def parse(html,url,adapter):
    d={'mega':mega,'saraiva':saraiva,'generic':generic,'zuk':zuk}[adapter](html,url)
    d['checked_at']=now();d['origin']='site';return d

def discover(html,url,pattern):
    root=DOM(html).root;host=urllib.parse.urlsplit(url).hostname;links=[];pages=[]
    for a in root.all(tag='a'):
        href=a.attrs.get('href','')
        if not href:continue
        try:u=canonical(urllib.parse.urljoin(url,href))
        except ValueError:continue
        if urllib.parse.urlsplit(u).hostname!=host:continue
        if re.search(pattern,urllib.parse.urlsplit(u).path):links.append(u)
        if a.attrs.get('rel')=='next' or norm(a.text()) in ('proxima','proximo','próxima','próximo','›','»'):pages.append(u)
    return list(dict.fromkeys(links)),list(dict.fromkeys(pages))
