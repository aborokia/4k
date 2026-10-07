import os, sqlite3, secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '4k_store.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
ALLOWED = {'png','jpg','jpeg','webp','gif'}


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


def init_db():
    con = db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        price REAL NOT NULL,
        old_price REAL DEFAULT 0,
        category TEXT DEFAULT 'ألعاب',
        image TEXT DEFAULT 'logo.png',
        stock INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        customer_name TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        total REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'جديد',
        payment_method TEXT DEFAULT 'تحويل يدوي',
        payment_proof TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name TEXT NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
    );
    ''')
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@4kstore.local').strip().lower()
    admin_password = os.environ.get('ADMIN_PASSWORD', 'ChangeMe123!')
    admin = con.execute('SELECT id FROM users WHERE email=?', (admin_email,)).fetchone()
    if not admin:
        con.execute('INSERT INTO users(name,email,password_hash,is_admin) VALUES(?,?,?,1)',
                     ('4K Admin',admin_email,generate_password_hash(admin_password)))
    count = con.execute('SELECT COUNT(*) c FROM products').fetchone()['c']
    if count == 0:
        imgs = [
            'ea-sports-fc-26-xbox-one-xbox-series-x-s-microsoft-store-cover.jpg',
            'grand-theft-auto-vi-gta-6-videogame-2025-games-gaming-vice-city-jason-lucia-wallpaper-1920x1080-(1).jpg',
            'It-Takes-Two-cover-art.png',
            'Euro-Truck-Simulator-2-cover.jpg',
            'Boxshot-of-video-game-Project-zomboid.jpg',
            '10039316-rust-console-edition-playstation-4-front-cover.jpg'
        ]
        products = [
            ('EA SPORTS FC 26','نسخة رقمية جاهزة للتفعيل',129,159,'ألعاب',imgs[0],25),
            ('GTA VI','احصل على آخر أخبار وعروض اللعبة',249,299,'ألعاب',imgs[1],10),
            ('It Takes Two','لعبة تعاونية ممتعة لشخصين',89,119,'ألعاب',imgs[2],30),
            ('Euro Truck Simulator 2','محاكي الشاحنات الشهير',55,75,'ألعاب',imgs[3],40),
            ('Project Zomboid','بقاء وزومبي في عالم مفتوح',69,89,'ألعاب',imgs[4],22),
            ('Rust Console Edition','تجربة بقاء وتحديات أونلاين',99,129,'ألعاب',imgs[5],18),
        ]
        con.executemany('INSERT INTO products(name,description,price,old_price,category,image,stock) VALUES(?,?,?,?,?,?,?)', products)
    con.commit(); con.close()


def current_user():
    uid = session.get('user_id')
    if not uid: return None
    con = db(); user = con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); con.close()
    return user


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user['is_admin']:
            flash('يجب تسجيل الدخول كمسؤول للوصول إلى لوحة التحكم.', 'error')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    cart = session.get('cart', {})
    count = sum(int(v) for v in cart.values())
    return {'user': current_user(), 'cart_count': count, 'store_name': '4K STORE'}


@app.route('/')
def index():
    con=db(); products=con.execute('SELECT * FROM products WHERE active=1 ORDER BY id DESC').fetchall(); con.close()
    return render_template('index.html', products=products)

@app.route('/products')
def products():
    q=request.args.get('q','').strip(); cat=request.args.get('category','').strip()
    con=db(); sql='SELECT * FROM products WHERE active=1'; params=[]
    if q: sql+=' AND (name LIKE ? OR description LIKE ?)'; params += [f'%{q}%',f'%{q}%']
    if cat: sql+=' AND category=?'; params.append(cat)
    sql+=' ORDER BY id DESC'; rows=con.execute(sql,params).fetchall(); cats=con.execute('SELECT DISTINCT category FROM products WHERE active=1').fetchall(); con.close()
    return render_template('products.html', products=rows, categories=[x['category'] for x in cats], q=q, category=cat)

@app.route('/product/<int:pid>')
def product(pid):
    con=db(); p=con.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone(); con.close()
    if not p: abort(404)
    return render_template('product.html', product=p)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form['name'].strip(); email=request.form['email'].strip().lower(); password=request.form['password']
        if len(password)<8: flash('كلمة المرور يجب أن تكون 8 أحرف على الأقل.','error'); return render_template('auth/register.html')
        con=db()
        try:
            cur=con.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',(name,email,generate_password_hash(password)))
            con.commit(); session['user_id']=cur.lastrowid; flash('تم إنشاء حسابك بنجاح.','success'); return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            flash('البريد الإلكتروني مستخدم بالفعل.','error')
        finally: con.close()
    return render_template('auth/register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form['email'].strip().lower(); password=request.form['password']
        con=db(); u=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); con.close()
        if u and check_password_hash(u['password_hash'], password):
            session.clear(); session['user_id']=u['id']; flash('تم تسجيل الدخول.','success')
            return redirect(request.args.get('next') or (url_for('admin_dashboard') if u['is_admin'] else url_for('index')))
        flash('بيانات الدخول غير صحيحة.','error')
    return render_template('auth/login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('index'))

@app.post('/cart/add/<int:pid>')
def cart_add(pid):
    con=db(); p=con.execute('SELECT id,stock FROM products WHERE id=? AND active=1',(pid,)).fetchone(); con.close()
    if not p: return jsonify(ok=False,error='المنتج غير موجود'),404
    cart=session.get('cart',{}); key=str(pid); qty=int(cart.get(key,0))+1
    if qty>p['stock']: return jsonify(ok=False,error='الكمية المطلوبة غير متوفرة'),400
    cart[key]=qty; session['cart']=cart
    return jsonify(ok=True,count=sum(cart.values()))

@app.route('/cart')
def cart():
    cart=session.get('cart',{}); ids=[int(x) for x in cart]
    items=[]; total=0
    if ids:
        con=db(); marks=','.join('?'*len(ids)); rows=con.execute(f'SELECT * FROM products WHERE id IN ({marks})',ids).fetchall(); con.close()
        for p in rows:
            qty=int(cart.get(str(p['id']),0)); subtotal=p['price']*qty; total+=subtotal; items.append((p,qty,subtotal))
    return render_template('cart.html',items=items,total=total)

@app.post('/cart/update')
def cart_update():
    cart={}
    for k,v in request.form.items():
        if k.startswith('qty_'):
            pid=k[4:]
            try: q=max(0,int(v))
            except: q=0
            if q: cart[pid]=q
    session['cart']=cart; return redirect(url_for('cart'))

@app.post('/cart/clear')
def cart_clear(): session.pop('cart',None); return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET','POST'])
def checkout():
    if not current_user(): return redirect(url_for('login',next=url_for('checkout')))
    items,total=cart_items()
    if not items: return redirect(url_for('cart'))
    if request.method=='POST':
        payment=request.form.get('payment_method','تحويل يدوي')
        proof=''
        f=request.files.get('payment_proof')
        if f and f.filename:
            ext=f.filename.rsplit('.',1)[-1].lower()
            if ext not in ALLOWED: flash('نوع ملف الإثبات غير مسموح.','error'); return render_template('checkout.html',items=items,total=total)
            name=secure_filename(f.filename); proof=f'{secrets.token_hex(8)}_{name}'; f.save(os.path.join(UPLOAD_DIR,proof))
        u=current_user(); con=db(); cur=con.execute('INSERT INTO orders(user_id,customer_name,customer_email,total,payment_method,payment_proof) VALUES(?,?,?,?,?,?)',(u['id'],u['name'],u['email'],total,payment,proof))
        oid=cur.lastrowid
        for p,q,_ in items:
            con.execute('INSERT INTO order_items(order_id,product_id,product_name,price,quantity) VALUES(?,?,?,?,?)',(oid,p['id'],p['name'],p['price'],q))
            con.execute('UPDATE products SET stock=MAX(stock-?,0) WHERE id=?',(q,p['id']))
        con.commit(); con.close(); session.pop('cart',None); flash(f'تم إنشاء الطلب #{oid} بنجاح.','success'); return redirect(url_for('my_orders'))
    return render_template('checkout.html',items=items,total=total)

def cart_items():
    cart=session.get('cart',{}); ids=[int(x) for x in cart]; items=[]; total=0
    if ids:
        con=db(); marks=','.join('?'*len(ids)); rows=con.execute(f'SELECT * FROM products WHERE id IN ({marks})',ids).fetchall(); con.close()
        for p in rows:
            q=min(int(cart.get(str(p['id']),0)),p['stock']); subtotal=p['price']*q; total+=subtotal; items.append((p,q,subtotal))
    return items,total

@app.route('/orders')
def my_orders():
    if not current_user(): return redirect(url_for('login'))
    con=db(); orders=con.execute('SELECT * FROM orders WHERE user_id=? ORDER BY id DESC',(session['user_id'],)).fetchall(); con.close()
    return render_template('orders.html',orders=orders)

# Admin
@app.route('/admin')
@admin_required
def admin_dashboard():
    con=db(); stats={
        'users':con.execute('SELECT COUNT(*) c FROM users WHERE is_admin=0').fetchone()['c'],
        'products':con.execute('SELECT COUNT(*) c FROM products').fetchone()['c'],
        'orders':con.execute('SELECT COUNT(*) c FROM orders').fetchone()['c'],
        'sales':con.execute("SELECT COALESCE(SUM(total),0) s FROM orders WHERE status NOT IN ('ملغي')").fetchone()['s'],
    }; recent=con.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 8').fetchall(); con.close()
    return render_template('admin/dashboard.html',stats=stats,recent=recent)

@app.route('/admin/products', methods=['GET','POST'])
@admin_required
def admin_products():
    con=db()
    if request.method=='POST':
        name=request.form['name'].strip(); price=float(request.form['price']); old=float(request.form.get('old_price') or 0); stock=int(request.form.get('stock') or 0); cat=request.form.get('category','ألعاب'); desc=request.form.get('description',''); image=request.form.get('image','logo.png').strip()
        con.execute('INSERT INTO products(name,description,price,old_price,category,image,stock) VALUES(?,?,?,?,?,?,?)',(name,desc,price,old,cat,image,stock)); con.commit(); flash('تمت إضافة المنتج.','success')
    rows=con.execute('SELECT * FROM products ORDER BY id DESC').fetchall(); con.close(); return render_template('admin/products.html',products=rows)

@app.post('/admin/products/<int:pid>/delete')
@admin_required
def admin_product_delete(pid):
    con=db(); con.execute('DELETE FROM products WHERE id=?',(pid,)); con.commit(); con.close(); flash('تم حذف المنتج.','success'); return redirect(url_for('admin_products'))

@app.post('/admin/products/<int:pid>/toggle')
@admin_required
def admin_product_toggle(pid):
    con=db(); con.execute('UPDATE products SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(pid,)); con.commit(); con.close(); return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    con=db(); rows=con.execute('SELECT * FROM orders ORDER BY id DESC').fetchall(); con.close(); return render_template('admin/orders.html',orders=rows)

@app.post('/admin/orders/<int:oid>/status')
@admin_required
def admin_order_status(oid):
    status=request.form['status']; allowed={'جديد','قيد المراجعة','مدفوع','مكتمل','ملغي'}
    if status not in allowed: abort(400)
    con=db(); con.execute('UPDATE orders SET status=? WHERE id=?',(status,oid)); con.commit(); con.close(); flash('تم تحديث حالة الطلب.','success'); return redirect(url_for('admin_orders'))

@app.route('/admin/customers')
@admin_required
def admin_customers():
    con=db(); rows=con.execute('SELECT id,name,email,created_at FROM users WHERE is_admin=0 ORDER BY id DESC').fetchall(); con.close(); return render_template('admin/customers.html',customers=rows)

@app.route('/admin/settings')
@admin_required
def admin_settings(): return render_template('admin/settings.html')

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_DIR, filename)

@app.errorhandler(404)
def not_found(e): return render_template('404.html'),404

# Initialize the database when running with Gunicorn/Render as well as locally.
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)), debug=True)
