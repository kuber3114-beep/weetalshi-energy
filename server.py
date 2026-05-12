from flask import Flask, request, jsonify, session, Response
import sqlite3
import hashlib
import os
import math
import re
from datetime import datetime
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = 'weetalshi_dev_secret_2024'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

DB_PATH = os.path.join(BASE_DIR, 'weetalshi.db')


# ── CORS ─────────────────────────────────────────────────────────────
@app.after_request
def add_cors(resp):
    origin = request.headers.get('Origin', '*')
    resp.headers['Access-Control-Allow-Origin'] = origin
    resp.headers['Access-Control-Allow-Credentials'] = 'true'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,PATCH,DELETE,OPTIONS'
    return resp

@app.route('/api/<path:p>', methods=['OPTIONS'])
def preflight(p):
    return jsonify({}), 200


# ── DATABASE ──────────────────────────────────────────────────────────
def get_db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def hp(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def a2d(row):
    d = dict(row)
    d['booster_active'] = bool(d.get('booster_active', 0))
    return d

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT
        );
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            mobile TEXT,
            aadhaar TEXT,
            pan TEXT,
            password TEXT NOT NULL,
            rank_id INTEGER DEFAULT 0,
            package_id TEXT DEFAULT 'starter',
            investment REAL DEFAULT 0,
            self_topup REAL DEFAULT 0,
            direct_business REAL DEFAULT 0,
            direct_recruits INTEGER DEFAULT 0,
            booster_active INTEGER DEFAULT 0,
            booster_months INTEGER DEFAULT 0,
            total_earnings REAL DEFAULT 0,
            monthly_earnings REAL DEFAULT 0,
            sponsor_id TEXT,
            status TEXT DEFAULT 'pending',
            join_date TEXT DEFAULT CURRENT_DATE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL DEFAULT 0,
            note TEXT,
            tx_date TEXT DEFAULT CURRENT_DATE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS downline (
            sponsor_id TEXT,
            agent_id TEXT,
            depth INTEGER DEFAULT 1,
            PRIMARY KEY(sponsor_id, agent_id)
        );
    """)

    if not conn.execute("SELECT id FROM admins WHERE username='admin'").fetchone():
        conn.execute("INSERT INTO admins(username,password) VALUES(?,?)", ('admin', hp('admin123')))

    demo_pw = hp('demo123')
    DEMO = [
        ('agent1','Rahul Sharma', 'rahul@demo.com', '9876543210','123456789012','ABCRS1234A',0,'starter',  50000,  50000,  30000, 1,0, 0,   9000,  3000,None,'approved','2025-01-15'),
        ('agent2','Priya Patel',  'priya@demo.com', '9876543211','234567890123','ABCPP1234B',1,'standard',200000,200000, 120000, 4,1,20,  85000, 14200,None,'approved','2024-10-05'),
        ('agent3','Arjun Singh',  'arjun@demo.com', '9876543212','345678901234','ABCAS1234C',2,'standard',400000,400000, 280000, 6,1,18, 320000, 38500,None,'approved','2024-07-20'),
        ('agent4','Meena Reddy',  'meena@demo.com', '9876543213','456789012345','ABCMR1234D',3,'premium',  800000,800000, 650000, 9,1,15,1200000, 98000,None,'approved','2024-04-10'),
        ('agent5','Vikram Nair',  'vikram@demo.com','9876543214','567890123456','ABCVN1234E',4,'premium', 1500000,1500000,1200000,15,1, 8,5800000,245000,None,'approved','2023-11-01'),
    ]
    for a in DEMO:
        if not conn.execute("SELECT id FROM agents WHERE id=?", (a[0],)).fetchone():
            conn.execute("""
                INSERT INTO agents(id,name,email,mobile,aadhaar,pan,rank_id,package_id,
                    investment,self_topup,direct_business,direct_recruits,booster_active,
                    booster_months,total_earnings,monthly_earnings,sponsor_id,status,join_date,password)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (*a, demo_pw))

    TXN = {
        'agent1':[('Dividend',3000,'Monthly dividend 6%','2025-05-01'),
                  ('Dividend',3000,'Monthly dividend 6%','2025-04-01'),
                  ('Dividend',3000,'Monthly dividend 6%','2025-03-01')],
        'agent2':[('Dividend',12000,'Monthly dividend 6%','2025-05-01'),
                  ('Booster',1800,'Booster 9%','2025-05-01'),
                  ('Leadership',400,'Leadership Level 1','2025-05-01')],
        'agent3':[('Dividend',24000,'Monthly dividend 6%','2025-05-01'),
                  ('Booster',3600,'Booster 9%','2025-05-01'),
                  ('TTO',8000,'2% Team Turnover','2025-05-01'),
                  ('Rank Bonus',2900,'Rank Level 8','2025-05-01')],
        'agent4':[('Dividend',48000,'Monthly dividend 6%','2025-05-01'),
                  ('TTO',21000,'3% TTO Diamond1','2025-05-01'),
                  ('Rank Bonus',16000,'Rank Level 10','2025-05-01'),
                  ('Leadership',13000,'Leadership Levels 1-10','2025-05-01')],
        'agent5':[('Dividend',90000,'Monthly dividend 6%','2025-05-01'),
                  ('CTO',60000,'1% Company Turnover','2025-05-01'),
                  ('Rank Bonus',52500,'Rank Level 12','2025-05-01'),
                  ('Leadership',42500,'Leadership all levels','2025-05-01')],
    }
    for aid, txlist in TXN.items():
        for t in txlist:
            if not conn.execute(
                "SELECT id FROM transactions WHERE agent_id=? AND type=? AND tx_date=?",
                (aid, t[0], t[3])
            ).fetchone():
                conn.execute(
                    "INSERT INTO transactions(agent_id,type,amount,note,tx_date) VALUES(?,?,?,?,?)",
                    (aid, t[0], t[1], t[2], t[3])
                )

    for sp, ag, d in [('agent2','agent1',1),('agent3','agent2',1),('agent4','agent3',1),('agent5','agent4',1)]:
        conn.execute("INSERT OR IGNORE INTO downline(sponsor_id,agent_id,depth) VALUES(?,?,?)", (sp, ag, d))

    conn.commit()
    conn.close()
    print("Database ready:", DB_PATH)


