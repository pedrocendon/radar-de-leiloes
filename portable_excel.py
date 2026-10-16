"""Redistributable Excel writer for installations without the Codex runtime.

Uses the BSD-licensed XlsxWriter bundled in the Windows installer. Formula caches
are written explicitly so the report also reads correctly without Excel running.
"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

STATUS={'ok':'Leitura concluída','assistida':'Consulta assistida','parcial':'Leitura parcial','falha_rede':'Falha de rede','bloqueado':'Acesso bloqueado','redirecionado':'Link redirecionado','navegador_necessario':'Requer navegador','referencia_planilha':'Referência original','erro_interpretacao':'Falha de interpretação'}
ORIGIN={'site':'Site','planilha':'Planilha original','consulta_assistida':'Texto do navegador'}
MONEY='"R$" #,##0.00'
DATE='dd/mm/yyyy hh:mm'
DAY='dd/mm/yyyy'

def date(value):
    if not value:return None
    try:return datetime.fromisoformat(value).replace(tzinfo=None)
    except (ValueError,TypeError):return None

def text(value):
    if value is None:return ''
    if isinstance(value,(dict,list)):return json.dumps(value,ensure_ascii=False)
    return str(value)

def joined(values):return '\n'.join(map(text,values)) if isinstance(values,list) else text(values)

def build_report(payload,output):
    import xlsxwriter
    from xlsxwriter.utility import xl_col_to_name
    data=payload
    wb=xlsxwriter.Workbook(str(output),{'strings_to_formulas':False,'strings_to_urls':False})
    wb.set_properties({'title':'Radar de Leilões','author':'Radar de Leilões','comments':'Gerado automaticamente a partir dos dados salvos no programa.'})
    wb.set_calc_mode('auto')
    names=['Painel','Anúncios','Praças','Áreas','Fontes','Alterações','Guia']
    sheets={name:wb.add_worksheet(name) for name in names}
    formats={}
    def fmt(number=None,bold=False,fill=None,color='#23334A',size=11):
        key=(number,bold,fill,color,size)
        if key not in formats:
            opts={'font_name':'Calibri','font_size':size,'font_color':color,'valign':'vcenter','text_wrap':True}
            if number:opts['num_format']=number
            if bold:opts['bold']=True
            if fill:opts['bg_color']=fill
            formats[key]=wb.add_format(opts)
        return formats[key]
    def write(s,row,column,value,number=None):
        style=fmt(number)
        if value is None or value=='':s.write_blank(row,column,None,style)
        elif isinstance(value,datetime):s.write_datetime(row,column,value,fmt(number or DATE))
        elif isinstance(value,(dict,list)):s.write_string(row,column,text(value),style)
        elif isinstance(value,str) and value.startswith(('https://','http://')) and '\n' not in value and len(value)<2079:s.write_url(row,column,value,fmt(color='#245F91'))
        else:s.write(row,column,value,style)
    def base(name,title,subtitle,widths):
        s=sheets[name];s.hide_gridlines(2);s.freeze_panes(5,1);s.set_default_row(25)
        for i,width in enumerate(widths):s.set_column(i,i,width,fmt())
        s.merge_range(0,0,0,min(3,len(widths))-1,title,fmt(bold=True,color='#284561',size=20));s.set_row(0,34)
        s.merge_range(1,0,1,min(7,len(widths))-1,subtitle,fmt(color='#657489',size=10));s.set_row(1,32)
        s.set_landscape();s.fit_to_pages(1,0);s.repeat_rows(0,4)
        return s
    def table(s,headers,rows,name,start=5,formats_by_col=None,height=62):
        formats_by_col=formats_by_col or {};first=start-1;end=first+max(1,len(rows))
        s.add_table(first,0,end,len(headers)-1,{'name':name,'style':'Table Style Medium 2','columns':[{'header':h,'header_format':fmt(bold=True,fill='#284561',color='#FFFFFF')} for h in headers]})
        s.set_row(first,38)
        for index,row in enumerate(rows):
            n=first+1+index;s.set_row(n,height)
            for c,value in enumerate(row):write(s,n,c,value,formats_by_col.get(c))
        return (first+2,end+1)
    def formula(s,row,col,expression,value,number=None):s.write_formula(row-1,col,expression,fmt(number),'' if value is None else value)
    def discount(s,row,bid,valuation,column='H',bidcol='F',valuecol='G'):
        value=1-bid/valuation if bid is not None and valuation is not None and valuation>0 else None
        formula(s,row,ord(column)-65,f'=IF(AND(ISNUMBER({bidcol}{row}),ISNUMBER({valuecol}{row}),{valuecol}{row}>0),1-{bidcol}{row}/{valuecol}{row},"")',value,'0.0%')
        return value
    def status_colors(s,col,start,end):
        for word,bg,fg in [('concluída','#E6F1E9','#285C39'),('Falha','#FCE7E6','#943A35'),('bloqueado','#FCE7E6','#943A35'),('parcial','#FFF1CF','#795C19'),('assistida','#FFF1CF','#795C19')]:
            s.conditional_format(f'{col}{start}:{col}{end}',{'type':'text','criteria':'containing','value':word,'format':fmt(fill=bg,color=fg)})
    generated=date(data['generated_at']);today=generated.replace(hour=0,minute=0,second=0,microsecond=0)
    listings=sorted(data['listings'],key=lambda r:(-r.get('similarity',0),text(r['data'].get('city'))))
    listing_by_id={r['id']:r for r in listings}
    code=lambda r:r['id'][:8].upper()
    if len(set(map(code,listings)))!=len(listings):raise ValueError('Códigos curtos de anúncio repetidos.')
    sources=data['config']['sources'];source_names={s['id']:s['name'] for s in sources}
    filters=data['config']['filters'];active=any(v not in (None,'',[]) for k,v in filters.items() if k!='show_pending')
    match=lambda value:({'corresponde':'Atende aos filtros','pendente':'Dados insuficientes','fora':'Fora dos filtros'}.get(value,value) if active else 'Sem filtros ativos')
    stages=sorted([r for r in data['results'] if r.get('praca') is not None],key=lambda r:(r.get('data_praca') or '9999',r['anuncio_id'],r['praca']))
    key=lambda r:(r['anuncio_id'],r.get('leilao_id'),r['praca'])
    stage_index={key(r):i+6 for i,r in enumerate(stages)}
    s=base('Praças','Praças e etapas','Uma linha por etapa. Datas e lances pertencem à mesma praça. Valores ausentes ficam vazios.',[12,43,23,8,21,20,20,14,22,22,24,23,25,32,50,28,26])
    pr=table(s,['Código','Imóvel','Cidade / UF','Praça','Data da praça','Lance mínimo','Avaliação da fonte','Desconto calculado','Situação da data','Natureza da data','Situação da coleta','Critérios desta praça','Situação do anúncio','Origem do lance','Link do anúncio','Leilão na fonte','Início da etapa'],[[code(listing_by_id[r['anuncio_id']]),r.get('titulo'),joined([x for x in [r.get('cidade'),r.get('uf')] if x]),r['praca'],date(r.get('data_praca')),r.get('lance_minimo'),r.get('avaliacao_fonte'),None,None,r.get('natureza_data'),STATUS.get(r['situacao_coleta'],r['situacao_coleta']),match(r.get('criterio_praca')),r.get('situacao_anuncio'),r.get('origem_lance'),r['url'],r.get('leilao_id'),date(r.get('inicio_praca'))] for r in stages],'TabelaPracas',formats_by_col={5:MONEY,6:MONEY,4:DATE,16:DATE})
    discounts={}
    for i,r in enumerate(stages,6):
        discounts[key(r)]=discount(s,i,r.get('lance_minimo'),r.get('avaliacao_fonte'))
        d=date(r.get('data_praca'));value='Não informada' if d is None else 'Data passada' if d<today else 'Hoje ou futura'
        formula(s,i,8,f'=IF(E{i}="","Não informada",IF(E{i}<\'Guia\'!$B$6,"Data passada","Hoje ou futura"))',value)
        if d and 'T' not in r['data_praca']:write(s,i-1,4,d,DAY)
    status_colors(s,'K',*pr)
    a=base('Anúncios','Anúncios acompanhados','Use as setas dos cabeçalhos para filtrar cidade, fonte, coleta e critérios.',[12,47,24,16,24,21,20,14,22,25,29,24,50,24,18,30,20,20,27,26,50,50,50,44,24,24,26,27,30,44])
    next_stages={r['id']:next((s for s in stages if s['anuncio_id']==r['id'] and date(s.get('data_praca')) and date(s['data_praca'])>=today),None) for r in listings}
    rows=[]
    for r in listings:
        d=r['data'];n=next_stages[r['id']] or {}
        rows.append([code(r),d.get('title') or 'Anúncio sem dados interpretados',' / '.join(filter(None,[d.get('city'),d.get('uf')])),d.get('type'),STATUS.get(r['collection_status'],r['collection_status']),date(n.get('data_praca')),n.get('lance_minimo'),None,match(r['match']),d.get('occupancy'),joined(r.get('similar_reasons')),source_names.get(r['source'],r['source']),d.get('address'),d.get('status'),n.get('praca'),d.get('auctioneer'),d.get('valuation'),d.get('personal_ceiling'),date(r.get('last_attempt')),date(r.get('last_success')),r['url'],joined(d.get('notice_links')),joined(r.get('group_links')),r.get('detail'),ORIGIN.get(d.get('origin'),d.get('origin')),r.get('property_id'),r['id'],date(d.get('checked_at')) if d.get('origin')=='consulta_assistida' else None,joined(r.get('match_reasons')),joined(d.get('warnings'))])
    ar=table(a,['Código','Imóvel','Cidade / UF','Tipo','Situação da coleta','Próxima data conhecida','Lance dessa praça','Desconto dessa praça','Critérios do anúncio','Ocupação','Semelhança com a seleção','Fonte','Endereço','Situação do anúncio','Praça seguinte','Leiloeiro','Avaliação da fonte','Teto pessoal original','Última tentativa','Última leitura HTTP','Link do anúncio','Editais','Links do mesmo grupo','Observações da coleta','Origem dos dados','Grupo de imóvel','ID completo do anúncio','Última leitura assistida','Motivos dos critérios','Alertas do anúncio'],rows,'TabelaAnuncios',formats_by_col={6:MONEY,16:MONEY,17:MONEY,5:DATE,18:DATE,19:DATE,27:DATE},height=76)
    for i,r in enumerate(listings,6):
        n=next_stages[r['id']]
        if n:
            k=stage_index[key(n)];formula(a,i,7,f'=IF(ISNUMBER(\'Praças\'!H{k}),\'Praças\'!H{k},"")',discounts[key(n)],'0.0%')
            if 'T' not in n['data_praca']:write(a,i-1,5,date(n['data_praca']),DAY)
    status_colors(a,'E',*ar)
    area=base('Áreas','Áreas informadas','Áreas privativas, totais, terrenos e garagens permanecem separadas. Confira o contexto do anúncio.',[12,47,19,17,78,23,50])
    table(area,['Código','Imóvel','Tipo de área','Área (m²)','Contexto publicado','Origem','Link do anúncio'],[[code(r),r['data'].get('title'),x.get('kind'),x.get('m2'),x.get('context'),x.get('origin'),r['url']] for r in listings for x in r['data'].get('areas',[])],'TabelaAreas',formats_by_col={3:'#,##0.000'},height=66)
    f=base('Fontes','Fontes e consultas','Falhas preservam o último dado armazenado. A cobertura é uma amostra dos catálogos.',[25,24,24,57,74,26,26])
    source_rows=[]
    for src in sources:
        run=next((r for r in data['runs'] if r['source']==src['id']),{})
        source_rows.append([src['name'],{'browser':'Importação assistida','blocked':'Acesso bloqueado'}.get(src['adapter'],'Página pública'),'Sim' if src.get('enabled') else 'Não',src['root'],src['note'],date(run.get('at')),STATUS.get(run.get('status'),run.get('status','Sem rodada'))])
    fr=table(f,['Fonte','Método','Habilitada','Página inicial','Limitação conhecida','Última rodada','Resultado da rodada'],source_rows,'TabelaFontes',formats_by_col={5:DATE},height=76)
    table(f,['Consulta em','Fonte','Resultado','Detalhes da cobertura'],[[date(r['at']),source_names.get(r['source'],r['source']),STATUS.get(r['status'],r['status']),text(r.get('details'))] for r in data['runs']],'TabelaConsultas',start=fr[1]+4,formats_by_col={0:DATE},height=106)
    field_names={'collection_status':'Situação da coleta','warnings':'Alertas','valuation':'Avaliação','title':'Título','status':'Situação do anúncio','stages':'Praças e datas','occupancy':'Ocupação','address':'Endereço','areas':'Áreas','auctioneer':'Leiloeiro','city':'Cidade','uf':'UF','type':'Tipo','notice_links':'Editais','registry':'Matrícula','registry_numbers':'Matrículas','registry_office':'Cartório','asset_scope':'Objeto da venda','description':'Descrição','initial_bid':'Lance inicial','auction_external_id':'Leilão na fonte'}
    def history_value(value,field):
        try:value=json.loads(value)
        except (ValueError,TypeError):pass
        if value is None:return 'Não informado'
        if field=='collection_status':return STATUS.get(value,value)
        if isinstance(value,(int,float)):return value
        if field=='stages' and isinstance(value,list):
            value='\n'.join(f"{x.get('number')}ª praça: {x.get('date') or 'data não informada'}; lance {x.get('minimum_bid') if x.get('minimum_bid') is not None else 'não informado'}" for x in value)
        elif isinstance(value,list):value=joined(value)
        return text(value)[:2000]
    h=base('Alterações','Histórico de alterações','Valores anteriores e novos. Textos extensos são resumidos; a íntegra permanece em alteracoes.csv.',[23,23,50,68,68,50])
    hr=table(h,['Registrado em','Campo alterado','Imóvel / anúncio','Valor anterior','Novo valor','Link do anúncio'],[[date(r['at']),field_names.get(r['field'],r['field']),listing_by_id.get(r['listing_id'],{}).get('data',{}).get('title',r['url']),history_value(r['old'],r['field']),history_value(r['new'],r['field']),r['url']] for r in data['history']],'TabelaAlteracoes',formats_by_col={0:DATE},height=100)
    table(h,['Anúncio A','Anúncio B','Motivo'],[[r['url_a'],r['url_b'],r['reason']] for r in data['duplicates']],'TabelaDuplicados',start=hr[1]+4)
    g=base('Guia','Como usar a planilha','A origem dos valores permanece identificada em cada aba. Os links apontam para as fontes.',[36,98])
    for i,(label,value) in enumerate([('Gerada em',generated),('Data-base das datas futuras',today),('Última tentativa de consulta',date(max((r.get('last_attempt') or '' for r in listings),default=''))),('Grupos registrados no banco',len({r['property_id'] for r in listings})),('Atualização','Automática após cada consulta ou exportação do programa.')],4):
        write(g,i,0,label);write(g,i,1,value,DAY if i==5 else None)
    guide=[('Abrir e filtrar','Comece no Painel. Anúncios e Praças têm filtros nos cabeçalhos. O Painel resume toda a base.'),('Atualizar a busca','Feche o Excel. No Radar, clique em Buscar novidades. Abra a planilha novamente após a conclusão.'),('Atualizar só a planilha','No Radar, clique em Atualizar planilha. Usa os dados salvos, sem consultar os sites.'),('Execução agendada','Configure a repetição em Minha busca. O computador e o programa precisam estar ligados.'),('Arquivo aberto no Excel','Se o Excel impedir a gravação, a versão anterior será mantida. Feche-a e atualize novamente.'),('Anotações pessoais','As abas são recriadas. Use Baixar cópia antes de escrever anotações próprias.'),('Dados extraídos','Avaliação, lance, datas, endereço e ocupação refletem a fonte. Célula vazia significa dado ausente.'),('Desconto calculado','1 − lance mínimo ÷ avaliação publicada. Não usa estimativa pessoal de mercado.'),('Próxima data conhecida','Primeira etapa registrada com data igual ou posterior à data-base. Não confirma disponibilidade.'),('Horários','O horário exibido é o informado na fonte. As exportações JSON preservam os fusos originais.'),('Leitura concluída','A página foi interpretada. Confira a situação do anúncio e a última tentativa.'),('Falha de consulta','Não significa ausência de imóveis. Dados anteriores são preservados.'),('Semelhança','Critérios de ordenação não são filtros obrigatórios. Configure sua própria busca.'),('Identificadores','Imóvel, anúncio e praça têm identificações separadas. Possíveis duplicados exigem conferência.'),('Origem dos dados','Site: leitura automática. Texto do navegador: consulta assistida. Referência original: sem confirmação.'),('Links e áreas','Links permitem conferir a fonte. Áreas totais e privativas permanecem separadas.')]
    table(g,['Assunto','Orientação'],guide,'TabelaGuia',start=12,height=58)
    table(g,['Filtro ativo no programa','Valor'],[[k,joined(v) if isinstance(v,list) and v else 'Sem restrição' if v in (None,[], '') else 'Sim' if v is True else 'Não' if v is False else v] for k,v in filters.items()],'TabelaFiltros',start=31,height=30)
    p=base('Painel','Radar de Leilões','Base armazenada no programa. Consulte as datas de coleta antes de decidir quais anúncios acompanhar.',[44,24,12,23,21,17,26,23]);p.freeze_panes(4,0)
    write(p,3,0,'Atualização da planilha');write(p,3,1,generated)
    table(p,['Fonte','Anúncios','Leitura OK','Assistidos','Com pendência'],[[s['name'],None,None,None,None] for s in sources],'ResumoFontes',start=6,height=30)
    for i,src in enumerate(sources,7):
        records=[r for r in listings if r['source']==src['id']];ok=sum(r['collection_status']=='ok' for r in records);assisted=sum(r['collection_status']=='assistida' for r in records);criteria=src['name'].replace('"','""')
        formula(p,i,1,f'=COUNTIF(\'Anúncios\'!$L$6:$L${ar[1]},"{criteria}")',len(records))
        for col,status,value in [(2,'Leitura concluída',ok),(3,'Consulta assistida',assisted)]:formula(p,i,col,f'=COUNTIFS(\'Anúncios\'!$L$6:$L${ar[1]},"{criteria}",\'Anúncios\'!$E$6:$E${ar[1]},"{status}")',value)
        formula(p,i,4,f'=B{i}-C{i}-D{i}',len(records)-ok-assisted)
    write(p,5,6,'Base acompanhada');write(p,5,7,'Quantidade')
    metrics=[('Anúncios',f'=COUNTA(\'Anúncios\'!A6:A{ar[1]})',len(listings)),('Grupos registrados',"='Guia'!B8",len({r['property_id'] for r in listings})),('Praças conhecidas',f'=COUNT(\'Praças\'!D6:D{pr[1]})',len(stages)),('Datas hoje / futuras',f'=COUNTIF(\'Praças\'!I6:I{pr[1]},"Hoje ou futura")',sum(bool(date(r.get('data_praca')) and date(r['data_praca'])>=today) for r in stages)),('Possíveis duplicados',f'={len(data["duplicates"])}',len(data['duplicates']))]
    for row,(label,expression,value) in enumerate(metrics,7):write(p,row-1,6,label);formula(p,row,7,expression,value)
    p.merge_range('A14:H14','Pendências incluem falhas e leituras parciais. Os últimos dados são preservados.',fmt(color='#657489'))
    p.merge_range('A15:H15','Próximas datas registradas. Confirme a disponibilidade no anúncio.',fmt(bold=True,color='#284561'))
    upcoming=[r for r in stages if date(r.get('data_praca')) and date(r['data_praca'])>=today][:14]
    table(p,['Imóvel','Cidade / UF','Praça','Data registrada','Lance mínimo','Desconto','Fonte','Situação da coleta'],[[None]*8 for _ in upcoming],'AgendaPracas',start=17,height=58)
    for i,r in enumerate(upcoming,18):
        k=stage_index[key(r)]
        values=[r.get('titulo'),' / '.join(filter(None,[r.get('cidade'),r.get('uf')])),r['praca'],None,r.get('lance_minimo'),discounts[key(r)]]
        values[3]=(date(r['data_praca'])-datetime(1899,12,30)).total_seconds()/86400
        for c,value in enumerate(values):
            source=['B','C','D','E','F','H'][c];expression=f"='Praças'!{source}{k}" if c<4 else f'=IF(ISNUMBER(\'Praças\'!{source}{k}),\'Praças\'!{source}{k},"")'
            formula(p,i,c,expression,value,({3:DATE if 'T' in r['data_praca'] else DAY,4:MONEY,5:'0.0%'}).get(c))
        write(p,i-1,6,source_names.get(r['fonte'],r['fonte']));write(p,i-1,7,STATUS.get(r['situacao_coleta'],r['situacao_coleta']))
    wb.close()
