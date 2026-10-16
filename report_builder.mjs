// Creates the complete managed workbook from a consistent database snapshot.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const require = createRequire(import.meta.url);
const library = require.resolve('@oai/artifact-tool', {paths:[process.env.RADAR_NODE_MODULES || process.cwd()]});
const {Workbook, SpreadsheetFile} = await import(pathToFileURL(library).href);
const [input, output, previewDir] = process.argv.slice(2);
const data = JSON.parse(await fs.readFile(input,'utf8'));
const wb = Workbook.create();
const names = ['Painel','Anúncios','Praças','Áreas','Fontes','Alterações','Guia'];
const sheets = Object.fromEntries(names.map(n=>[n,wb.worksheets.add(n)]));
const ink='#22344A', navy='#284561', blue='#245F91', muted='#657489', pale='#EDF3F8', amber='#FFF1CF';
const currency='"R$" #,##0.00', datefmt='dd/mm/yyyy hh:mm', dayfmt='dd/mm/yyyy';
const statusNames={ok:'Leitura concluída',assistida:'Consulta assistida',parcial:'Leitura parcial',falha_rede:'Falha de rede',bloqueado:'Acesso bloqueado',redirecionado:'Link redirecionado',navegador_necessario:'Requer navegador',referencia_planilha:'Referência original',erro_interpretacao:'Falha de interpretação'};
const origins={site:'Site',planilha:'Planilha original',consulta_assistida:'Texto do navegador'};
const sourceNames=Object.fromEntries(data.config.sources.map(s=>[s.id,s.name]));
const filtersActive=Object.entries(data.config.filters).some(([k,v])=>k!=='show_pending'&&(Array.isArray(v)?v.length:v!==null&&v!==''));
const matchLabel=v=>filtersActive?({corresponde:'Atende aos filtros',pendente:'Dados insuficientes',fora:'Fora dos filtros'}[v]||v):'Sem filtros ativos';
const text=v=>v==null?'':typeof v==='object'?JSON.stringify(v):String(v);
const safe=v=>typeof v==='string'&&/^\s*[=+@-]/.test(v)?"'"+v:v??null;
const join=v=>Array.isArray(v)?v.map(text).join('\n'):text(v);
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
// Excel has no timezone. Keep the source wall-clock time; offsets stay in provenance.
const date=v=>{if(!v)return null;const m=String(v).match(/^(\d{4})-(\d\d)-(\d\d)(?:T(\d\d):(\d\d)(?::(\d\d))?)?/);return m?new Date(Date.UTC(+m[1],+m[2]-1,+m[3],+(m[4]||0),+(m[5]||0),+(m[6]||0))):null;};
const generated=date(data.generated_at), today=new Date(Date.UTC(generated.getUTCFullYear(),generated.getUTCMonth(),generated.getUTCDate()));
function base(name,title,subtitle,widths,rows=30){
 const s=sheets[name],last=col(widths.length-1);
 s.showGridLines=false;
 s.getRange(`A1:${last}${rows}`).format={font:{name:'Calibri',size:11,color:ink},rowHeight:25,verticalAlignment:'center'};
 widths.forEach((w,i)=>s.getRange(`${col(i)}1:${col(i)}${rows}`).format.columnWidth=w);
 s.getRange('A1').values=[[title]];s.getRange('A1').format.font={name:'Calibri',size:20,bold:true,color:navy};s.getRange(`A1:${last}1`).format.rowHeight=34;
 s.getRange('A2').values=[[subtitle]];s.getRange(`A2:${last}2`).format.font={size:10,color:muted};
 s.getRange(`A3:${last}3`).format.borders={bottom:{style:'thin',color:'#CBD7E2'}};
 s.freezePanes.freezeRows(5);s.freezePanes.freezeColumns(1);
 return s;
}
function table(s,headers,rows,name,start=5){
 const last=col(headers.length-1),end=start+Math.max(1,rows.length);
 s.getRange(`A${start}:${last}${end}`).values=[headers,...(rows.length?rows.map(r=>r.map(safe)):[headers.map(()=>null)])];
 const t=s.tables.add(`A${start}:${last}${end}`,true,name);t.style='TableStyleMedium2';t.showFilterButton=true;
 s.getRange(`A${start}:${last}${start}`).format={fill:navy,font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:36};
 s.getRange(`A${start+1}:${last}${end}`).format.wrapText=true;
 s.getRange(`A${start+1}:${last}${end}`).format.fill='#FFFFFF';
 for(let n=start+1;n<=end;n+=2)s.getRange(`A${n}:${last}${n}`).format.fill=pale;
 return {start:start+1,end};
}
function fmt(s,column,range,format){s.getRange(`${column}${range.start}:${column}${range.end}`).setNumberFormat(format);}
function statusColor(s,column,range){
 const r=s.getRange(`${column}${range.start}:${column}${range.end}`);
 r.conditionalFormats.add('containsText',{text:'concluída',format:{fill:'#E6F1E9',font:{color:'#285C39'}}});
 for(const word of ['Falha','bloqueado','redirecionado'])r.conditionalFormats.add('containsText',{text:word,format:{fill:'#FCE7E6',font:{color:'#943A35'}}});
 for(const word of ['parcial','assistida','Referência','navegador'])r.conditionalFormats.add('containsText',{text:word,format:{fill:amber,font:{color:'#795C19'}}});
}
function discount(s,r,bid,valuation,target){
 s.getRange(`${target}${r.start}:${target}${r.end}`).formulas=Array.from({length:r.end-r.start+1},(_,i)=>{
  const n=r.start+i;return [`=IF(AND(ISNUMBER(${bid}${n}),ISNUMBER(${valuation}${n}),${valuation}${n}>0),1-${bid}${n}/${valuation}${n},"")`];
 });fmt(s,target,r,'0.0%');
}
const listings=[...data.listings].sort((a,b)=>(b.similarity||0)-(a.similarity||0)||text(a.data.city).localeCompare(text(b.data.city),'pt-BR'));
const code=r=>r.id.slice(0,8).toUpperCase();
if(new Set(listings.map(code)).size!==listings.length)throw Error('Identificadores curtos repetidos.');
const listingById=Object.fromEntries(listings.map(r=>[r.id,r]));
const stageRows=data.results.filter(r=>r.praca!=null).sort((a,b)=>text(a.data_praca||'9999').localeCompare(text(b.data_praca||'9999'))||a.anuncio_id.localeCompare(b.anuncio_id)||a.praca-b.praca);
const stageIndex=new Map();
const stageKey=r=>`${r.anuncio_id}|${r.leilao_id}|${r.praca}`;
const s=sheets['Praças'];
base('Praças','Praças e etapas','Uma linha por etapa. Datas e lances pertencem à mesma praça. Valores ausentes ficam vazios.',[12,43,23,8,21,20,20,14,22,22,24,23,25,32,50,28,26],stageRows.length+6);
const pr=table(s,['Código','Imóvel','Cidade / UF','Praça','Data da praça','Lance mínimo','Avaliação da fonte','Desconto calculado','Situação da data','Natureza da data','Situação da coleta','Critérios desta praça','Situação do anúncio','Origem do lance','Link do anúncio','Leilão na fonte','Início da etapa'],stageRows.map((r,i)=>{
 stageIndex.set(stageKey(r),i+6);
 return [code(listingById[r.anuncio_id]),r.titulo,[r.cidade,r.uf].filter(Boolean).join(' / '),r.praca,date(r.data_praca),r.lance_minimo,r.avaliacao_fonte,null,null,r.natureza_data,statusNames[r.situacao_coleta]||r.situacao_coleta,matchLabel(r.criterio_praca),r.situacao_anuncio,r.origem_lance,r.url,r.leilao_id,date(r.inicio_praca)];
}),'TabelaPracas');
fmt(s,'F',pr,currency);fmt(s,'G',pr,currency);fmt(s,'E',pr,datefmt);fmt(s,'Q',pr,datefmt);discount(s,pr,'F','G','H');statusColor(s,'K',pr);
stageRows.forEach((r,i)=>{if(r.data_praca&&!r.data_praca.includes('T'))s.getRange(`E${i+6}`).setNumberFormat(dayfmt);});
s.getRange(`I${pr.start}:I${pr.end}`).formulas=Array.from({length:pr.end-pr.start+1},(_,i)=>[`=IF(E${i+6}="","Não informada",IF(E${i+6}<'Guia'!$B$6,"Data passada","Hoje ou futura"))`]);
s.getRange(`A6:Q${pr.end}`).format.rowHeight=62;

