"""Confirmed rescheduling, suspension and cancellation of saved favorites."""
import json
import re
from datetime import datetime
from collectors import norm, now
from engine import dump
from favorite_notifications import stage_date, upcoming
import favorite_notifications


KINDS = {'favorite_rescheduled': 'date_changes', 'favorite_status': 'status_changes'}


def readable(row):
    return row['collection_status'] in ('ok', 'parcial') and row['data'].get('origin') == 'site'


def auction_id(data):
    value = data.get('auction_external_id')
    return None if value is None or norm(value) in ('', 'none', 'desconhecido') else str(value)


def situation(value):
    # A specific status field is evidence; prose mentioning possible cancellation is not.
    text = norm(value).strip(' .:!-')
    text = re.sub(r'^(?:(?:situacao|status)\s*:\s*)?(?:(?:leilao|lote|pregao)\s+(?:esta\s+)?)?', '', text)
    if text in ('suspenso', 'suspensa', 'suspensao'):return 'suspenso'
    if text in ('cancelado', 'cancelada', 'cancelamento'):return 'cancelado'
    if text in ('aberto', 'aberta', 'em andamento', 'em leilao', 'ativo', 'ativa', 'agendado', 'agendada', 'disponivel', 'retomado', 'retomada'):return 'ativo'
    if text in ('encerrado', 'encerrada', 'arrematado', 'arrematada', 'vendido', 'vendida', 'inativo', 'inativa'):return 'encerrado'
    return None


def different_date(old, new):
    left, right = stage_date({'date': old}), stage_date({'date': new})
    if left is None or right is None:return False
    # A newly supplied hour on the same day adds precision, not a confirmed rescheduling.
    if isinstance(left, datetime) and isinstance(right, datetime):return left != right
    return (left.date() if isinstance(left, datetime) else left) != (right.date() if isinstance(right, datetime) else right)


def date_label(value):
    parsed = stage_date({'date': value})
    if parsed is None:return 'não informada'
    return parsed.strftime('%d/%m/%Y às %H:%M' if isinstance(parsed, datetime) else '%d/%m/%Y')


def dates(data):
    stages = data.get('stages') or []
    numbers = [str(s.get('number')) for s in stages]
    return {str(s['number']): s['date'] for s in stages if s.get('number') is not None
            and numbers.count(str(s['number'])) == 1 and stage_date(s) is not None}


def snapshot(data):
    return dict(auction=auction_id(data), status=situation(data.get('status')), raw_status=data.get('status'), dates=dates(data))


