from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import random
import datetime
import time
import threading

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz.db'
app.config['TEMPLATES_AUTO_RELOAD'] = True
db = SQLAlchemy(app)

# Database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    last_attempt = db.Column(db.DateTime, nullable=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    option_a = db.Column(db.String(100), nullable=False)
    option_b = db.Column(db.String(100), nullable=False)
    option_c = db.Column(db.String(100), nullable=False)
    option_d = db.Column(db.String(100), nullable=False)
    option_e = db.Column(db.String(100), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)

class UserAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Kullanıcı ID'si
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)  # Soru ID'si
    chosen_option = db.Column(db.String(1), nullable=True)  # Kullanıcının seçtiği şık
    is_correct = db.Column(db.Boolean, nullable=False, default=False)  # Doğru mu?
    is_blank = db.Column(db.Boolean, nullable=False, default=False)  # Boş mu?

    user = db.relationship('User', backref=db.backref('answers', lazy=True))
    question = db.relationship('Question', backref=db.backref('answers', lazy=True))


quiz_code = str(random.randint(1000, 9999))

def generate_code():
    """Arka planda çalışan thread, her 10 saniyede bir yeni kod oluşturur."""
    global quiz_code
    while True:
        time.sleep(60)  # 10 saniyede bir kodu değiştir
        quiz_code = str(random.randint(1000, 9999))  # Yeni kod üret
        print(f"Yeni Quiz Kodu: {quiz_code}")  # Konsolda güncellenen kodu göster


with app.app_context():
    db.create_all()

@app.route('/get_code')
def get_code():
    """Güncellenen kodu JSON formatında döndür (AJAX için)."""
    return jsonify({"code": quiz_code})


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        surname = request.form['surname']
        user = User.query.filter_by(name=name, surname=surname).first()
        
        if not user:
            user = User(name=name, surname=surname)
            db.session.add(user)
            db.session.commit()

        if user.last_attempt and (datetime.utcnow() - user.last_attempt).total_seconds() < 180:
            return "Testi tekrar başlatamazsınız. Lütfen bekleyin."

        session['user_id'] = user.id
        session['name'] = name
        session['surname'] = surname  

        return redirect(url_for('start_quiz'))
    return render_template('login.html')

@app.route('/start_quiz', methods=['GET', 'POST'])  # GET ve POST ekledik
def start_quiz():
    if request.method == 'POST':
        user_id = session.get('user_id')
        if not user_id:
            return "Lütfen giriş yapın.", 403  

        user = User.query.get(user_id)
        entered_code = request.form.get('code')  # Kullanıcının girdiği kod
        if entered_code == quiz_code:
            return redirect(url_for('quiz'))  # Kod doğruysa quiz başlasın
        else:
            return "<script>alert('Kod Yanlış! Lütfen tekrar deneyin.'); window.location.href='/start_quiz';</script>"

    return render_template('start_quiz.html') 

@app.route('/check_code', methods=['POST'])
def check_code():
    user_code = request.form.get('code')
    
    if user_code == quiz_code:
        return redirect(url_for('quiz'))  # Doğru kod girildi, quiz başlasın
    else:
        return "<script>alert('Kod Yanlış! Lütfen tekrar deneyin.'); window.location.href='/';</script>"


@app.route('/admin_results')
def admin_results():
    users = User.query.all()
    user_data = []

    for user in users:
        answers = UserAnswer.query.filter_by(user_id=user.id).all()
        correct_count = sum(1 for ans in answers if ans.is_correct)
        total_questions = len(answers)
        score_percentage = (correct_count / total_questions) * 100 if total_questions > 0 else 0
        wrong_count = sum(1 for ans in answers if not ans.is_correct and not ans.is_blank)
        blank_count = sum(1 for ans in answers if ans.is_blank)

        user_data.append({
            'username': f"{user.name} {user.surname}",
            'correct': correct_count,
            'wrong': wrong_count,
            'blank': blank_count,
            'score': int(score_percentage)
        })

    return render_template('admin_results.html', user_data=user_data, code=quiz_code)