const a=base('Anúncios','Anúncios acompanhados','Uma linha por anúncio. Use as setas dos cabeçalhos para filtrar cidade, fonte, coleta e critérios.',[12,47,24,16,24,21,20,14,22,25,29,24,50,24,18,30,20,20,27,26,50,50,50,44,24,24,26,27,30,44],listings.length+6);
const ar=table(a,['Código','Imóvel','Cidade / UF','Tipo','Situação da coleta','Próxima data conhecida','Lance dessa praça','Desconto dessa praça','Critérios do anúncio','Ocupação','Semelhança com a seleção','Fonte','Endereço','Situação do anúncio','Praça seguinte','Leiloeiro','Avaliação da fonte','Teto pessoal original','Última tentativa','Última leitura HTTP','Link do anúncio','Editais','Links do mesmo grupo','Observações da coleta','Origem dos dados','Grupo de imóvel','ID completo do anúncio','Última leitura assistida','Motivos dos critérios','Alertas do anúncio'],listings.map(r=>{
 const d=r.data,next=stageRows.find(x=>x.anuncio_id===r.id&&date(x.data_praca)>=today&&x.data_praca);
 const sr=next?stageIndex.get(stageKey(next)):null;
 r.nextRow=sr;
 return [code(r),d.title||'Anúncio sem dados interpretados',[d.city,d.uf].filter(Boolean).join(' / '),d.type,statusNames[r.collection_status]||r.collection_status,next?date(next.data_praca):null,next?.lance_minimo??null,null,matchLabel(r.match),d.occupancy,join(r.similar_reasons),sourceNames[r.source]||r.source,d.address,d.status,next?.praca??null,d.auctioneer,d.valuation,d.personal_ceiling,date(r.last_attempt),date(r.last_success),r.url,join(d.notice_links),join(r.group_links),r.detail,origins[d.origin]||d.origin,r.property_id,r.id,d.origin==='consulta_assistida'?date(d.checked_at):null,join(r.match_reasons),join(d.warnings)];
}),'TabelaAnuncios');
for(const c of ['G','Q','R'])fmt(a,c,ar,currency);
for(const c of ['F','S','T','AB'])fmt(a,c,ar,datefmt);
discount(a,ar,'G','Q','H');statusColor(a,'E',ar);a.getRange(`A6:AD${ar.end}`).format.rowHeight=70;
listings.forEach((r,i)=>{if(r.nextRow){a.getRange(`F${i+6}:G${i+6}`).formulas=[[`='Praças'!E${r.nextRow}`,`=IF(ISNUMBER('Praças'!F${r.nextRow}),'Praças'!F${r.nextRow},"")`]];const st=stageRows[r.nextRow-6];if(!st.data_praca.includes('T'))a.getRange(`F${i+6}`).setNumberFormat(dayfmt);}});

