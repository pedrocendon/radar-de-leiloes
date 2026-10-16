"""Favorite price comparisons and due-date reminders, independent of search filters."""
import json
import math
import re
from datetime import date, datetime, timedelta
from collectors import norm, now, TZ
from engine import dump


def clock():
    return datetime.now(TZ)


def active(row):
    return (row['collection_status'] in ('ok', 'parcial') and row['data'].get('origin') == 'site'
            and not re.search(r'\b(inativ\w*|encerrad\w*|arrematad\w*|cancelad\w*|suspens\w*|vendid\w*|retirad\w*)\b', norm(row['data'].get('status'))))


def stage_date(stage):
    value = stage.get('date')
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value) if len(value) > 10 else date.fromisoformat(value)
        if isinstance(parsed, datetime):
            return parsed.replace(tzinfo=TZ) if parsed.tzinfo is None else parsed.astimezone(TZ)
        return parsed
    except ValueError:
        return None


def upcoming(stage, current):
    parsed = stage_date(stage)
    if parsed is None:
        return not stage.get('date')
    return parsed >= current if isinstance(parsed, datetime) else parsed >= current.date()


def stage_key(data, stage):
    # A changed date/event starts a new comparison, rather than guessing auction identity.
    if stage.get('number') is None or (not data.get('auction_external_id') and not stage.get('date')):
        return None
    return dump([data.get('auction_external_id'), stage['number'], stage.get('date')])


def price(value):
    return round(value, 2) if type(value) in (int, float) and math.isfinite(value) and value > 0 else None


def reais(value):
    return 'R$ ' + f'{value:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