@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))




@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if password == 'admin123' and username == 'Zamin':
            session['admin'] = True
            return redirect(url_for('admin_results'))
        else:
            return render_template('admin_login.html', error="Yanlış şifre!")

    return render_template('admin_login.html')



@app.route('/quiz', methods=['GET', 'POST'])
def quiz():

    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']

    if request.method == 'POST':
        for key, value in request.form.items():
            question_id = int(key.split('_')[-1])
            question = Question.query.get(question_id)

            if not question:
                continue  

            answer = UserAnswer.query.filter_by(user_id=user_id, question_id=question_id).first()

            if not answer:
                answer = UserAnswer(user_id=user_id, question_id=question_id)
                db.session.add(answer)

            answer.chosen_option = value if value else None
            answer.is_correct = value == question.correct_option if value else False
            answer.is_blank = value == ""  

        db.session.commit()

        return "Imtahini bitirdiniz! Ugurlar!!!"

    # Kullanıcının daha önce çözmediği soruları getir
    answered_questions = {ans.question_id for ans in UserAnswer.query.filter_by(user_id=user_id).all()}
    questions = Question.query.filter(~Question.id.in_(answered_questions)).order_by(db.func.random()).limit(11).all()

    if len(questions) < 11:  # Eğer yeterli yeni soru yoksa, tekrar sorular gösterilebilir
        questions = Question.query.order_by(db.func.random()).limit(36).all()

    return render_template('quiz.html', questions=questions, name=session.get('name', ''), surname=session.get('surname', ''))




@app.route('/admin')
def admin():
    users = User.query.all()
    results = {}
    for user in users:
        answers = UserAnswer.query.filter_by(user_id=user.id).all()
        correct = sum(1 for ans in answers if ans.chosen_option == Question.query.get(ans.question_id).correct_option)
        incorrect = sum(1 for ans in answers if ans.chosen_option and ans.chosen_option != Question.query.get(ans.question_id).correct_option)
        empty = 41 - (correct + incorrect)
        results[user.name + ' ' + user.surname] = {'correct': correct, 'incorrect': incorrect, 'empty': empty}
    return render_template('admin.html', results=results)