const areaRows=listings.flatMap(r=>(r.data.areas||[]).map(x=>[code(r),r.data.title,x.kind,x.m2,x.context,x.origin,r.url]));
const area=base('Áreas','Áreas informadas','Áreas privativas, totais, terrenos e garagens permanecem separadas. Confira o contexto do anúncio.',[12,47,19,17,78,23,50],areaRows.length+6);
const areaR=table(area,['Código','Imóvel','Tipo de área','Área (m²)','Contexto publicado','Origem','Link do anúncio'],areaRows,'TabelaAreas');fmt(area,'D',areaR,'#,##0.000');area.getRange(`A6:G${areaR.end}`).format.rowHeight=66;

const f=base('Fontes','Fontes e consultas','Falhas preservam o último dado armazenado. A cobertura é uma amostra dos catálogos.',[25,24,24,57,74,26,26],data.runs.length+20);
const fr=table(f,['Fonte','Método','Habilitada','Página inicial','Limitação conhecida','Última rodada','Resultado da rodada'],data.config.sources.map(src=>{
 const run=data.runs.find(r=>r.source===src.id);
 return [src.name,({browser:'Importação assistida',blocked:'Acesso bloqueado'})[src.adapter]||'Página pública',src.enabled?'Sim':'Não',src.root,src.note,date(run?.at),statusNames[run?.status]||run?.status||'Sem rodada'];
}),'TabelaFontes');fmt(f,'F',fr,datefmt);f.getRange(`A6:G${fr.end}`).format.rowHeight=76;
const runsStart=fr.end+4;f.getRange(`A${runsStart-1}`).values=[['Histórico de consultas']];
function runSummary(details){
 let v;try{v=JSON.parse(details);}catch{return details;}
 if(typeof v!=='object'||v===null)return text(v);
 return `Lidos: ${v.lidos??'não informado'}. Falhas: ${v.falhas??'não informado'}. Páginas: ${v.paginas_lidas??'não informado'}. Novos links: ${v.novos_links??'não informado'}.\nLimite atingido: ${v.limite_atingido?'sim':'não'}. Problemas registrados: ${(v.problemas||[]).length}.\nAmostra do catálogo. Detalhes em consultas.csv.`;
}
const rr=table(f,['Consulta em','Fonte','Resultado','Detalhes da cobertura'],data.runs.map(r=>[date(r.at),sourceNames[r.source]||r.source,statusNames[r.status]||r.status,runSummary(r.details)]),'TabelaConsultas',runsStart);fmt(f,'A',rr,datefmt);f.getRange(`A${rr.start}:D${rr.end}`).format.rowHeight=106;
f.getRange(`D${rr.start}:D${rr.end}`).format.wrapText=true;

