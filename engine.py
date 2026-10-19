"""Persistence, filters, safe consolidation, observations and CSV exports."""
import json,sqlite3,hashlib,csv,re,threading,math
from contextlib import contextmanager
from pathlib import Path
from collectors import now,norm,canonical,Client,CollectError,parse,discover

def ident(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()[:20]
def dump(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,x):
    p=Path(path);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)

def connect_database(path):
    if not hasattr(sqlite3.Connection,'setconfig'):
        raise RuntimeError('Use Python 3.12 ou superior para ativar as proteções do banco de dados.')
    db=sqlite3.connect(path,timeout=30)
    try:
        # The application supplies SQL and never imports third-party databases.
        # Defense in depth for bundled SQLite versions: disable dangerous schema
        # changes and extension loading before preparing any statement.
        db.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE,True)
        db.setconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA,False)
        db.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION,False)
        db.row_factory=sqlite3.Row
        return db
    except Exception:
        db.close()
        raise

class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:db.executescript('''
          CREATE TABLE IF NOT EXISTS properties(id TEXT PRIMARY KEY, identity_key TEXT UNIQUE);
          CREATE TABLE IF NOT EXISTS listings(id TEXT PRIMARY KEY,property_id TEXT,source TEXT,url TEXT UNIQUE,data TEXT,last_attempt TEXT,last_success TEXT,collection_status TEXT,detail TEXT);
          CREATE TABLE IF NOT EXISTS auctions(id TEXT PRIMARY KEY,listing_id TEXT,external_id TEXT);
          CREATE TABLE IF NOT EXISTS stages(id TEXT PRIMARY KEY,auction_id TEXT,number INTEGER,data TEXT,current INTEGER);
          CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY,listing_id TEXT,at TEXT,status TEXT,data TEXT,detail TEXT);
          CREATE TABLE IF NOT EXISTS changes(id INTEGER PRIMARY KEY,listing_id TEXT,at TEXT,field TEXT,old TEXT,new TEXT);
          CREATE TABLE IF NOT EXISTS source_runs(id INTEGER PRIMARY KEY,at TEXT,source TEXT,status TEXT,details TEXT);
          CREATE TABLE IF NOT EXISTS favorites(listing_id TEXT PRIMARY KEY,created_at TEXT NOT NULL);
        ''')
    @contextmanager
    def connect(self):
        db=connect_database(self.path)
        try:
            with db:yield db
        finally:db.close()
    def key(self,d,url,overrides):
        if url in overrides:return 'manual:'+str(overrides[url])
        if d.get('registry') and d.get('registry_office') and d.get('city') and d.get('uf') and len(d.get('registry_numbers',[]))==1 and d.get('asset_scope')=='direitos sobre o imóvel':
            return 'registro:'+norm('|'.join([d['registry'],d['registry_office'],d['city'],d['uf'],d['asset_scope']]))
        # Address matches are candidates only: spelling/unit/rights differences can be material.
        return 'anuncio:'+url
    def put(self,source,url,data=None,status='ok',detail='',overrides=None):
        url=canonical(url);lid=ident(url);at=now();overrides=overrides or {}
        with self.connect() as db:
            old=db.execute('SELECT * FROM listings WHERE id=?',(lid,)).fetchone()
            olddata=json.loads(old['data']) if old else {}
            if data is not None:
                data=dict(data)
                for personal in ('market_estimate','personal_ceiling','source_cells','selected_date'):
                    if personal in olddata:data.setdefault(personal,olddata[personal])
                data.setdefault('provenance',{}).update({k:'planilha do usuário' for k in ('market_estimate','personal_ceiling','source_cells','selected_date') if k in data})
            db.execute('INSERT INTO observations(listing_id,at,status,data,detail) VALUES(?,?,?,?,?)',(lid,at,status,dump(data),detail))
            if data is not None:
                key=self.key(data,url,overrides);pid=ident(key)
                db.execute('INSERT OR IGNORE INTO properties VALUES(?,?)',(pid,key))
                if old:
                    for field in sorted(set(olddata)|set(data)):
                        if field in ('checked_at','provenance'):continue
                        if olddata.get(field)!=data.get(field):db.execute('INSERT INTO changes(listing_id,at,field,old,new) VALUES(?,?,?,?,?)',(lid,at,field,dump(olddata.get(field)),dump(data.get(field))))
                aid=ident(lid+'|'+str(data.get('auction_external_id') or 'desconhecido'))
                db.execute('INSERT OR IGNORE INTO auctions VALUES(?,?,?)',(aid,lid,str(data.get('auction_external_id'))))
                db.execute('UPDATE stages SET current=0 WHERE auction_id IN (SELECT id FROM auctions WHERE listing_id=?)',(lid,))
                for stage in data.get('stages',[]):db.execute('INSERT OR REPLACE INTO stages VALUES(?,?,?,?,1)',(ident(aid+'|'+str(stage['number'])),aid,stage['number'],dump(stage)))
            else:pid=old['property_id'] if old else ident('anuncio:'+url)
            for field,new in [('collection_status',status)]:
                if old and old[field]!=new:db.execute('INSERT INTO changes(listing_id,at,field,old,new) VALUES(?,?,?,?,?)',(lid,at,field,dump(old[field]),dump(new)))
            db.execute('INSERT OR REPLACE INTO listings VALUES(?,?,?,?,?,?,?,?,?)',(lid,pid,source,url,dump(data if data is not None else olddata),at,at if data is not None and data.get('origin')=='site' else (old['last_success'] if old else None),status,detail))
    def rows(self):
        with self.connect() as db:
            rows=[]
            for r in db.execute('SELECT l.*,f.created_at AS favorited_at FROM listings l LEFT JOIN favorites f ON f.listing_id=l.id ORDER BY l.source,l.url'):
                x=dict(r);x['data']=json.loads(x['data']);rows.append(x)
            return rows
    def set_favorite(self,listing_id,enabled):
        # Keep user selections separate from collector writes (which replace listings).
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM listings WHERE id=?',(listing_id,)).fetchone():
                raise ValueError('Este anúncio não foi encontrado. Atualize a tela e tente novamente.')
            if enabled:
                db.execute('INSERT OR IGNORE INTO favorites(listing_id,created_at) VALUES(?,?)',(listing_id,now()))
            else:db.execute('DELETE FROM favorites WHERE listing_id=?',(listing_id,))
            row=db.execute('SELECT created_at FROM favorites WHERE listing_id=?',(listing_id,)).fetchone()
            return row['created_at'] if row else None
    def log(self,source,status,detail):
        with self.connect() as db:db.execute('INSERT INTO source_runs(at,source,status,details) VALUES(?,?,?,?)',(now(),source,status,detail))
    def history(self):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT c.*,l.url FROM changes c LEFT JOIN listings l ON l.id=c.listing_id ORDER BY c.id DESC LIMIT 500')]
    def runs(self):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT * FROM source_runs ORDER BY id DESC LIMIT 100')]