class FavoriteChanges:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS favorite_change_baselines(listing TEXT PRIMARY KEY, data TEXT NOT NULL)')

    def sync(self, reset=()):
        with self.store.connect() as db:
            db.execute('DELETE FROM favorite_change_baselines WHERE listing NOT IN (SELECT listing_id FROM favorites)')
            for row in self.store.rows():
                if not row['favorited_at'] or not readable(row):continue
                data = snapshot(row['data'])
                existing = db.execute('SELECT data FROM favorite_change_baselines WHERE listing=?', (row['id'],)).fetchone()
                if not existing:
                    db.execute('INSERT INTO favorite_change_baselines VALUES(?,?)', (row['id'], dump(data)))
                elif reset:
                    old = json.loads(existing[0])
                    for field in reset:old[field] = data[field]
                    db.execute('UPDATE favorite_change_baselines SET data=? WHERE listing=?', (dump(old), row['id']))

    def capture(self, config):
        enabled = {s['id'] for s in config['sources'] if s.get('enabled', True)}
        groups = {kind: {} for kind in KINDS}
        current = favorite_notifications.clock()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            settings = db.execute('SELECT * FROM favorite_notice_settings WHERE id=1').fetchone()
            for row in self.store.rows():
                if not row['favorited_at'] or not readable(row):continue
                new = snapshot(row['data'])
                saved = db.execute('SELECT data FROM favorite_change_baselines WHERE listing=?', (row['id'],)).fetchone()
                old = json.loads(saved[0]) if saved else None
                if old and old['auction'] and new['auction'] is None:
                    continue  # Do not compare an unidentified event to a previously identified one.
                if old and old['auction'] == new['auction']:
                    if (settings['status_changes'] and row['source'] in enabled
                            and new['status'] in ('suspenso', 'cancelado') and new['status'] != old['status']):
                        self._item(groups['favorite_status'], row, None, old.get('raw_status'), new['raw_status'], new['status'])
                    for number, value in new['dates'].items():
                        previous = old['dates'].get(number)
                        if (settings['date_changes'] and row['source'] in enabled and different_date(previous, value)
                                and (upcoming({'date': previous}, current) or upcoming({'date': value}, current))):
                            self._item(groups['favorite_rescheduled'], row, number, previous, value)
                    # Missing values never reset a known date or status and create a false transition.
                    new['dates'] = dict(old['dates'], **new['dates'])
                    if new['status'] is None:
                        new['status'], new['raw_status'] = old['status'], old.get('raw_status')
                db.execute('INSERT OR REPLACE INTO favorite_change_baselines VALUES(?,?)', (row['id'], dump(new)))
            for kind, items in groups.items():
                if items:
                    db.execute('INSERT INTO notification_events(at,kind,data) VALUES(?,?,?)',
                               (now(), kind, dump(dict(items=list(items.values())))))
        return sum(len(items) for items in groups.values())

    def _item(self, group, row, number, previous, value, status=None):
        key = (row['property_id'], number, previous, value)
        data = row['data']
        if status:
            reasons = [f'O leilão deste favorito foi identificado como {status} na fonte.',
                       'Situação publicada: ' + str(value) + '.', 'Confira o comunicado e o edital no site.']
        else:
            reasons = [f'Data da {number}ª etapa alterada: de {date_label(previous)} para {date_label(value)}.',
                       'Confira a nova data e as condições no edital.']
        item = group.setdefault(key, dict(property_id=row['property_id'], title=data.get('title') or 'Imóvel sem título',
            city=data.get('city'), uf=data.get('uf'), stage=number, date=None if status else value,
            previous_date=None if status else previous, previous_status=previous if status else None,
            status=status, published_status=value if status else None, listings=[], reasons=reasons, last_success=row['last_success']))
        item['listings'].append(dict(id=row['id'], url=row['url'], source=row['source'], auction=auction_id(data)))

    def claim(self, config=None):
        rows = {r['id']: r for r in self.store.rows()}
        sources = None if config is None else {s['id'] for s in config['sources'] if s.get('enabled', True)}
        def relevant(item, kind):
            for listing in item['listings']:
                row = rows.get(listing['id'])
                if not row or not row['favorited_at'] or not readable(row):continue
                if sources is not None and row['source'] not in sources:continue
                if auction_id(row['data']) != listing['auction']:continue
                if kind == 'favorite_status':
                    if situation(row['data'].get('status')) == item['status']:return True
                else:
                    value = dates(row['data']).get(str(item['stage']))
                    if value and not different_date(value, item['date']):return True
            return False
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            settings = db.execute('SELECT * FROM favorite_notice_settings WHERE id=1').fetchone()
            events = db.execute("SELECT * FROM notification_events WHERE dispatched=0 AND kind IN ('favorite_rescheduled','favorite_status') ORDER BY CASE kind WHEN 'favorite_status' THEN 0 ELSE 1 END,id").fetchall()
            for event in events:
                db.execute('UPDATE notification_events SET dispatched=1 WHERE id=?', (event['id'],))
                if not settings[KINDS[event['kind']]]:continue
                items = [i for i in json.loads(event['data'])['items'] if relevant(i, event['kind'])]
                if not items:continue
                title = 'Radar: suspensão ou cancelamento' if event['kind'] == 'favorite_status' else 'Radar: data de favorito alterada'
                text = (items[0]['title'][:60] + '. ' + items[0]['reasons'][0]) if len(items) == 1 else f'{len(items)} alterações em leilões de favoritos. Confira as informações atualizadas.'
                return dict(title=title, text=text + ' Abra Avisos no Radar.')
        return None