const fieldNames={collection_status:'Situação da coleta',warnings:'Alertas',valuation:'Avaliação',title:'Título',status:'Situação do anúncio',stages:'Praças e datas',occupancy:'Ocupação',address:'Endereço',areas:'Áreas',auctioneer:'Leiloeiro',city:'Cidade',uf:'UF',type:'Tipo',notice_links:'Editais',registry:'Matrícula',registry_numbers:'Matrículas',registry_office:'Cartório',asset_scope:'Objeto da venda',description:'Descrição',initial_bid:'Lance inicial',auction_external_id:'Leilão na fonte'};
function historyValue(value,field){
 let x;try{x=JSON.parse(value);}catch{x=value;}
 if(x==null)return 'Não informado';
 if(field==='collection_status')return statusNames[x]||x;
 if(field==='stages'&&Array.isArray(x))return x.map(z=>`${z.number}ª praça: ${z.date||'data não informada'}; lance ${z.minimum_bid==null?'não informado':z.minimum_bid.toLocaleString('pt-BR',{style:'currency',currency:'BRL'})}`).join('\n');
 if(Array.isArray(x))x=x.map(z=>typeof z==='object'?JSON.stringify(z):z).join('\n');
 if(typeof x==='string'&&x.length>700)return x.slice(0,620)+'… [texto completo em alteracoes.csv]';
 return x;
}
const h=base('Alterações','Histórico de alterações','Valores anteriores e novos. Textos extensos são resumidos; a íntegra permanece em alteracoes.csv.',[23,23,50,68,68,50],data.history.length+16+data.duplicates.length);
const hr=table(h,['Registrado em','Campo alterado','Imóvel / anúncio','Valor anterior','Novo valor','Link do anúncio'],data.history.map(r=>[date(r.at),fieldNames[r.field]||r.field,listingById[r.listing_id]?.data.title||r.url,historyValue(r.old,r.field),historyValue(r.new,r.field),r.url]),'TabelaAlteracoes');fmt(h,'A',hr,datefmt);h.getRange(`A6:F${hr.end}`).format.rowHeight=150;
data.history.forEach((r,i)=>{
 if(['valuation','initial_bid','personal_ceiling','market_estimate'].includes(r.field))h.getRange(`D${i+6}:E${i+6}`).setNumberFormat(currency);
 const lines=v=>text(v).split('\n').reduce((n,t)=>n+Math.max(1,Math.ceil(t.length/70)),0);
 const height=Math.max(58,Math.min(190,18+16*Math.max(lines(historyValue(r.old,r.field)),lines(historyValue(r.new,r.field)))));
 h.getRange(`A${i+6}:F${i+6}`).format.rowHeight=height;
});
const dupeStart=hr.end+4;h.getRange(`A${dupeStart-1}`).values=[['Possíveis duplicados — exigem conferência']];
table(h,['Anúncio A','Anúncio B','Motivo'],data.duplicates.map(x=>[x.url_a,x.url_b,x.reason]),'TabelaDuplicados',dupeStart);
if(!data.duplicates.length)h.getRange(`A${dupeStart+2}`).values=[['Nenhum par sinalizado nesta exportação. A ausência de alerta não confirma unicidade.']];