def evaluate(d,f):
    reasons=[];unknown=[];failed=[]
    for field,key in [('city','cities'),('uf','states'),('type','types')]:
        wanted=f.get(key) or []
        if not wanted:continue
        if not d.get(field):unknown.append(field+' ausente')
        elif norm(d[field]) not in [norm(x) for x in wanted]:failed.append(field+' fora do filtro')
        else:reasons.append(field+': '+d[field])
    # Every numeric and date condition must be met by the SAME auction stage.
    stage_filters=any(f.get(k) is not None and f.get(k)!='' for k in ('min_price','max_price','min_discount','date_from','date_to'))
    matching=[];pending=[]
    for s in d.get('stages',[]) or [{}]:
        fail=[];missing=[];why=[];price=s.get('minimum_bid');dt=(s.get('date') or '')[:10];valuation=d.get('valuation')
        discount=round((1-price/valuation)*100,4) if price is not None and valuation and valuation>0 else None
        for key,value,test in [('min_price',price,lambda x,y:x>=y),('max_price',price,lambda x,y:x<=y),('min_discount',discount,lambda x,y:x>=y),('date_from',dt or None,lambda x,y:x>=y),('date_to',dt or None,lambda x,y:x<=y)]:
            wanted=f.get(key)
            if wanted is None or wanted=='':continue
            if value is None:missing.append(key+' sem dado')
            elif not test(value,wanted):fail.append(key)
            else:why.append(key+' atendido ('+str(value)+')')
        if not fail:
            if missing:pending.extend(missing)
            else:matching.append({'stage':s.get('number'),'reasons':why,'discount':discount})
    if stage_filters and not matching:
        if pending:unknown.extend(sorted(set(pending)))
        else:failed.append('Nenhuma praça atende simultaneamente preço, desconto e data')
    if matching and stage_filters:reasons.extend(['Praça '+str(m['stage'])+': '+', '.join(m['reasons']) for m in matching])
    if failed:return 'fora',reasons+failed
    if unknown:return 'pendente',reasons+unknown
    return 'corresponde',reasons or ['Sem filtros obrigatórios configurados']