# ── COMPENSATION ──────────────────────────────────────────────────────
RANKS = [
    {'id':0,'name':'Starter',  'tto':0,'cto':0},
    {'id':1,'name':'Silver',   'tto':1,'cto':0},
    {'id':2,'name':'Gold',     'tto':2,'cto':0},
    {'id':3,'name':'Diamond 1','tto':3,'cto':0},
    {'id':4,'name':'Diamond 2','tto':0,'cto':1},
]
RBL = [
    {'minPV':1,      'pct':1.00},{'minPV':51,     'pct':2.00},
    {'minPV':151,    'pct':3.00},{'minPV':501,     'pct':3.25},
    {'minPV':1501,   'pct':3.50},{'minPV':4001,    'pct':3.75},
    {'minPV':10001,  'pct':4.00},{'minPV':25001,   'pct':4.25},
    {'minPV':75001,  'pct':4.50},{'minPV':175001,  'pct':4.75},
    {'minPV':400001, 'pct':5.00},{'minPV':1000001, 'pct':5.25},
]

def pv(amt):
    return math.floor(amt / 10000)

def get_rb(p):
    r = RBL[0]
    for l in RBL:
        if p >= l['minPV']:
            r = l
    return r

def calc_monthly(ag):
    inv    = ag['investment']
    r      = RANKS[min(ag['rank_id'], 4)]
    booster = bool(ag.get('booster_active', 0))
    return (
        round(inv * 0.06) +
        (round(inv * 0.09) if booster else 0) +
        round(inv * get_rb(pv(inv))['pct'] / 100) +
        (round(inv * 0.3 * r['tto'] / 100) if r['tto'] else 0) +
        (round(inv * 0.01) if ag['rank_id'] == 4 else 0)
    )