const g=base('Guia','Como usar a planilha','Arquivo gerado pelo Radar de Leilões. A fonte dos valores permanece identificada em cada aba.',[36,98],42);
g.getRange('A5:B9').values=[['Gerada em',generated],['Data-base das datas futuras',today],['Última tentativa de consulta',date(listings.map(r=>r.last_attempt).filter(Boolean).sort().at(-1))],['Grupos registrados no banco',new Set(listings.map(r=>r.property_id).filter(Boolean)).size],['Atualização','Automática após cada consulta ou exportação do programa.']];
g.getRange('B5:B7').setNumberFormat(datefmt);g.getRange('B6').setNumberFormat(dayfmt);
const guide=[
 ['Abrir e filtrar','Comece no Painel. Em Anúncios e Praças, use as setas dos cabeçalhos para filtrar e ordenar. O Painel resume toda a base; filtros das outras abas não alteram seus totais.'],
 ['Atualizar a busca','Feche este arquivo no Excel e execute CONSULTAR.cmd. Ao terminar, abra a planilha novamente. A atualização depende do resultado de cada fonte.'],
 ['Atualizar só a planilha','ATUALIZAR-PLANILHA.cmd recria este arquivo usando o banco salvo, sem consultar a internet.'],
 ['Execução agendada','As consultas agendadas pelo programa também recriam a planilha. Configure a agenda conforme LEIA-ME.txt. Nenhuma agenda foi ativada nesta entrega.'],
 ['Arquivo aberto no Excel','Se o Excel impedir a gravação, o arquivo anterior é mantido. A pendência fica em situacao-planilha.json. Feche o arquivo e execute ATUALIZAR-PLANILHA.cmd.'],
 ['Edições neste arquivo','As abas são recriadas a cada atualização. Configure filtros no programa. Para guardar anotações pessoais, salve uma cópia separada.'],
 ['Dados extraídos','Avaliação, lance, ocupação, endereço, datas e situação refletem o que estava disponível na fonte. Células vazias significam informação ausente.'],
 ['Desconto calculado','Fórmula do Excel: 1 − lance mínimo ÷ avaliação. Só é calculado quando ambos os valores existem e a avaliação é positiva. Não usa o valor de mercado pessoal.'],
 ['Próxima data conhecida','Primeira etapa registrada com data igual ou posterior à data-base. Não confirma disponibilidade do lote. Para etapas posteriores e preços diferentes, consulte Praças.'],
 ['Horários','As datas mantêm o horário local informado, normalmente Brasília. Uma data sem horário é exibida sem hora. O Excel não armazena fuso; os dados JSON mantêm a informação original.'],
 ['Leitura concluída','Indica que o programa interpretou o anúncio. Não confirma que o leilão continua aberto. Consulte também Situação do anúncio e Última tentativa.'],
 ['Falha de consulta','Não significa ausência de imóveis. Última tentativa inclui falhas; Última leitura HTTP registra a consulta interpretada mais recente. Top e Krobel usam a data da leitura assistida.'],
 ['Semelhança','Cidade presente na seleção original, apartamento e referência a duplex/triplex são sugestões de ordenação. Essas características não são filtros obrigatórios.'],
 ['Identificadores','Código identifica o anúncio. Grupo de imóvel reúne vínculos reconhecidos pelo programa e pode requerer revisão. Praça é uma etapa de um leilão, não um imóvel novo.'],
 ['Proveniência','Site: extração HTTP. Texto do navegador: consulta assistida. Planilha original: referência ainda sem confirmação. Teto pessoal vem de Leilões.xlsx e permanece separado da avaliação.'],
 ['Fontes e áreas','As colunas de links permitem conferir a origem. Em Áreas, cada medida mantém o contexto, pois total e privativa não são equivalentes.']
];
table(g,['Assunto','Orientação'],guide,'TabelaGuia',12);g.getRange('A13:B28').format.rowHeight=58;
const filterLabels={cities:'Cidades',states:'UFs',types:'Tipos',min_price:'Lance mínimo',max_price:'Lance máximo',min_discount:'Desconto mínimo (%)',date_from:'Data inicial',date_to:'Data final',show_pending:'Exibir pendentes'};
table(g,['Filtro ativo no programa','Valor'],Object.entries(filterLabels).map(([key,label])=>[label,Array.isArray(data.config.filters[key])?data.config.filters[key].join('; ')||'Sem restrição':data.config.filters[key]==null?'Sem restrição':typeof data.config.filters[key]==='boolean'?(data.config.filters[key]?'Sim':'Não'):data.config.filters[key]]),'TabelaFiltros',31);