def similarity(d,profile):
    if profile.get('kind')=='web':
        reasons=[]
        if norm(d.get('city')) in [norm(x) for x in profile.get('cities',[])]:reasons.append('Cidade escolhida na sua busca')
        if d.get('type') in profile.get('types',[]):reasons.append('Tipo escolhido na sua busca')
        return len(reasons),reasons
    reasons=[]
    if norm(d.get('city')) in [norm(x) for x in profile['cities']]:reasons.append('Cidade presente na seleção original')
    if d.get('type')=='apartamento':reasons.append('Mesmo tipo dos 9 imóveis selecionados')
    if d.get('subtype') in ('duplex','triplex'):reasons.append('Duplex/triplex aparece em 3 dos 9 imóveis')
    return len(reasons),reasons

def duplicate_candidates(rows):
    pairs=[]
    for i,a in enumerate(rows):
        da=a['data']
        for b in rows[i+1:]:
            db=b['data']
            if a['property_id']==b['property_id']:continue
            if not da.get('city') or norm(da['city'])!=norm(db.get('city')) or da.get('uf')!=db.get('uf'):continue
            same_address=da.get('address') and norm(da['address'])==norm(db.get('address'))
            same_registry=da.get('registry') and da['registry']==db.get('registry')
            same_title=da.get('title') and norm(da['title'])==norm(db.get('title'))
            if same_address or same_registry or same_title:pairs.append({'url_a':a['url'],'url_b':b['url'],'reason':'Endereço, matrícula ou título coincidente; conferir unidade, cartório, área e direitos antes de consolidar.'})
    return pairs

def validate_config(c):
    f=c['filters']
    for k in ('min_price','max_price','min_discount'):
        if f.get(k) is not None and (not isinstance(f[k],(int,float)) or not math.isfinite(f[k]) or f[k]<0):raise ValueError(k+': informe número positivo e finito ou null')
    if f.get('min_price') is not None and f.get('max_price') is not None and f['min_price']>f['max_price']:raise ValueError('Preço mínimo maior que o máximo.')
    if f.get('min_discount') is not None and f['min_discount']>100:raise ValueError('Desconto deve estar entre 0 e 100.')
    from datetime import date
    for k in ('date_from','date_to'):
        if f.get(k):date.fromisoformat(f[k])
    if f.get('date_from') and f.get('date_to') and f['date_from']>f['date_to']:raise ValueError('Data inicial maior que final.')
    for k in ('cities','states','types'):
        if not isinstance(f.get(k,[]),list):raise ValueError(k+' deve ser uma lista.')
    ids=set()
    for s in c['sources']:
        if s['id'] in ids:raise ValueError('ID de fonte repetido')
        ids.add(s['id'])
        if s['adapter'] not in ('mega','saraiva','zuk','generic','browser','blocked'):raise ValueError('Adaptador desconhecido')
        canonical(s['root']);re.compile(s['detail_pattern'])
        for u in s.get('discovery_urls',[]):canonical(u)
    for k in ('max_pages','max_new_per_source'):
        if not isinstance(c[k],int) or not 1<=c[k]<=100:raise ValueError(k+' deve estar entre 1 e 100')
    return c