class FavoriteNotifications:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS favorite_notice_settings(id INTEGER PRIMARY KEY, price INTEGER NOT NULL, dates INTEGER NOT NULL, days INTEGER NOT NULL);
                INSERT OR IGNORE INTO favorite_notice_settings(id,price,dates,days) VALUES(1,1,1,3);
                CREATE TABLE IF NOT EXISTS favorite_price_baselines(listing TEXT, stage TEXT, value REAL, PRIMARY KEY(listing,stage));
                CREATE TABLE IF NOT EXISTS favorite_date_notices(property TEXT, stage TEXT, PRIMARY KEY(property,stage));
            ''')

            columns = {r['name'] for r in db.execute('PRAGMA table_info(favorite_notice_settings)')}
            for name in ('date_changes', 'status_changes'):
                if name not in columns:
                    db.execute(f'ALTER TABLE favorite_notice_settings ADD COLUMN {name} INTEGER NOT NULL DEFAULT 1')
        from favorite_changes import FavoriteChanges
        self.changes = FavoriteChanges(store)

    def settings(self):
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM favorite_notice_settings WHERE id=1').fetchone()
            return dict(price=bool(row['price']), dates=bool(row['dates']), days=row['days'], date_changes=bool(row['date_changes']), status_changes=bool(row['status_changes']))

    def sync(self, reset=False):
        """Baseline at migration/favoriting, never invent a historical price reduction."""
        self.changes.sync()
        with self.store.connect() as db:
            if reset:
                db.execute('DELETE FROM favorite_price_baselines')
            db.execute('DELETE FROM favorite_price_baselines WHERE listing NOT IN (SELECT listing_id FROM favorites)')
            for row in self.store.rows():
                if not row['favorited_at'] or not active(row):
                    continue
                for stage in row['data'].get('stages') or []:
                    key = stage_key(row['data'], stage)
                    if key is not None:
                        db.execute('INSERT OR IGNORE INTO favorite_price_baselines VALUES(?,?,?)',
                                   (row['id'], key, price(stage.get('minimum_bid'))))

    def configure(self, payload):
        previous = self.settings()
        payload = dict(previous, **payload)
        if (any(type(payload.get(k)) is not bool for k in ('date_changes','status_changes'))
                or type(payload.get('price')) is not bool or type(payload.get('dates')) is not bool
                or type(payload.get('days')) is not int or payload['days'] not in (1, 3, 7)):
            raise ValueError('Escolha os avisos dos favoritos e uma antecedência de 1, 3 ou 7 dias.')
        if previous['price'] != payload['price']:
            self.sync(reset=True)
        reset = []
        if previous['date_changes'] != payload['date_changes']:reset.append('dates')
        if previous['status_changes'] != payload['status_changes']:reset.extend(['status','raw_status'])
        if reset:self.changes.sync(reset=reset)
        with self.store.connect() as db:
            db.execute('UPDATE favorite_notice_settings SET price=?,dates=?,days=?,date_changes=?,status_changes=? WHERE id=1',
                       (int(payload['price']), int(payload['dates']), payload['days'], int(payload['date_changes']), int(payload['status_changes'])))
            for kind, enabled in [('favorite_price', payload['price']), ('favorite_date', payload['dates']), ('favorite_rescheduled', payload['date_changes']), ('favorite_status', payload['status_changes'])]:
                if not enabled:
                    db.execute('UPDATE notification_events SET dispatched=1 WHERE kind=?', (kind,))

    def capture(self, config, dates_only=False):
        changes = 0 if dates_only else self.changes.capture(config)
        current = clock()
        enabled_sources = {s['id'] for s in config['sources'] if s.get('enabled', True)}
        grouped = {'favorite_price': {}, 'favorite_date': {}}
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            settings = db.execute('SELECT * FROM favorite_notice_settings WHERE id=1').fetchone()
            for row in self.store.rows():
                if not row['favorited_at'] or not active(row):
                    continue
                data = row['data']
                stages = data.get('stages') or []
                keys = [stage_key(data, s) for s in stages]
                for stage, key in zip(stages, keys):
                    if key is None or keys.count(key) != 1:
                        continue  # Ambiguous stage identities cannot support a safe comparison.
                    value = price(stage.get('minimum_bid'))
                    previous = db.execute('SELECT value FROM favorite_price_baselines WHERE listing=? AND stage=?', (row['id'], key)).fetchone()
                    eligible = row['source'] in enabled_sources and upcoming(stage, current)
                    if not dates_only and value is not None:
                        if (settings['price'] and eligible and previous and previous['value'] is not None
                                and value < previous['value']):
                            self._item(grouped['favorite_price'], row, stage, previous=previous['value'], value=value)
                        db.execute('INSERT OR REPLACE INTO favorite_price_baselines VALUES(?,?,?)', (row['id'], key, value))
                    parsed = stage_date(stage)
                    if not settings['dates'] or not eligible or parsed is None:
                        continue
                    day = parsed.date() if isinstance(parsed, datetime) else parsed
                    days = (day - current.date()).days
                    try:
                        checked = datetime.fromisoformat(row['last_success']).astimezone(TZ)
                    except (TypeError, ValueError):
                        continue
                    if not (0 <= days <= settings['days'] and timedelta(0) <= current - checked <= timedelta(hours=48)):
                        continue
                    # Cross-source grouping uses confirmed property identity + stage/date.
                    reminder_key = dump([stage['number'], stage.get('date')])
                    sent = db.execute('SELECT 1 FROM favorite_date_notices WHERE property=? AND stage=?', (row['property_id'], reminder_key)).fetchone()
                    if not sent or (row['property_id'], reminder_key) in grouped['favorite_date']:
                        self._item(grouped['favorite_date'], row, stage, days=days, reminder_key=reminder_key)
                        db.execute('INSERT OR IGNORE INTO favorite_date_notices VALUES(?,?)', (row['property_id'], reminder_key))
            for kind, items in grouped.items():
                if items:
                    db.execute('INSERT INTO notification_events(at,kind,data) VALUES(?,?,?)',
                               (now(), kind, dump(dict(items=list(items.values())))))
        return changes + sum(len(items) for items in grouped.values())

    def _item(self, group, row, stage, previous=None, value=None, days=None, reminder_key=None):
        key = (row['property_id'], reminder_key) if reminder_key else (row['property_id'], stage['number'], stage.get('date'), previous, value)
        data = row['data']
        if previous is not None:
            reasons = [f"Lance da {stage['number']}ª etapa: de {reais(previous)} para {reais(value)}.",
                       f"Redução calculada: {reais(previous-value)} (" + f"{(1-value/previous)*100:.1f}".replace(".", ",") + "%)."]
        else:
            when = 'hoje' if days == 0 else 'amanhã' if days == 1 else f'em {days} dias'
            reasons = [f"A {stage['number']}ª etapa está prevista para {when}.",
                       'Lembrete baseado na última leitura do site. Confirme a data e a disponibilidade no anúncio.']
        item = group.setdefault(key, dict(property_id=row['property_id'], title=data.get('title') or 'Imóvel sem título',
            city=data.get('city'), uf=data.get('uf'), listings=[], reasons=reasons, stage=stage['number'],
            date=stage.get('date'), previous_price=previous, price=value, days=days, last_success=row['last_success']))
        item['listings'].append(dict(id=row['id'], url=row['url'], source=row['source']))

    def claim(self, config=None):
        change = self.changes.claim(config)
        if change:return change
        current = clock()
        rows_by_id = {r['id']: r for r in self.store.rows()}
        sources = None if config is None else {s['id'] for s in config['sources'] if s.get('enabled', True)}
        def relevant(item, kind):
            for listing in item['listings']:
                row = rows_by_id.get(listing['id'])
                if not row or not row['favorited_at'] or not active(row) or (sources is not None and row['source'] not in sources):
                    continue
                for stage in row['data'].get('stages') or []:
                    if stage.get('number') == item['stage'] and stage.get('date') == item['date'] and upcoming(stage, current):
                        if kind == 'favorite_date':
                            day = stage_date(stage)
                            if day is None:continue
                            day = day.date() if isinstance(day, datetime) else day
                            try:checked = datetime.fromisoformat(row['last_success']).astimezone(TZ)
                            except (ValueError, TypeError):continue
                            if not 0 <= (day-current.date()).days <= settings['days'] or current-checked > timedelta(hours=48):continue
                            return True
                        if price(stage.get('minimum_bid')) == item['price']:
                            return True
            return False
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            settings = db.execute('SELECT * FROM favorite_notice_settings WHERE id=1').fetchone()
            rows = db.execute("SELECT * FROM notification_events WHERE dispatched=0 AND kind IN ('favorite_price','favorite_date') ORDER BY id").fetchall()
            for event in rows:
                db.execute('UPDATE notification_events SET dispatched=1 WHERE id=?', (event['id'],))
                enabled = settings['price'] if event['kind'] == 'favorite_price' else settings['dates']
                items = [i for i in json.loads(event['data'])['items'] if relevant(i, event['kind'])]
                if not enabled or not items:
                    continue
                count = len(items)
                title = 'Radar: favorito baixou de preço' if event['kind'] == 'favorite_price' else 'Radar: leilão de favorito próximo'
                if count == 1:
                    reason = items[0]['reasons'][0]
                    if event['kind'] == 'favorite_date':
                        parsed = stage_date({'date': items[0]['date']})
                        day = parsed.date() if isinstance(parsed, datetime) else parsed
                        days = (day-current.date()).days
                        when = 'hoje' if days == 0 else 'amanhã' if days == 1 else f'em {days} dias'
                        reason = f"A {items[0]['stage']}ª etapa está prevista para {when}."
                    text = items[0]['title'][:80] + '. ' + reason
                else:
                    text = f'{count} etapas de favoritos ' + ('baixaram de preço.' if event['kind'] == 'favorite_price' else 'estão próximas da data do leilão.')
                return dict(title=title, text=text + ' Abra Avisos no Radar para conferir.')
        return None