const p=base('Painel','Radar de Leilões','Base armazenada no programa. Consulte as datas de coleta antes de decidir quais anúncios acompanhar.',[44,24,12,23,21,17,26,23],36);
p.freezePanes.freezeRows(4);
p.getRange('A4').values=[['Atualização da planilha']];p.getRange('B4').values=[[generated]];p.getRange('B4').setNumberFormat(datefmt);
const ps=table(p,['Fonte','Anúncios','Leitura OK','Assistidos','Com pendência'],data.config.sources.map(src=>[src.name,null,null,null,null]),'ResumoFontes',6);
data.config.sources.forEach((src,i)=>{
 const n=i+7,criteria=src.name.replaceAll('"','""');
 p.getRange(`B${n}:E${n}`).formulas=[[
  `=COUNTIF('Anúncios'!$L$6:$L$${ar.end},"${criteria}")`,
  `=COUNTIFS('Anúncios'!$L$6:$L$${ar.end},"${criteria}",'Anúncios'!$E$6:$E$${ar.end},"Leitura concluída")`,
  `=COUNTIFS('Anúncios'!$L$6:$L$${ar.end},"${criteria}",'Anúncios'!$E$6:$E$${ar.end},"Consulta assistida")`,
  `=B${n}-C${n}-D${n}`]];
});
p.getRange('G6:H6').values=[['Base acompanhada','Quantidade']];p.getRange('G6:H6').format={fill:navy,font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:36};
p.getRange('G7:G11').values=[['Anúncios'],['Grupos registrados'],['Praças conhecidas'],['Datas hoje / futuras'],['Possíveis duplicados']];
p.getRange('H7:H11').formulas=[[`=COUNTA('Anúncios'!A6:A${ar.end})`],["='Guia'!B8"],[`=COUNT('Praças'!D6:D${pr.end})`],[`=COUNTIF('Praças'!I6:I${pr.end},"Hoje ou futura")`],[`=${data.duplicates.length}`]];
p.getRange('A14').values=[['Pendências incluem falhas, leituras parciais e links redirecionados. Os últimos dados são preservados.']];
p.getRange('A15').values=[['Próximas datas registradas — primeiras 14 etapas. A disponibilidade deve ser conferida no anúncio.']];p.getRange('A15').format.font={bold:true,color:navy,size:12};
const upcoming=stageRows.filter(r=>r.data_praca&&date(r.data_praca)>=today).slice(0,14);
const up=table(p,['Imóvel','Cidade / UF','Praça','Data registrada','Lance mínimo','Desconto','Fonte','Situação da coleta'],upcoming.map(()=>Array(8).fill(null)),'AgendaPracas',17);
upcoming.forEach((r,i)=>{
 const n=i+18,k=stageIndex.get(stageKey(r));
 p.getRange(`A${n}:F${n}`).formulas=[[`='Praças'!B${k}`,`='Praças'!C${k}`,`='Praças'!D${k}`,`='Praças'!E${k}`,`=IF(ISNUMBER('Praças'!F${k}),'Praças'!F${k},"")`,`=IF(ISNUMBER('Praças'!H${k}),'Praças'!H${k},"")`]];
 p.getRange(`G${n}:H${n}`).values=[[sourceNames[r.fonte]||r.fonte,statusNames[r.situacao_coleta]||r.situacao_coleta]];
});
fmt(p,'D',up,datefmt);fmt(p,'E',up,currency);fmt(p,'F',up,'0.0%');p.getRange(`A18:H${up.end}`).format.rowHeight=58;statusColor(p,'H',up);
upcoming.forEach((r,i)=>{if(!r.data_praca.includes('T'))p.getRange(`D${i+18}`).setNumberFormat(dayfmt);});
p.getRange(`A${up.end+2}`).values=[['Veja todos os registros em Anúncios e Praças. Filtros e instruções de atualização estão na aba Guia.']];