def run(base,notify=lambda x:None,client=None):
    base=Path(base);config=validate_config(load(base/'config.json'));store=Store(base/'data/monitor.sqlite');seeds=load(base/'references.json');client=client or Client()
    known={r['url'] for r in store.rows()}
    for s in seeds:
        if canonical(s['url']) not in known:store.put(s['source'],s['url'],s,'referencia_planilha','Ainda não confirmado no site',config.get('property_overrides'))
    from notifications import Notifications
    notifications=Notifications(store);notifications.begin(config)
    for source in config['sources']:
        sid=source['id'];notify('Consultando '+source['name'])
        if not source.get('enabled',True):store.log(sid,'desativada','Fonte desativada na configuração');continue
        existing=[r['url'] for r in store.rows() if r['source']==sid]
        if source['adapter'] in ('browser','blocked'):
            status='navegador_necessario' if source['adapter']=='browser' else 'bloqueado'
            for url in existing:store.put(sid,url,status=status,detail=source['note'])
            store.log(sid,status,source['note']);continue
        urls=list(dict.fromkeys(existing+source.get('watch_urls',[])));queue=list(source.get('discovery_urls',[]));seen=set();new=[];problems=[]
        while queue and len(seen)<config['max_pages']:
            u=queue.pop(0)
            if u in seen:continue
            seen.add(u)
            try:
                page=client.get(u);found,following=discover(page,u,source['detail_pattern']);new.extend(found)
                catalogs=discover(page,u,source['catalog_pattern'])[0] if source.get('catalog_pattern') else []
                queue.extend(x for x in following+catalogs if x not in seen and x not in queue)
                if not found and not catalogs:problems.append('Nenhum link reconhecido em '+u+'; catálogo vazio ou estrutura diferente, sem confirmação.')
            except CollectError as e:problems.append(e.status+': '+u+' '+str(e))
        new=list(dict.fromkeys(u for u in new if u not in urls))
        new.sort(key=lambda u:sum(norm(city).replace(' ','-') in norm(u) for city in config['profile']['cities'])+int(any(w in norm(u) for w in ('apartamento','apto','duplex','triplex'))),reverse=True)
        limited=len(new)>config['max_new_per_source'] or bool(queue)
        urls.extend(new[:config['max_new_per_source']]);ok=0;errors=0
        for url in urls:
            try:
                html=client.get(url);d=parse(html,url,source['adapter']);store.put(sid,url,d,'ok' if d.get('stages') else 'parcial','; '.join(d.get('warnings',[])),config.get('property_overrides'));ok+=1
            except (CollectError,ValueError,KeyError,TypeError) as e:
                status=e.status if isinstance(e,CollectError) else 'erro_interpretacao';store.put(sid,url,status=status,detail=str(e));errors+=1
        status='parcial' if errors or problems or limited else 'ok'
        store.log(sid,status,dump({'lidos':ok,'falhas':errors,'novos_links':len(new),'paginas_lidas':len(seen),'limite_atingido':limited,'problemas':problems,'cobertura':'amostra limitada; não garante catálogo completo'}))
    notifications.capture(config)
    export(base)
    from xlsx_export import status_message
    notify('Consulta concluída. '+status_message(base));return store