def refresh_sponsor_stats(conn, sponsor_id):
    row = conn.execute("""
        SELECT COUNT(*) as cnt, COALESCE(SUM(a.investment),0) as biz
        FROM agents a JOIN downline d ON d.agent_id=a.id
        WHERE d.sponsor_id=? AND d.depth=1 AND a.status='approved'
    """, (sponsor_id,)).fetchone()
    sponsor = conn.execute("SELECT * FROM agents WHERE id=?", (sponsor_id,)).fetchone()
    if not sponsor:
        return
    sp = dict(sponsor)
    sp['booster_active'] = bool(sp.get('booster_active', 0))
    monthly = calc_monthly(sp)
    conn.execute(
        "UPDATE agents SET direct_recruits=?,direct_business=?,monthly_earnings=? WHERE id=?",
        (row['cnt'], row['biz'], monthly, sponsor_id)
    )


# ── AUTH DECORATORS ───────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def dec(*a, **k):
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*a, **k)
    return dec

def admin_required(f):
    @wraps(f)
    def dec(*a, **k):
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin required'}), 403
        return f(*a, **k)
    return dec


# ── STATIC ────────────────────────────────────────────────────────────
@app.route('/')
def index():
    try:
        with open(os.path.join(BASE_DIR, 'index.html'), 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content, mimetype='text/html')
    except FileNotFoundError:
        return Response("index.html not found in: " + BASE_DIR, status=404)


# ── AUTH ──────────────────────────────────────────────────────────────
@app.route('/api/auth/login', methods=['POST'])
def login():
    d = request.get_json(silent=True) or {}
    if d.get('role') == 'admin':
        conn = get_db()
        adm  = conn.execute("SELECT * FROM admins WHERE username='admin'").fetchone()
        conn.close()
        if not adm or hp(str(d.get('password', ''))) != adm['password']:
            return jsonify({'error': 'Invalid admin password'}), 401
        session.clear()
        session['user_id'] = 'admin'
        session['role']    = 'admin'
        return jsonify({'role': 'admin', 'name': 'Admin User'})
    else:
        aid   = str(d.get('agent_id',  '') or '').strip()
        ident = str(d.get('identifier','') or '').strip()
        conn  = get_db()
        ag    = None
        if aid:
            ag = conn.execute(
                "SELECT * FROM agents WHERE id=? AND status='approved'", (aid,)
            ).fetchone()
        elif ident:
            ag = conn.execute(
                "SELECT * FROM agents WHERE (email=? OR mobile=?) AND status='approved'",
                (ident, ident)
            ).fetchone()
        conn.close()
        if not ag:
            return jsonify({'error': 'Agent not found or not approved'}), 401
        session.clear()
        session['user_id'] = ag['id']
        session['role']    = 'agent'
        return jsonify({'role': 'agent', 'agent': a2d(ag)})

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/auth/me')
@login_required
def me():
    if session.get('role') == 'admin':
        return jsonify({'role': 'admin', 'name': 'Admin User', 'id': 'admin'})
    conn = get_db()
    ag   = conn.execute("SELECT * FROM agents WHERE id=?", (session['user_id'],)).fetchone()
    conn.close()
    if not ag:
        session.clear()
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'role': 'agent', 'agent': a2d(ag)})