const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:4000});
if(/#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A|#NUM!|#NULL!|#SPILL!|#CALC!/.test(errors.ndjson||''))throw Error('Erro de fórmula: '+errors.ndjson);
if(previewDir){
 await fs.mkdir(previewDir,{recursive:true});
 await fs.writeFile(path.join(previewDir,'inspecao.json'),JSON.stringify({errors:errors.ndjson,panel:(await wb.inspect({kind:'region',sheetId:'Painel',range:'A6:H12',maxChars:5000,tableMaxCols:8,tableMaxRows:7})).ndjson},null,2));
 const previewRegions=process.env.RADAR_PREVIEW_ONLY?JSON.parse(process.env.RADAR_PREVIEW_ONLY):[['Painel','A1:H22'],['Anúncios','A1:J10'],['Praças','A1:L10'],['Áreas','A1:F10'],['Fontes','A1:G11'],['Alterações','A1:E10'],['Guia','A1:B17']];
 for(const [sheetName,range] of previewRegions){
  const png=await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(previewDir,`${sheetName}.png`),new Uint8Array(await png.arrayBuffer()));
 }
}
await fs.mkdir(path.dirname(output),{recursive:true});
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(output);
console.log(JSON.stringify({anuncios:listings.length,pracas:stageRows.length,arquivo:output}));