def safe_cell(v):
    if v is None:return ''
    if isinstance(v,float):return str(v).replace('.',',')
    if isinstance(v,(dict,list)):v=dump(v)
    if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')):return "'"+v
    return v
def write_csv(path,rows,fields):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=';',extrasaction='ignore');w.writeheader();w.writerows({k:safe_cell(v) for k,v in r.items()} for r in rows)
def export(base):
    base=Path(base);store=Store(base/'data/monitor.sqlite');config=load(base/'config.json');rows=store.rows();out=[];groups={}
    for r in rows:groups.setdefault(r['property_id'],[]).append(r['url'])
    for r in rows:
        d=r['data'];result,why=evaluate(d,config['filters']);score,similar=similarity(d,config['profile'])
        for s in d.get('stages',[]) or [{}]:
            price=s.get('minimum_bid');valuation=d.get('valuation');discount=round((1-price/valuation)*100,4) if price is not None and valuation and valuation>0 else None
            out.append({'imovel_id':r['property_id'],'anuncio_id':r['id'],'leilao_id':d.get('auction_external_id'),'praca':s.get('number'),'titulo':d.get('title'),'endereco':d.get('address'),'cidade':d.get('city'),'uf':d.get('uf'),'tipo':d.get('type'),'areas_m2':d.get('areas'),'avaliacao_fonte':valuation,'lance_minimo':price,'origem_lance':s.get('bid_origin'),'desconto_calculado_pct':discount,'formula_desconto':'100 × (1 − lance / avaliação)' if discount is not None else None,'data_praca':s.get('date'),'natureza_data':s.get('date_kind'),'inicio_praca':s.get('starts_at'),'ocupacao':d.get('occupancy'),'leiloeiro':d.get('auctioneer'),'situacao_anuncio':d.get('status'),'fonte':r['source'],'url':r['url'],'links_todas_fontes':groups[r['property_id']],'editais':d.get('notice_links'),'ultima_consulta':r['last_attempt'],'ultima_coleta_site':r['last_success'],'situacao_coleta':r['collection_status'],'detalhe_coleta':r['detail'],'origem_dados':d.get('origin'),'correspondencia':result,'motivos':why,'semelhanca_pontos':score,'motivos_semelhanca':similar,'mercado_planilha':d.get('market_estimate'),'teto_planilha':d.get('personal_ceiling'),'proveniencia':d.get('provenance')})
    folder=base/'exports';folder.mkdir(exist_ok=True)
    fields=list(out[0]) if out else ['anuncio_id','url','situacao_coleta']
    write_csv(folder/'resultados.csv',out,fields)
    write_csv(folder/'alteracoes.csv',store.history(),['at','url','field','old','new'])
    write_csv(folder/'consultas.csv',store.runs(),['at','source','status','details'])
    write_csv(folder/'possiveis_duplicados.csv',duplicate_candidates(rows),['url_a','url_b','reason'])
    save(folder/'resultados.json',out)
    # A single snapshot feeds every worksheet, including collection failures.
    from xlsx_export import refresh_excel
    snapshot_rows=[]
    for r in rows:
        match,reasons=evaluate(r['data'],config['filters']);score,similar=similarity(r['data'],config['profile'])
        snapshot_rows.append(dict(r,match=match,match_reasons=reasons,similarity=score,similar_reasons=similar,group_links=groups[r['property_id']]))
    by_id={r['id']:r for r in rows}
    stage_results=[]
    for record in out:
        original=by_id[record['anuncio_id']]['data']
        selected=[s for s in original.get('stages',[]) if s.get('number')==record['praca']]
        match,_=evaluate(dict(original,stages=selected),config['filters'])
        stage_results.append(dict(record,criterio_praca=match))
    refresh_excel(base,{'generated_at':now(),'config':config,'listings':snapshot_rows,'results':stage_results,
                        'history':store.history(),'runs':store.runs(),'duplicates':duplicate_candidates(rows)})
    return folder