def add_questions():
    if Question.query.count() == 0:  # Eğer veritabanında hiç soru yoksa ekle
        questions = [
        Question(text="Partlayış təhlükəli zona nədir?", option_a="Sadəcə yanğın riski olan ərazi", option_b="Partlayıcı qazların və ya tozların ola biləcəyi yer", option_c="Elektrik naqilləri olan hər hansı ərazi", option_d="Kimyəvi maddələr saxlanılan anbar", option_e="Yalnız yüksək temperatur olan sahə", correct_option="B"),
        Question(text="Hansı sənəd partlayış təhlükəli zonalarda istifadə olunan avadanlıqları tənzimləyir?", option_a="ISO 9001", option_b="ATEX Direktivi", option_c="CE Sertifikatı", option_d="OSHA Standartı", option_e="IEC 61892", correct_option="B"),
        Question(text="ATEX sertifikatı nə üçündür?", option_a="Elektrik avadanlıqlarının suya davamlılığını yoxlamaq üçün", option_b="Yüksək gərginlikli avadanlıqlar üçün", option_c="Partlayış təhlükəli mühitlərdə istifadə üçün avadanlıqları təsdiqləmək üçün", option_d="Sənaye müəssisələrində istifadə olunan mexanizmlər üçün", option_e="Səviyyə ölçmə cihazları üçün", correct_option="C"),
        Question(text="Ex işarəsi nəyi bildirir?", option_a="Yanğınsöndürmə cihazının mövcudluğunu", option_b="Partlayış təhlükəsiz avadanlıq olduğunu", option_c="Elektrik naqillərinin çəkilmə qaydalarını", option_d="Kimyəvi maddələrin təhlükəli səviyyəsini", option_e="İş yerlərində havalandırma sistemini", correct_option="B"),
        Question(text="Zonalar necə təsnif edilir?", option_a="0, 1, 2 və 20, 21, 22 kimi", option_b="A, B, C, D kimi", option_c="1, 2, 3, 4 kimi", option_d="Qırmızı, Sarı, Yaşıl kimi", option_e="Elektrik və qeyri-elektrik kimi", correct_option="A"),
        Question(text="Partlayış təhlükəli zonada hansı növ alətlər istifadə olunmalıdır?", option_a="Normal sənaye alətləri", option_b="Partlayışa davamlı və ya intrinsik təhlükəsiz alətlər", option_c="Plastik alətlər", option_d="Sadəcə mexaniki alətlər", option_e="Yüksək gərginlikli avadanlıqlar", correct_option="B"),
        Question(text="IECEx nədir?", option_a="Beynəlxalq elektrik sertifikasiyası sistemi", option_b="Elektrik naqillərinin ölçülməsi qaydaları", option_c="Təhlükəsizlik kaskalarının standartı", option_d="Su altında qaynaq qaydaları", option_e="Yanğınsöndürmə avadanlıqlarının sertifikasiyası", correct_option="A"),
        Question(text="Partlayış təhlükəli zonada hansı geyim geyinilməlidir?", option_a="Sintetik geyimlər", option_b="Neft və yanacaq keçirməyən geyimlər", option_c="Normal işçi formasından istifadə edilə bilər", option_d="Yalnız pambıq paltarlar", option_e="Metal düyməli və fermuarlı geyimlər", correct_option="B"),
        Question(text="Partlayış təhlükəli zonalarda istifadə olunan kabel növü hansı olmalıdır?", option_a="Plastik izolyasiyalı kabellər", option_b="Alüminium naqillər", option_c="ATEX və ya IECEx sertifikatlı kabellər", option_d="Yüksək gərginlikli enerji kabelləri", option_e="Standart sənaye kabelləri", correct_option="C"),
        Question(text="Hansı yanacaq hava qarışığı partlayıcı mühit yarada bilər?", option_a="Yalnız qaz qarışıqları", option_b="Yalnız neft məhsulları", option_c="Hər hansı üzvi və ya qeyri-üzvi maddələrin toz və qaz halında qarışıqları", option_d="Yalnız hidrogen və oksigen qarışığı", option_e="Heç biri", correct_option="C"),
        Question(text="Partlayışa davamlı avadanlıqlar hansıdır?", option_a="Ex e", option_b="Ex i", option_c="Ex d", option_d="Ex n", option_e="Heç biri", correct_option="C"),
        Question(text="Hansılardan biri yanğının baş verməsi üçün lazım deyil?", option_a="Yanacaq", option_b="Oksigen", option_c="Qapalı mühit", option_d="Kifayət qədər enerjili qığılcım", option_e="Heç biri", correct_option="C"),
        Question(text="ATEX kateqoriyaları ilə əlaqədar, avadanlıqlar üçün hansı qısaltma istifadə olunur?", option_a="IEC", option_b="APL", option_c="EPL", option_d="API", option_e="Heç biri", correct_option="C"),
        Question(text="EPL-in açılışı nədir?", option_a="Elektrik Mühafizə Səviyyəsi", option_b="Avadanlıq Mühafizə Səviyyəsi", option_c="Elektrik Mühafizə Yükü", option_d="Avadanlıq Təzyiq Səviyyəsi", option_e="Heç biri", correct_option="B"),
        Question(text="Ex 'n' avadanlıqları harada istifadə edilə bilər?", option_a="Zona 0", option_b="Zona 0 və Zona 1", option_c="Zona 0, 1 və 2", option_d="Zona 2", option_e="Heç biri", correct_option="D"),
        Question(text="'Gc' avadanlıq mühafizə səviyyəsi (EPL) və ya 3-cü kateqoriya avadanlıqlar harada istifadə edilə bilər?", option_a="Zona 0", option_b="Zona 0 və 1", option_c="Zona 0, 1 və 2", option_d="Zona 2", option_e="Heç biri", correct_option="D"),
        Question(text="Ex 'd' mühafizə konsepsiyasının ümumi tələbləri ilə bağlı hansı standart istifadə olunur?", option_a="IEC 60079-1", option_b="IEC 60079-3", option_c="IEC 60079-14", option_d="IEC 60079-17", option_e="Heç biri", correct_option="A"),
        Question(text="Alovkeçirməz avadanlıqlar niyə belə adlanır?", option_a="Daxili partlayışa icazə verilmir", option_b="Daxili partlayışa icazə verilir", option_c="Xarici partlayışa icazə verilir", option_d="Qazın örtük içinə girməsinə müqavimət göstərir", option_e="Heç biri", correct_option="B"),
        Question(text="Ex 'd' avadanlıqları harada istifadə edilə bilər?", option_a="Zona 0", option_b="Zona 1 və 2", option_c="Yalnız Zona 2", option_d="Zona 0 və 1", option_e="Heç biri", correct_option="B"),
        Question(text="IEC 60079-1 standartı nə ilə bağlıdır?", option_a="Ex 'd' alovkeçirməz mühafizə konsepsiyası", option_b="Ex 'e' artırılmış təhlükəsizlik konsepsiyası", option_c="Ex 'i' intrinsik təhlükəsizlik konsepsiyası", option_d="Ex 'n' normal mühafizə konsepsiyası", option_e="Heç biri", correct_option="A"),
        Question(text="Alovkeçirməz (flameproof) örtükdə yerləşən açarın həcmi 2 litrdən azdır və IIC mühitində yerləşir. Örtük hansı növ qovşaqlara ehtiyac duyur?", option_a="Sənaye tipli qovşaqlar", option_b="Ex 'e' qovşaqlar", option_c="Ex 'd' baryer qovşaqlar", option_d="Dolğu qovşaqları ilə təchiz olunmuş dolayı giriş Ex 'e' kamerası", option_e="Heç biri", correct_option="C"),
        Question(text="Artırılmış təhlükəsiz Ex 'e' aparatları daxili partlayışları saxlayacaq şəkildə hazırlanmışdır?", option_a="Bəli", option_b="Xeyr", option_c="Bəli, əgər baryer qovşaqlar istifadə olunarsa", option_d="Bəli, əgər IP dərəcəsi ən azı IP54 olarsa", option_e="Heç biri", correct_option="B"),
        Question(text="Ümumiyyətlə, Ex 'e' avadanlıqları harada quraşdırıla bilər?", option_a="Zona 0", option_b="Zona 1 və 2", option_c="Zona 0, 1 və 2", option_d="Yalnız Zona 2", option_e="Heç biri", correct_option="B"),
        Question(text="Ex 'e' avadanlıqları hansı EPL (Equipment Protection Level) tələblərinə cavab verməlidir?", option_a="EPL 'Ga' və 'Gb' avadanlıqları", option_b="EPL 'Ga', 'Gb' və 'Gc' avadanlıqları", option_c="EPL 'Ga' və ya 1-ci kateqoriya avadanlıqları", option_d="EPL 'Gb' və 'Gc' avadanlıqları", option_e="Heç biri", correct_option="D"),
        Question(text="Ex 'e' avadanlıqlarının IP reytinqi neçə olmalıdır?", option_a="IP 54", option_b="Ən azı IP 54, lakin mühit şərtləri daha yüksək dəyər tələb edə bilər", option_c="IP 44", option_d="Ən azı IP 44, lakin mühit şərtləri daha yüksək dəyər tələb edə bilər", option_e="Heç biri", correct_option="B"),
        Question(text="Ex 'e' avadanlıqlarda kontrqaykalar (locknut) nə vaxt tələb olunur?", option_a="Həmişə tələb olunur", option_b="Heç vaxt tələb olunmur", option_c="Yalnız boşluq deşiklərində tələb olunur", option_d="Yalnız 10 mm qalınlığında yivli girişlərdə tələb olunur", option_e="Heç biri", correct_option="C"),
        Question(text="Ümumiyyətlə, Ex 'n' avadanlıqları harada quraşdırıla bilər?", option_a="Zona 0", option_b="Zona 1", option_c="Zona 2", option_d="Təmiz zonalar", option_e="Heç biri", correct_option="C"),
        Question(text="Ex 'n' avadanlıqları hansı qaz qrupları üçün nəzərdə tutulmuş ola bilər?", option_a="II qrup", option_b="IIA və IIB qrupları", option_c="Yalnız IIA qrupu", option_d="Yalnız IIB qrupu", option_e="Heç biri", correct_option="B"),
        Question(text="Aşağıdakılardan hansı Ex 'n' mühafizə metodlarından biri deyil?", option_a="Tip A - qığılcım yaratmayan", option_b="Tip d - alovkeçirməz", option_c="Tip L - enerji məhdudlaşdırılmış", option_d="Tip R - məhdud nəfəsalma", option_e="Tip C - hermetik möhürlənmiş, kapsullanmış", correct_option="B"),
        Question(text="8 mm qalınlığında, yivli girişə malik Ex 'n' metal örtüyə kabel qoşulduqda hansı tələb olunur?", option_a="Kontrqayka (locknut)", option_b="Ulduz yuyucu (star washer)", option_c="IP yuyucu (IP washer)", option_d="Heç biri", option_e="Heç biri", correct_option="A"),
        Question(text="Ex 'n' məhdud nəfəsalma (restricted breathing) mühafizəsi üçün həmişə hansı element təmin edilməlidir?", option_a="IP yuyucu (IP washer)", option_b="Kontrqayka (locknut)", option_c="Yerə qoşulma etiketi (earth tag)", option_d="Yivli giriş (threaded entry)", option_e="Heç biri", correct_option="D"),
        Question(text="Ex 'ia' avadanlıqları harada quraşdırıla bilər?", option_a="Zona 0", option_b="Zona 1", option_c="Zona 2", option_d="Təmiz zonalar", option_e="Heç biri", correct_option="A"),
        Question(text="Qalvanik izolatorlar nəyi tələb edir?", option_a="İntrinsik təhlükəsiz yerə qoşulma", option_b="Ən azı iki Zener diodu", option_c="Elektrik ayrılmasını təmin edən qurğu (məsələn, transformator, relye və ya opto-kuplör)", option_d="Ən azı üç Zener diodu", option_e="Heç biri", correct_option="C"),
        Question(text="Aşağıdakılardan hansına intrinsik təhlükəsiz xüsusi yerə qoşulma lazım deyil?", option_a="İki Zener diodlu Zener baryeri", option_b="Qalvanik izolyasiyalı baryer", option_c="Üç Zener diodlu Zener baryeri", option_d="Sadə aparatları təmin edən Zener baryeri", option_e="Heç biri", correct_option="B"),
        Question(text="İntrinsik təhlükəsiz dövrələrin terminalları ilə qeyri-intrinsik təhlükəsiz dövrələrin terminalları arasında minimum məsafə nə qədər olmalıdır?", option_a="100 mm", option_b="50 mm", option_c="6 mm", option_d="3 mm", option_e="Heç biri", correct_option="C"),
        Question(text="Yerə qədər olan minimum məsafə (intrinsik təhlükəsiz dövrələr üçün) nə qədərdir?", option_a="100 mm", option_b="50 mm", option_c="6 mm", option_d="3 mm", option_e="Heç biri", correct_option="D")
        ]
        db.session.bulk_save_objects(questions)  # Daha hızlı ekleme
        db.session.commit()
        print("Sorular eklendi!")
    else:
        print("Sorular zaten ekli, tekrar eklenmedi.")


# Fonksiyonu çağır
with app.app_context():
    add_questions()

if __name__ == '__main__':
    threading.Thread(target=generate_code, daemon=True).start()
    app.run(debug=True, host="0.0.0.0", port=10000)