# ── REFERRAL VERIFY ───────────────────────────────────────────────────
@app.route('/api/referral/verify', methods=['POST'])
def verify_referral():
    d    = request.get_json(silent=True) or {}
    code = str(d.get('code', '') or '').strip()
    if not code:
        return jsonify({'valid': False})
    conn = get_db()
    row  = conn.execute(
        "SELECT id,name FROM agents WHERE mobile=? AND status='approved'", (code,)
    ).fetchone()
    conn.close()
    if row:
        return jsonify({'valid': True, 'sponsorName': row['name'], 'sponsorId': row['id']})
    return jsonify({'valid': False})


# ── REGISTER ──────────────────────────────────────────────────────────
@app.route('/api/agents/register', methods=['POST'])
def register():
    d = request.get_json(silent=True) or {}

    name     = str(d.get('name')        or '').strip()
    mobile   = str(d.get('mobile')      or '').strip()
    email    = str(d.get('email')       or '').strip().lower()
    aadhaar  = str(d.get('aadhaar')     or '').strip() or None
    pan      = str(d.get('pan')         or '').strip().upper() or None
    referral = str(d.get('referralCode')or '').strip() or None
    password = str(d.get('password')    or '')

    if not name:
        return jsonify({'error': 'Name required', 'field': 'name'}), 400
    if not re.match(r'^\d{10}$', mobile):
        return jsonify({'error': 'Valid 10-digit mobile required', 'field': 'mobile'}), 400
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        return jsonify({'error': 'Valid email required', 'field': 'email'}), 400
    if aadhaar and not re.match(r'^\d{12}$', aadhaar):
        return jsonify({'error': 'Aadhaar must be 12 digits', 'field': 'aadhaar'}), 400
    if pan and not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan):
        return jsonify({'error': 'PAN format: ABCDE1234F', 'field': 'pan'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Min 6 characters', 'field': 'password'}), 400

    conn = get_db()
    try:
        if conn.execute("SELECT id FROM agents WHERE mobile=?", (mobile,)).fetchone():
            return jsonify({'error': 'Mobile already registered', 'field': 'mobile'}), 409
        if conn.execute("SELECT id FROM agents WHERE email=?", (email,)).fetchone():
            return jsonify({'error': 'Email already registered', 'field': 'email'}), 409
        if aadhaar and conn.execute("SELECT id FROM agents WHERE aadhaar=?", (aadhaar,)).fetchone():
            return jsonify({'error': 'Aadhaar already registered', 'field': 'aadhaar'}), 409
        if pan and conn.execute("SELECT id FROM agents WHERE pan=?", (pan,)).fetchone():
            return jsonify({'error': 'PAN already registered', 'field': 'pan'}), 409

        sponsor_id   = None
        sponsor_name = None
        if referral:
            sponsor_row = conn.execute(
                "SELECT id,name FROM agents WHERE mobile=? AND status='approved'", (referral,)
            ).fetchone()
            if not sponsor_row:
                return jsonify({
                    'error': 'Referral code not found. Please check the mobile number.',
                    'field': 'referralCode'
                }), 400
            sponsor_id   = sponsor_row['id']
            sponsor_name = sponsor_row['name']

        aid = 'agent_' + datetime.now().strftime('%Y%m%d%H%M%S%f')
        conn.execute(
            "INSERT INTO agents(id,name,email,mobile,aadhaar,pan,password,sponsor_id,status) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (aid, name, email, mobile, aadhaar, pan, hp(password), sponsor_id, 'pending')
        )
        conn.commit()
        return jsonify({'ok': True, 'sponsorName': sponsor_name})

    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ── AGENT ROUTES ──────────────────────────────────────────────────────
@app.route('/api/agents/me')
@login_required
def my_data():
    if session.get('role') == 'admin':
        return jsonify({'error': 'Admin cannot use agent route'}), 403
    conn = get_db()
    ag   = conn.execute("SELECT * FROM agents WHERE id=?", (session['user_id'],)).fetchone()
    txns = conn.execute(
        "SELECT * FROM transactions WHERE agent_id=? ORDER BY tx_date DESC,id DESC LIMIT 50",
        (session['user_id'],)
    ).fetchall()
    dl   = conn.execute(
        "SELECT a.* FROM agents a JOIN downline d ON d.agent_id=a.id "
        "WHERE d.sponsor_id=? AND d.depth=1 AND a.status='approved'",
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify({
        'agent':        a2d(ag),
        'transactions': [dict(t) for t in txns],
        'downline':     [a2d(x) for x in dl],
    })

@app.route('/api/agents/me', methods=['PATCH'])
@login_required
def update_me():
    if session.get('role') == 'admin':
        return jsonify({'error': 'Admin cannot use agent route'}), 403
    d      = request.get_json(silent=True) or {}
    name   = str(d.get('name',  '') or '').strip()
    email  = str(d.get('email', '') or '').strip().lower()
    mobile = str(d.get('mobile','') or '').strip() or None
    if not name or not email:
        return jsonify({'error': 'Name and email required'}), 400
    conn = get_db()
    try:
        if mobile:
            conn.execute("UPDATE agents SET name=?,email=?,mobile=? WHERE id=?",
                         (name, email, mobile, session['user_id']))
        else:
            conn.execute("UPDATE agents SET name=?,email=? WHERE id=?",
                         (name, email, session['user_id']))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/agents/me/promote', methods=['POST'])
@login_required
def promote_self():
    conn = get_db()
    ag   = dict(conn.execute("SELECT * FROM agents WHERE id=?", (session['user_id'],)).fetchone())
    if ag['rank_id'] >= 4:
        conn.close()
        return jsonify({'error': 'Already at max rank'}), 400
    if ag['self_topup'] < 100000 or ag['direct_business'] < 100000:
        conn.close()
        return jsonify({'error': 'Eligibility not met'}), 400
    nr = ag['rank_id'] + 1
    conn.execute("UPDATE agents SET rank_id=? WHERE id=?", (nr, session['user_id']))
    conn.execute("INSERT INTO transactions(agent_id,type,amount,note) VALUES(?,?,?,?)",
                 (session['user_id'], 'Bonus', 0, f'Promoted to {RANKS[nr]["name"]}'))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'new_rank': nr})


# ── ADMIN ROUTES ──────────────────────────────────────────────────────
@app.route('/api/admin/agents')
@login_required
@admin_required
def list_agents():
    status = request.args.get('status', 'approved')
    conn   = get_db()
    ags    = conn.execute(
        "SELECT * FROM agents WHERE status=? ORDER BY created_at DESC", (status,)
    ).fetchall()
    conn.close()
    return jsonify([a2d(a) for a in ags])

@app.route('/api/admin/agents/pending')
@login_required
@admin_required
def pending_agents():
    conn = get_db()
    ags  = conn.execute(
        "SELECT * FROM agents WHERE status='pending' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify([a2d(a) for a in ags])

@app.route('/api/admin/agents/<aid>/approve', methods=['POST'])
@login_required
@admin_required
def approve(aid):
    conn = get_db()
    ag   = conn.execute("SELECT * FROM agents WHERE id=?", (aid,)).fetchone()
    if not ag:
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    conn.execute("UPDATE agents SET status='approved' WHERE id=?", (aid,))
    if ag['sponsor_id']:
        conn.execute(
            "INSERT OR IGNORE INTO downline(sponsor_id,agent_id,depth) VALUES(?,?,1)",
            (ag['sponsor_id'], aid)
        )
        refresh_sponsor_stats(conn, ag['sponsor_id'])
        conn.execute(
            "INSERT INTO transactions(agent_id,type,amount,note,tx_date) VALUES(?,?,?,?,?)",
            (ag['sponsor_id'], 'Bonus', 0,
             f"New recruit joined: {ag['name']}",
             datetime.now().strftime('%Y-%m-%d'))
        )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/agents/<aid>/reject', methods=['POST'])
@login_required
@admin_required
def reject(aid):
    conn = get_db()
    conn.execute("UPDATE agents SET status='rejected' WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/agents', methods=['POST'])
@login_required
@admin_required
def add_agent():
    d       = request.get_json(silent=True) or {}
    name    = str(d.get('name',      '') or '').strip()
    email   = str(d.get('email',     '') or '').strip().lower()
    mobile  = str(d.get('mobile',    '') or '').strip() or None
    aadhaar = str(d.get('aadhaar',   '') or '').strip() or None
    pan     = str(d.get('pan',       '') or '').strip().upper() or None
    pkg     = str(d.get('packageId', '') or 'starter')
    sponsor = str(d.get('sponsorId', '') or '').strip() or None
    invest  = float(d.get('investment') or 10000)
    if not name or not email:
        return jsonify({'error': 'Name and email required'}), 400
    aid     = 'agent_' + datetime.now().strftime('%Y%m%d%H%M%S%f')
    monthly = round(invest * 0.06)
    conn    = get_db()
    try:
        conn.execute(
            "INSERT INTO agents(id,name,email,mobile,aadhaar,pan,password,package_id,"
            "investment,self_topup,monthly_earnings,sponsor_id,status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'approved')",
            (aid, name, email, mobile, aadhaar, pan, hp('temp123'),
             pkg, invest, invest, monthly, sponsor)
        )
        if sponsor:
            conn.execute(
                "INSERT OR IGNORE INTO downline(sponsor_id,agent_id,depth) VALUES(?,?,1)",
                (sponsor, aid)
            )
            refresh_sponsor_stats(conn, sponsor)
        conn.execute(
            "INSERT INTO transactions(agent_id,type,amount,note) VALUES(?,?,?,?)",
            (aid, 'Dividend', monthly, 'First month dividend')
        )
        conn.commit()
        return jsonify({'ok': True, 'id': aid})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/agents/<aid>', methods=['PATCH'])
@login_required
@admin_required
def edit_agent(aid):
    d    = request.get_json(silent=True) or {}
    conn = get_db()
    ag   = conn.execute("SELECT * FROM agents WHERE id=?", (aid,)).fetchone()
    if not ag:
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    invest = float(d.get('investment',     ag['investment']))
    pkg    = str(d.get('packageId',        ag['package_id']))
    rank   = int(d.get('rankId',           ag['rank_id']))
    rec    = int(d.get('directRecruits',   ag['direct_recruits']))
    topup  = float(d.get('selfTopup',      ag['self_topup']))
    biz    = float(d.get('directBusiness', ag['direct_business']))
    boo    = 1 if d.get('boosterActive') else 0
    bmth   = int(d.get('boosterMonths',    ag['booster_months']))
    note   = str(d.get('txNote', '') or '').strip()
    mo     = calc_monthly({'investment': invest, 'rank_id': rank,
                           'booster_active': boo, 'booster_months': bmth})
    try:
        conn.execute(
            "UPDATE agents SET investment=?,package_id=?,rank_id=?,direct_recruits=?,"
            "self_topup=?,direct_business=?,booster_active=?,booster_months=?,monthly_earnings=? WHERE id=?",
            (invest, pkg, rank, rec, topup, biz, boo, bmth, mo, aid)
        )
        if note:
            conn.execute(
                "INSERT INTO transactions(agent_id,type,amount,note) VALUES(?,?,?,?)",
                (aid, 'Bonus', 0, note)
            )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/agents/<aid>/promote', methods=['POST'])
@login_required
@admin_required
def admin_promote(aid):
    d    = request.get_json(silent=True) or {}
    nr   = int(d.get('rankId', 0))
    if not 0 <= nr <= 4:
        return jsonify({'error': 'Invalid rank'}), 400
    conn = get_db()
    ag   = conn.execute("SELECT * FROM agents WHERE id=?", (aid,)).fetchone()
    if not ag:
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    conn.execute("UPDATE agents SET rank_id=? WHERE id=?", (nr, aid))
    conn.execute(
        "INSERT INTO transactions(agent_id,type,amount,note) VALUES(?,?,?,?)",
        (aid, 'Bonus', 0, f'Promoted to {RANKS[nr]["name"]}')
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/agents/<aid>/transactions')
@login_required
@admin_required
def agent_txns(aid):
    conn = get_db()
    txns = conn.execute(
        "SELECT * FROM transactions WHERE agent_id=? ORDER BY tx_date DESC LIMIT 100", (aid,)
    ).fetchall()
    conn.close()
    return jsonify([dict(t) for t in txns])

@app.route('/api/admin/agents/<aid>/downline')
@login_required
@admin_required
def agent_dl(aid):
    conn = get_db()
    dl   = conn.execute(
        "SELECT a.* FROM agents a JOIN downline d ON d.agent_id=a.id "
        "WHERE d.sponsor_id=? AND d.depth=1", (aid,)
    ).fetchall()
    conn.close()
    return jsonify([a2d(x) for x in dl])

@app.route('/api/admin/stats')
@login_required
@admin_required
def stats():
    conn = get_db()
    ags  = [a2d(a) for a in conn.execute("SELECT * FROM agents WHERE status='approved'").fetchall()]
    pc   = conn.execute("SELECT COUNT(*) FROM agents WHERE status='pending'").fetchone()[0]
    conn.close()
    ti   = sum(a['investment'] for a in ags)
    rc   = {}
    for a in ags:
        rc[a['rank_id']] = rc.get(a['rank_id'], 0) + 1
    bp = {}
    for a in ags:
        p = a['package_id']
        if p not in bp:
            bp[p] = {'count': 0, 'investment': 0}
        bp[p]['count']      += 1
        bp[p]['investment'] += a['investment']
    return jsonify({
        'total_agents':     len(ags),
        'pending_count':    pc,
        'total_investment': ti,
        'total_monthly':    sum(a['monthly_earnings'] for a in ags),
        'total_pv':         sum(pv(a['investment']) for a in ags),
        'rank_counts':      rc,
        'by_package':       bp,
        'top_investors':    sorted(ags, key=lambda x: x['investment'], reverse=True)[:5],
        'monthly_breakdown': {
            'dividend':   sum(round(a['investment'] * 0.06) for a in ags),
            'booster':    sum(round(a['investment'] * 0.09) for a in ags if a['booster_active']),
            'rank_bonus': sum(round(a['investment'] * get_rb(pv(a['investment']))['pct'] / 100) for a in ags),
        },
    })

@app.route('/api/admin/commissions')
@login_required
@admin_required
def commissions():
    conn   = get_db()
    ags    = [a2d(a) for a in conn.execute("SELECT * FROM agents WHERE status='approved'").fetchall()]
    conn.close()
    result = []
    for ag in ags:
        inv = ag['investment']
        r   = RANKS[min(ag['rank_id'], 4)]
        div = round(inv * 0.06)
        boo = round(inv * 0.09) if ag['booster_active'] else 0
        rkb = round(inv * get_rb(pv(inv))['pct'] / 100)
        tto = round(inv * 0.3 * r['tto'] / 100) if r['tto'] else 0
        cto = round(inv * 0.01) if ag['rank_id'] == 4 else 0
        result.append({**ag, 'breakdown': {
            'dividend': div, 'booster': boo, 'rank_bonus': rkb,
            'tto_cto': tto + cto, 'total': div + boo + rkb + tto + cto
        }})
    return jsonify(sorted(result, key=lambda x: x['breakdown']['total'], reverse=True))

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '2.0.0'})


# ── RUN ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🌿 WEETALSHI on http://localhost:{port}")
    print("🔑 Admin: admin123")
    print("👤 Demo: agent1 to agent5\n")
    app.run(debug=True, host='0.0.0.0', port=port)