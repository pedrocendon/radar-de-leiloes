"""Persistent discovery ledger and Windows notification outbox, backed by the user database."""
import json
import re
import time
from datetime import date
from engine import dump, evaluate
from collectors import norm, now


def has_filters(filters):
    return any(v not in (None, '', []) for k, v in filters.items() if k != 'show_pending')


class Notifications:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS notification_settings(id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL, filters TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS notification_seen_listings(id TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS notification_seen_properties(id TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS notification_events(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                    kind TEXT NOT NULL, data TEXT NOT NULL, dispatched INTEGER NOT NULL DEFAULT 0);
            ''')
            # Migrate quietly: saved listings never become a backlog of "new" properties.
            if not db.execute('SELECT 1 FROM notification_settings WHERE id=1').fetchone():
                db.execute("INSERT INTO notification_settings VALUES(1,1,'')")
                self._baseline(db)

    def _baseline(self, db):
        db.execute('INSERT OR IGNORE INTO notification_seen_listings SELECT id FROM listings')
        db.execute('INSERT OR IGNORE INTO notification_seen_properties SELECT property_id FROM listings')
        db.execute('UPDATE notification_events SET dispatched=1 WHERE dispatched=0')

    def configure(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Escolha se deseja receber avisos de novos imóveis.')
        with self.store.connect() as db:
            db.execute('UPDATE notification_settings SET enabled=? WHERE id=1', (int(enabled),))
            self._baseline(db)

    def begin(self, config):
        signature = dump(dict(filters={k: sorted(v) if isinstance(v, list) else v
                          for k, v in config['filters'].items() if k != 'show_pending'},
                          sources=sorted(s['id'] for s in config['sources'] if s.get('enabled', True))))
        with self.store.connect() as db:
            previous = db.execute('SELECT filters FROM notification_settings WHERE id=1').fetchone()[0]
            if signature != previous:
                self._baseline(db)
                db.execute('UPDATE notification_settings SET filters=? WHERE id=1', (signature,))

    def capture(self, config):
        """Called after collection, before Excel export. Errors/stale data never qualify."""
        active = {s['id'] for s in config['sources'] if s.get('enabled', True)}
        rows = self.store.rows()
        grouped = {}
        with self.store.connect() as db:
            enabled = bool(db.execute('SELECT enabled FROM notification_settings WHERE id=1').fetchone()[0])
            if not enabled or not has_filters(config['filters']):
                self._baseline(db)
                return 0
            seen_lids = {r[0] for r in db.execute('SELECT id FROM notification_seen_listings')}
            seen_pids = {r[0] for r in db.execute('SELECT id FROM notification_seen_properties')}
            seen_pids.update(r['property_id'] for r in rows if r['id'] in seen_lids)
            for row in rows:
                lid, pid, data = row['id'], row['property_id'], row['data']
                if lid in seen_lids or pid in seen_pids:
                    # Remember a richer identity discovered later for an already known listing.
                    db.execute('INSERT OR IGNORE INTO notification_seen_properties VALUES(?)', (pid,))
                    db.execute('INSERT OR IGNORE INTO notification_seen_listings VALUES(?)', (lid,))
                    continue
                if row['source'] not in active or row['collection_status'] not in ('ok', 'parcial') or data.get('origin') != 'site':
                    continue
                stages = data.get('stages') or []
                upcoming = [s for s in stages if not s.get('date') or s['date'][:10] >= date.today().isoformat()]
                result, reasons = evaluate(dict(data, stages=upcoming), config['filters'])
                if stages and not upcoming:
                    result = 'fora'
                if result == 'pendente':
                    continue  # Wait for sufficient details, rather than alert on guessed matches.
                db.execute('INSERT OR IGNORE INTO notification_seen_listings VALUES(?)', (lid,))
                db.execute('INSERT OR IGNORE INTO notification_seen_properties VALUES(?)', (pid,))
                if result != 'corresponde':
                    continue
                status = norm(data.get('status') or '')
                if re.search(r'\b(inativo|encerrad\w*|arrematad\w*|cancelad\w*|suspens\w*|vendid\w*|retirad\w*)\b', status):
                    continue
                item = grouped.setdefault(pid, dict(property_id=pid, title=data.get('title') or 'Imóvel sem título',
                    city=data.get('city'), uf=data.get('uf'), listings=[], reasons=reasons))
                item['listings'].append(dict(id=lid, url=row['url'], source=row['source']))
            if grouped:
                db.execute('INSERT INTO notification_events(at,kind,data) VALUES(?,?,?)',
                           (now(), 'properties', dump(dict(items=list(grouped.values()), filters=config['filters']))))
            return len(grouped)

    def state(self, supported=False):
        with self.store.connect() as db:
            enabled = bool(db.execute('SELECT enabled FROM notification_settings WHERE id=1').fetchone()[0])
            events = [dict(id=r['id'], at=r['at'], **json.loads(r['data'])) for r in db.execute(
                "SELECT * FROM notification_events WHERE kind='properties' ORDER BY id DESC LIMIT 50")]
            pending = db.execute('SELECT COUNT(*) FROM notification_events WHERE dispatched=0').fetchone()[0]
            return dict(enabled=enabled, supported=supported, events=events, pending=pending)

    def pending(self):
        with self.store.connect() as db:
            return bool(db.execute('SELECT enabled AND EXISTS(SELECT 1 FROM notification_events WHERE dispatched=0) FROM notification_settings WHERE id=1').fetchone()[0])

    def test(self):
        with self.store.connect() as db:
            if not db.execute('SELECT enabled FROM notification_settings WHERE id=1').fetchone()[0]:
                raise ValueError('Ative os avisos antes de enviar um teste.')
            recent = db.execute("SELECT at FROM notification_events WHERE kind='test' ORDER BY id DESC LIMIT 1").fetchone()
            if recent and time.time() - float(recent[0]) < 60:
                raise ValueError('Aguarde um minuto antes de testar novamente.')
            db.execute("INSERT INTO notification_events(at,kind,data) VALUES(?,'test','{}')", (str(time.time()),))

    def claim(self):
        # Consume atomically before handing off: no duplicate popup after a tray restart.
        # History survives a crash or Windows suppressing the banner; display is not guaranteed.
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT enabled FROM notification_settings WHERE id=1').fetchone()[0]:
                return None
            rows = db.execute('SELECT * FROM notification_events WHERE dispatched=0 ORDER BY id LIMIT 20').fetchall()
            if not rows:
                return None
            properties = [r for r in rows if r['kind'] == 'properties']
            selected = properties or rows[:1]
            for row in selected:
                db.execute('UPDATE notification_events SET dispatched=1 WHERE id=?', (row['id'],))
            if not properties:
                return dict(title='Teste de aviso do Radar', text='Os avisos do Radar chegam por aqui, mesmo com a janela fechada. Clique para abrir o programa.')
            count = sum(len(json.loads(r['data'])['items']) for r in properties)
            return dict(title='Radar: novos imóveis encontrados',
                        text=(f'{count} novo imóvel atende' if count == 1 else f'{count} novos imóveis atendem') +
                             ' aos filtros da sua busca. Abra o Radar e consulte Novos imóveis para ver os detalhes.')
