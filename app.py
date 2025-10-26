from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///oquv_markaz.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============= MODELS =============

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'mentor', 'talaba'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Talaba(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ism = db.Column(db.String(100), nullable=False)
    familiya = db.Column(db.String(100), nullable=False)
    telefon = db.Column(db.String(20))
    manzil = db.Column(db.String(200))
    tug_sana = db.Column(db.Date)
    guruh_id = db.Column(db.Integer, db.ForeignKey('guruh.id'))
    
    user = db.relationship('User', backref='talaba_profile')
    guruh = db.relationship('Guruh', backref='talabalar')

class Mentor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ism = db.Column(db.String(100), nullable=False)
    familiya = db.Column(db.String(100), nullable=False)
    telefon = db.Column(db.String(20))
    mutaxassislik = db.Column(db.String(100))
    tajriba_yili = db.Column(db.Integer)
    biografiya = db.Column(db.Text)
    
    user = db.relationship('User', backref='mentor_profile')
    guruhlar = db.relationship('Guruh', backref='mentor')

class Fan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nomi = db.Column(db.String(100), nullable=False)
    tavsif = db.Column(db.Text)
    davomiyligi = db.Column(db.Integer)  # soatlarda
    narxi = db.Column(db.Float)
    
    guruhlar = db.relationship('Guruh', backref='fan')

class Guruh(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nomi = db.Column(db.String(100), nullable=False)
    fan_id = db.Column(db.Integer, db.ForeignKey('fan.id'), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey('mentor.id'))
    boshlanish_sana = db.Column(db.Date)
    tugash_sana = db.Column(db.Date)
    max_talabalar = db.Column(db.Integer, default=15)
    holat = db.Column(db.String(20), default='faol')  # 'faol', 'tugallangan', 'rejalashtirilgan'
    
    dars_jadvali = db.relationship('DarsJadvali', backref='guruh', cascade='all, delete-orphan')

class GuruhAriza(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    talaba_id = db.Column(db.Integer, db.ForeignKey('talaba.id'), nullable=False)
    guruh_id = db.Column(db.Integer, db.ForeignKey('guruh.id'), nullable=False)
    holat = db.Column(db.String(20), default='kutilmoqda')  # 'kutilmoqda', 'qabul_qilindi', 'qabul_qilinmadi'
    ariza_sana = db.Column(db.DateTime, default=datetime.utcnow)
    javob_sana = db.Column(db.DateTime)
    izoh = db.Column(db.Text)
    
    talaba = db.relationship('Talaba', backref='guruh_arizalari')
    guruh = db.relationship('Guruh', backref='arizalar')

class DarsJadvali(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    guruh_id = db.Column(db.Integer, db.ForeignKey('guruh.id'), nullable=False)
    kun = db.Column(db.String(20), nullable=False)  # 'Dushanba', 'Seshanba', ...
    boshlanish_vaqti = db.Column(db.Time, nullable=False)
    tugash_vaqti = db.Column(db.Time, nullable=False)
    xona = db.Column(db.String(50))
    holat = db.Column(db.String(20), default='faol')  # 'faol', 'bekor_qilindi'
    yaratilgan_sana = db.Column(db.DateTime, default=datetime.utcnow)

# ============= DECORATORS =============

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Iltimos, tizimga kiring!', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Bu sahifaga kirish uchun admin huquqi kerak!', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def mentor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') not in ['admin', 'mentor']:
            flash('Bu sahifaga kirish uchun mentor huquqi kerak!', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ============= ROUTES =============

@app.route('/')
def index():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'mentor':
            return redirect(url_for('mentor_dashboard'))
        elif role == 'talaba':
            return redirect(url_for('talaba_dashboard'))
    return render_template('index.html')

# ============= AUTH ROUTES =============

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'talaba')
        ism = request.form.get('ism')
        familiya = request.form.get('familiya')
        telefon = request.form.get('telefon')
        
        if User.query.filter_by(username=username).first():
            flash('Bu foydalanuvchi nomi band!', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Bu email allaqachon ro\'yxatdan o\'tgan!', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        
        if role == 'talaba':
            talaba = Talaba(user_id=user.id, ism=ism, familiya=familiya, telefon=telefon)
            db.session.add(talaba)
        elif role == 'mentor':
            mentor = Mentor(user_id=user.id, ism=ism, familiya=familiya, telefon=telefon)
            db.session.add(mentor)
        
        db.session.commit()
        flash('Ro\'yxatdan muvaffaqiyatli o\'tdingiz!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(f'Xush kelibsiz, {user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Login yoki parol noto\'g\'ri!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Tizimdan chiqdingiz!', 'info')
    return redirect(url_for('index'))

# ============= ADMIN ROUTES =============

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    talabalar_soni = Talaba.query.count()
    mentorlar_soni = Mentor.query.count()
    guruhlar_soni = Guruh.query.count()
    fanlar_soni = Fan.query.count()
    arizalar_soni = GuruhAriza.query.filter_by(holat='kutilmoqda').count()
    jadvallar_soni = DarsJadvali.query.filter_by(holat='faol').count()
    
    # Yangi arizalarni olish (oxirgi 10 ta)
    arizalar = GuruhAriza.query.filter_by(holat='kutilmoqda').order_by(GuruhAriza.ariza_sana.desc()).limit(10).all()
    
    return render_template('admin_dashboard.html', 
                         talabalar_soni=talabalar_soni,
                         mentorlar_soni=mentorlar_soni,
                         guruhlar_soni=guruhlar_soni,
                         fanlar_soni=fanlar_soni,
                         arizalar_soni=arizalar_soni,
                         jadvallar_soni=jadvallar_soni,
                         arizalar=arizalar)

@app.route('/admin/fanlar')
@admin_required
def fanlar_list():
    fanlar = Fan.query.all()
    return render_template('fanlar_list.html', fanlar=fanlar)

@app.route('/admin/fan/add', methods=['GET', 'POST'])
@admin_required
def fan_add():
    if request.method == 'POST':
        fan = Fan(
            nomi=request.form.get('nomi'),
            tavsif=request.form.get('tavsif'),
            davomiyligi=request.form.get('davomiyligi'),
            narxi=request.form.get('narxi')
        )
        db.session.add(fan)
        db.session.commit()
        flash('Fan muvaffaqiyatli qo\'shildi!', 'success')
        return redirect(url_for('fanlar_list'))
    return render_template('fan_form.html')

@app.route('/admin/fan/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def fan_edit(id):
    fan = Fan.query.get_or_404(id)
    if request.method == 'POST':
        fan.nomi = request.form.get('nomi')
        fan.tavsif = request.form.get('tavsif')
        fan.davomiyligi = request.form.get('davomiyligi')
        fan.narxi = request.form.get('narxi')
        db.session.commit()
        flash('Fan muvaffaqiyatli yangilandi!', 'success')
        return redirect(url_for('fanlar_list'))
    return render_template('fan_form.html', fan=fan)

@app.route('/admin/fan/delete/<int:id>')
@admin_required
def fan_delete(id):
    fan = Fan.query.get_or_404(id)
    db.session.delete(fan)
    db.session.commit()
    flash('Fan o\'chirildi!', 'info')
    return redirect(url_for('fanlar_list'))

@app.route('/admin/guruhlar')
@admin_required
def guruhlar_list():
    guruhlar = Guruh.query.all()
    return render_template('guruhlar_list.html', guruhlar=guruhlar)

@app.route('/admin/guruh/add', methods=['GET', 'POST'])
@admin_required
def guruh_add():
    if request.method == 'POST':
        boshlanish = request.form.get('boshlanish_sana')
        guruh = Guruh(
            nomi=request.form.get('nomi'),
            fan_id=request.form.get('fan_id'),
            mentor_id=request.form.get('mentor_id'),
            boshlanish_sana=datetime.strptime(boshlanish, '%Y-%m-%d').date() if boshlanish else None,
            max_talabalar=request.form.get('max_talabalar', 15),
            holat=request.form.get('holat', 'faol')
        )
        db.session.add(guruh)
        db.session.commit()
        flash('Guruh muvaffaqiyatli qo\'shildi!', 'success')
        return redirect(url_for('guruhlar_list'))
    
    fanlar = Fan.query.all()
    mentorlar = Mentor.query.all()
    return render_template('guruh_form.html', fanlar=fanlar, mentorlar=mentorlar)

@app.route('/admin/guruh/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def guruh_edit(id):
    guruh = Guruh.query.get_or_404(id)
    if request.method == 'POST':
        boshlanish = request.form.get('boshlanish_sana')
        guruh.nomi = request.form.get('nomi')
        guruh.fan_id = request.form.get('fan_id')
        guruh.mentor_id = request.form.get('mentor_id')
        guruh.boshlanish_sana = datetime.strptime(boshlanish, '%Y-%m-%d').date() if boshlanish else None
        guruh.max_talabalar = request.form.get('max_talabalar', 15)
        guruh.holat = request.form.get('holat', 'faol')
        db.session.commit()
        flash('Guruh muvaffaqiyatli yangilandi!', 'success')
        return redirect(url_for('guruhlar_list'))
    
    fanlar = Fan.query.all()
    mentorlar = Mentor.query.all()
    return render_template('guruh_form.html', guruh=guruh, fanlar=fanlar, mentorlar=mentorlar)

@app.route('/admin/guruh/delete/<int:id>')
@admin_required
def guruh_delete(id):
    guruh = Guruh.query.get_or_404(id)
    db.session.delete(guruh)
    db.session.commit()
    flash('Guruh o\'chirildi!', 'info')
    return redirect(url_for('guruhlar_list'))

@app.route('/admin/talabalar')
@admin_required
def talabalar_list():
    talabalar = Talaba.query.all()
    return render_template('talabalar_list.html', talabalar=talabalar)

@app.route('/admin/talaba/<int:id>')
@admin_required
def talaba_detail(id):
    talaba = Talaba.query.get_or_404(id)
    return render_template('talaba_detail.html', talaba=talaba)

@app.route('/admin/talaba/delete/<int:id>')
@admin_required
def talaba_delete(id):
    talaba = Talaba.query.get_or_404(id)
    user = User.query.get(talaba.user_id)
    db.session.delete(talaba)
    db.session.delete(user)
    db.session.commit()
    flash('Talaba o\'chirildi!', 'info')
    return redirect(url_for('talabalar_list'))

@app.route('/admin/mentorlar')
@admin_required
def mentorlar_list():
    mentorlar = Mentor.query.all()
    return render_template('mentorlar_list.html', mentorlar=mentorlar)

@app.route('/admin/mentor/<int:id>')
@admin_required
def mentor_detail(id):
    mentor = Mentor.query.get_or_404(id)
    return render_template('mentor_detail.html', mentor=mentor)

@app.route('/admin/mentor/delete/<int:id>')
@admin_required
def mentor_delete(id):
    mentor = Mentor.query.get_or_404(id)
    user = User.query.get(mentor.user_id)
    db.session.delete(mentor)
    db.session.delete(user)
    db.session.commit()
    flash('Mentor o\'chirildi!', 'info')
    return redirect(url_for('mentorlar_list'))

# ============= ARIZA BOSHQARISH =============

@app.route('/admin/arizalar')
@admin_required
def arizalar_list():
    arizalar = GuruhAriza.query.order_by(GuruhAriza.ariza_sana.desc()).all()
    return render_template('arizalar_list.html', arizalar=arizalar)

@app.route('/admin/ariza/<int:id>')
@admin_required
def ariza_detail(id):
    ariza = GuruhAriza.query.get_or_404(id)
    return render_template('ariza_detail.html', ariza=ariza)

@app.route('/admin/ariza/qabul/<int:id>')
@admin_required
def ariza_qabul(id):
    ariza = GuruhAriza.query.get_or_404(id)
    
    if ariza.holat != 'kutilmoqda':
        flash('Bu ariza allaqachon ko\'rib chiqilgan!', 'warning')
        return redirect(url_for('ariza_detail', id=id))
    
    # Guruh to'lganmi tekshirish
    talabalar_soni = Talaba.query.filter_by(guruh_id=ariza.guruh_id).count()
    if talabalar_soni >= ariza.guruh.max_talabalar:
        flash('Guruh to\'lgan! Ariza qabul qilinmadi.', 'danger')
        ariza.holat = 'qabul_qilinmadi'
        ariza.javob_sana = datetime.utcnow()
        ariza.izoh = 'Guruh to\'lgan'
        db.session.commit()
        return redirect(url_for('ariza_detail', id=id))
    
    # Talabani guruhga qo'shish
    ariza.talaba.guruh_id = ariza.guruh_id
    ariza.holat = 'qabul_qilindi'
    ariza.javob_sana = datetime.utcnow()
    ariza.izoh = 'Ariza qabul qilindi va talaba guruhga qo\'shildi'
    
    db.session.commit()
    flash(f'Ariza qabul qilindi! {ariza.talaba.ism} {ariza.talaba.familiya} {ariza.guruh.nomi} guruhiga qo\'shildi.', 'success')
    return redirect(url_for('ariza_detail', id=id))

@app.route('/admin/ariza/rad/<int:id>', methods=['GET', 'POST'])
@admin_required
def ariza_rad(id):
    ariza = GuruhAriza.query.get_or_404(id)
    
    if ariza.holat != 'kutilmoqda':
        flash('Bu ariza allaqachon ko\'rib chiqilgan!', 'warning')
        return redirect(url_for('ariza_detail', id=id))
    
    if request.method == 'POST':
        izoh = request.form.get('izoh', 'Qabul qilinmadi')
        if not izoh.strip():
            izoh = 'Qabul qilinmadi'
        
        ariza.holat = 'qabul_qilinmadi'
        ariza.javob_sana = datetime.utcnow()
        ariza.izoh = izoh
        db.session.commit()
        
        if izoh == 'Qabul qilinmadi':
            flash('Ariza rad etildi!', 'info')
        else:
            flash(f'Ariza rad etildi! Sabab: {izoh}', 'info')
        return redirect(url_for('ariza_detail', id=id))
    
    return render_template('ariza_rad.html', ariza=ariza)

# ============= MENTOR ROUTES =============

@app.route('/mentor/dashboard')
@mentor_required
def mentor_dashboard():
    mentor = Mentor.query.filter_by(user_id=session['user_id']).first()
    if not mentor:
        flash('Mentor profili topilmadi!', 'danger')
        return redirect(url_for('index'))
    mening_guruhlar = Guruh.query.filter_by(mentor_id=mentor.id).all()
    return render_template('mentor_dashboard.html', mentor=mentor, guruhlar=mening_guruhlar)

@app.route('/mentor/profile')
@mentor_required
def mentor_profile():
    mentor = Mentor.query.filter_by(user_id=session['user_id']).first()
    return render_template('mentor_profile.html', mentor=mentor)

@app.route('/mentor/profile/edit', methods=['GET', 'POST'])
@mentor_required
def mentor_profile_edit():
    mentor = Mentor.query.filter_by(user_id=session['user_id']).first()
    if request.method == 'POST':
        mentor.ism = request.form.get('ism')
        mentor.familiya = request.form.get('familiya')
        mentor.telefon = request.form.get('telefon')
        mentor.mutaxassislik = request.form.get('mutaxassislik')
        tajriba = request.form.get('tajriba_yili')
        mentor.tajriba_yili = int(tajriba) if tajriba else None
        mentor.biografiya = request.form.get('biografiya')
        db.session.commit()
        flash('Profil yangilandi!', 'success')
        return redirect(url_for('mentor_profile'))
    return render_template('mentor_profile_edit.html', mentor=mentor)

@app.route('/mentor/guruh/<int:id>')
@mentor_required
def mentor_guruh_detail(id):
    guruh = Guruh.query.get_or_404(id)
    mentor = Mentor.query.filter_by(user_id=session['user_id']).first()
    
    if guruh.mentor_id != mentor.id and session.get('role') != 'admin':
        flash('Bu guruhga ruxsatingiz yo\'q!', 'danger')
        return redirect(url_for('mentor_dashboard'))
    
    return render_template('guruh_detail.html', guruh=guruh)

# ============= TALABA ROUTES =============

@app.route('/talaba/dashboard')
@login_required
def talaba_dashboard():
    talaba = Talaba.query.filter_by(user_id=session['user_id']).first()
    if not talaba:
        flash('Talaba profili topilmadi!', 'danger')
        return redirect(url_for('index'))
    
    # Talabaning arizalarini olish
    arizalar = GuruhAriza.query.filter_by(talaba_id=talaba.id).order_by(GuruhAriza.ariza_sana.desc()).all()
    
    return render_template('talaba_dashboard.html', talaba=talaba, arizalar=arizalar)

@app.route('/talaba/profile')
@login_required
def talaba_profile():
    talaba = Talaba.query.filter_by(user_id=session['user_id']).first()
    return render_template('talaba_profile.html', talaba=talaba)

@app.route('/talaba/profile/edit', methods=['GET', 'POST'])
@login_required
def talaba_profile_edit():
    talaba = Talaba.query.filter_by(user_id=session['user_id']).first()
    if request.method == 'POST':
        talaba.ism = request.form.get('ism')
        talaba.familiya = request.form.get('familiya')
        talaba.telefon = request.form.get('telefon')
        talaba.manzil = request.form.get('manzil')
        tug_sana = request.form.get('tug_sana')
        talaba.tug_sana = datetime.strptime(tug_sana, '%Y-%m-%d').date() if tug_sana else None
        db.session.commit()
        flash('Profil yangilandi!', 'success')
        return redirect(url_for('talaba_profile'))
    return render_template('talaba_profile_edit.html', talaba=talaba)

@app.route('/talaba/guruhga-yozilish', methods=['GET', 'POST'])
@login_required
def guruhga_yozilish():
    talaba = Talaba.query.filter_by(user_id=session['user_id']).first()
    if not talaba:
        flash('Talaba profili topilmadi!', 'danger')
        return redirect(url_for('talaba_dashboard'))
    
    if request.method == 'POST':
        guruh_id = request.form.get('guruh_id')
        
        if not guruh_id:
            flash('Guruhni tanlang!', 'danger')
            return redirect(url_for('guruhga_yozilish'))
        
        guruh = Guruh.query.get(guruh_id)
        if not guruh:
            flash('Guruh topilmadi!', 'danger')
            return redirect(url_for('guruhga_yozilish'))
        
        # Talaba bu guruhga necha marta ariza yuborganini tekshirish
        ariza_soni = GuruhAriza.query.filter_by(talaba_id=talaba.id, guruh_id=guruh_id).count()
        if ariza_soni >= 5:
            flash('Bu guruhga 5 martadan ko\'p ariza yuborish mumkin emas!', 'danger')
            return redirect(url_for('guruhga_yozilish'))
        
        # Talaba allaqachon bu guruhga qabul qilinganmi tekshirish
        qabul_qilingan_ariza = GuruhAriza.query.filter_by(talaba_id=talaba.id, guruh_id=guruh_id, holat='qabul_qilindi').first()
        if qabul_qilingan_ariza:
            flash('Bu guruhga allaqachon qabul qilingansiz!', 'warning')
            return redirect(url_for('guruhga_yozilish'))
        
        # Talaba allaqachon boshqa guruhda bormi tekshirish
        if talaba.guruh_id:
            flash('Siz allaqachon boshqa guruhdasiz!', 'warning')
            return redirect(url_for('guruhga_yozilish'))
        
        # Guruh to'lganmi tekshirish
        talabalar_soni = Talaba.query.filter_by(guruh_id=guruh_id).count()
        if talabalar_soni >= guruh.max_talabalar:
            flash('Guruh to\'lgan!', 'warning')
            return redirect(url_for('guruhga_yozilish'))
        
        # Ariza yaratish
        ariza = GuruhAriza(
            talaba_id=talaba.id,
            guruh_id=guruh_id,
            holat='kutilmoqda'
        )
        db.session.add(ariza)
        db.session.commit()
        flash('Ariza muvaffaqiyatli yuborildi! Administrator javobini kuting.', 'success')
        return redirect(url_for('talaba_dashboard'))
    
    # Faol guruhlarni olish
    guruhlar = Guruh.query.filter_by(holat='faol').all()
    
    # Har bir guruh uchun talabaning ariza sonini hisoblash
    guruhlar_with_ariza_count = []
    for guruh in guruhlar:
        ariza_soni = GuruhAriza.query.filter_by(talaba_id=talaba.id, guruh_id=guruh.id).count()
        qabul_qilingan = GuruhAriza.query.filter_by(talaba_id=talaba.id, guruh_id=guruh.id, holat='qabul_qilindi').first() is not None
        guruhlar_with_ariza_count.append({
            'guruh': guruh,
            'ariza_soni': ariza_soni,
            'max_arizalar': 5,
            'qabul_qilingan': qabul_qilingan
        })
    
    return render_template('guruhga_yozilish.html', guruhlar=guruhlar_with_ariza_count, talaba=talaba)

@app.route('/jadval/<int:guruh_id>')
@login_required
def dars_jadvali(guruh_id):
    guruh = Guruh.query.get_or_404(guruh_id)
    
    # Kunlar tartibini belgilash
    kunlar_tartibi = {
        'Dushanba': 1, 'Seshanba': 2, 'Chorshanba': 3, 'Payshanba': 4,
        'Juma': 5, 'Shanba': 6, 'Yakshanba': 7
    }
    
    # Faol jadvallarni kunlar bo'yicha tartiblash
    jadval = DarsJadvali.query.filter_by(guruh_id=guruh_id, holat='faol').all()
    jadval = sorted(jadval, key=lambda x: kunlar_tartibi.get(x.kun, 8))
    
    return render_template('dars_jadvali.html', guruh=guruh, jadval=jadval)

@app.route('/admin/jadval/add/<int:guruh_id>', methods=['GET', 'POST'])
@admin_required
def jadval_add(guruh_id):
    guruh = Guruh.query.get_or_404(guruh_id)
    if request.method == 'POST':
        kun_turi = request.form.get('kun_turi')  # 'barcha', 'juft', 'toq'
        kunlar = request.form.getlist('kunlar')  # Tanlangan kunlar
        boshlanish = request.form.get('boshlanish_vaqti')
        tugash = request.form.get('tugash_vaqti')
        xona = request.form.get('xona')
        
        # Validatsiya
        if not kun_turi or not boshlanish or not tugash:
            flash('Barcha majburiy maydonlarni to\'ldiring!', 'danger')
            return redirect(url_for('jadval_add', guruh_id=guruh_id))
        
        if kun_turi == 'tanlash' and not kunlar:
            flash('Kamida bitta kunni tanlang!', 'danger')
            return redirect(url_for('jadval_add', guruh_id=guruh_id))
        
        try:
            # Vaqt formatini to'g'ri o'zgartirish
            boshlanish_vaqti = datetime.strptime(boshlanish, '%H:%M').time()
            tugash_vaqti = datetime.strptime(tugash, '%H:%M').time()
            
            # Vaqt tekshiruvi
            if boshlanish_vaqti >= tugash_vaqti:
                flash('Tugash vaqti boshlanish vaqtidan keyin bo\'lishi kerak!', 'danger')
                return redirect(url_for('jadval_add', guruh_id=guruh_id))
            
            # Kunlarni aniqlash
            if kun_turi == 'barcha':
                tanlangan_kunlar = ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba']
            elif kun_turi == 'juft':
                tanlangan_kunlar = ['Dushanba', 'Chorshanba', 'Juma', 'Yakshanba']
            elif kun_turi == 'toq':
                tanlangan_kunlar = ['Seshanba', 'Payshanba', 'Shanba']
            else:  # tanlash
                tanlangan_kunlar = kunlar
            
            # Har bir kun uchun jadval yaratish
            yaratilgan_jadval = 0
            for kun in tanlangan_kunlar:
                # Shu kunda vaqtlar mos kelmasligini tekshirish
                existing_jadval = DarsJadvali.query.filter_by(guruh_id=guruh_id, kun=kun, holat='faol').first()
                if existing_jadval:
                    continue  # Bu kun uchun jadval mavjud, o'tkazib yuborish
                
                jadval = DarsJadvali(
                    guruh_id=guruh_id,
                    kun=kun,
                    boshlanish_vaqti=boshlanish_vaqti,
                    tugash_vaqti=tugash_vaqti,
                    xona=xona,
                    holat='faol'
                )
                db.session.add(jadval)
                yaratilgan_jadval += 1
            
            db.session.commit()
            flash(f'{yaratilgan_jadval} ta dars jadvali muvaffaqiyatli qo\'shildi!', 'success')
            return redirect(url_for('dars_jadvali', guruh_id=guruh_id))
            
        except ValueError:
            flash('Vaqt formati noto\'g\'ri!', 'danger')
            return redirect(url_for('jadval_add', guruh_id=guruh_id))
        except Exception as e:
            flash(f'Xatolik yuz berdi: {str(e)}', 'danger')
            return redirect(url_for('jadval_add', guruh_id=guruh_id))
    
    kunlar = ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba']
    return render_template('jadval_form.html', guruh=guruh, kunlar=kunlar)

@app.route('/admin/jadval/delete/<int:id>')
@admin_required
def jadval_delete(id):
    jadval = DarsJadvali.query.get_or_404(id)
    guruh_id = jadval.guruh_id
    
    # Jadvalni bekor qilish (o'chirish o'rniga holatini o'zgartirish)
    jadval.holat = 'bekor_qilindi'
    db.session.commit()
    flash('Dars jadvali bekor qilindi!', 'info')
    return redirect(url_for('dars_jadvali', guruh_id=guruh_id))

@app.route('/admin/jadval/restore/<int:id>')
@admin_required
def jadval_restore(id):
    jadval = DarsJadvali.query.get_or_404(id)
    guruh_id = jadval.guruh_id
    
    # Jadvalni qayta faollashtirish
    jadval.holat = 'faol'
    db.session.commit()
    flash('Dars jadvali qayta faollashtirildi!', 'success')
    return redirect(url_for('dars_jadvali', guruh_id=guruh_id))

# ============= DATABASE INIT =============

@app.cli.command()
def init_db():
    """Ma'lumotlar bazasini yaratish"""
    db.create_all()
    
    # Eski admin foydalanuvchisini o'chirish (agar mavjud bo'lsa)
    old_admin = User.query.filter_by(username='admin').first()
    if old_admin:
        db.session.delete(old_admin)
        db.session.commit()
        print('Eski admin foydalanuvchisi o\'chirildi')
    
    # Yangi admin yaratish
    if not User.query.filter_by(username='admin123').first():
        admin = User(username='admin123', email='admin@oquvmarkaz.uz', role='admin')
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()
        print('Admin yaratildi: username=admin123, password=admin')
    
    print('Ma\'lumotlar bazasi yaratildi!')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Eski admin foydalanuvchisini o'chirish (agar mavjud bo'lsa)
        old_admin = User.query.filter_by(username='admin').first()
        if old_admin:
            db.session.delete(old_admin)
            db.session.commit()
            print('Eski admin foydalanuvchisi o\'chirildi')
        
        # Yangi admin yaratish
        if not User.query.filter_by(username='admin123').first():
            admin = User(username='admin123', email='admin@oquvmarkaz.uz', role='admin')
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            print('Admin yaratildi: username=admin123, password=admin')
    
    app.run(debug=True)


