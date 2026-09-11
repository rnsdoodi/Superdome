from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import openpyxl
import os
import io
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)

# --- الإعدادات (Configuration) ---
# استخدام متغيرات البيئة على Heroku، مع قيم افتراضية للتطوير المحلي
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'superdome_secret_key_2024_dev')

# Heroku يوفر متغير DATABASE_URL لـ PostgreSQL
# نستخدم SQLite محلياً إذا لم يكن المتغير موجوداً
database_url = os.environ.get('DATABASE_URL', 'sqlite:///superdome.db')

# إصلاح مشكلة Heroku القديمة (postgres:// بدلاً من postgresql://)
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)


class CompanyRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_name = db.Column(db.String(100), nullable=False)
    job_title = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)  # جديد
    email = db.Column(db.String(100), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    request_details = db.Column(db.Text, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- Routes ---
@app.route('/')
def landing():
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        new_request = CompanyRequest(
            person_name=request.form.get('person_name'),
            job_title=request.form.get('job_title'),
            phone=request.form.get('phone'),  # جديد
            email=request.form.get('email'),
            company_name=request.form.get('company_name'),
            request_details=request.form.get('request_details')
        )
        db.session.add(new_request)
        db.session.commit()
        flash('Request added successfully')
        return redirect(url_for('dashboard'))

    requests = CompanyRequest.query.all()
    return render_template('dashboard.html', requests=requests)

@app.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_request(id):
    req = CompanyRequest.query.get_or_404(id)
    req.person_name = request.form.get('person_name')
    req.job_title = request.form.get('job_title')
    req.phone = request.form.get('phone')  # جديد
    req.email = request.form.get('email')
    req.company_name = request.form.get('company_name')
    req.request_details = request.form.get('request_details')
    db.session.commit()
    flash('Data updated successfully')
    return redirect(url_for('dashboard'))


@app.route('/delete/<int:id>')
@login_required
def delete_request(id):
    req = CompanyRequest.query.get_or_404(id)
    db.session.delete(req)
    db.session.commit()
    flash('Request deleted successfully')
    return redirect(url_for('dashboard'))


# --- Export Routes ---
@app.route('/export/excel')
@login_required
def export_excel():
    requests = CompanyRequest.query.all()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Company Requests"
    ws.append(['ID', 'Person Name', 'Job Title', 'Phone', 'Email', 'Company Name', 'Request Details'])

    for req in requests:
        ws.append([req.id, req.person_name, req.job_title, req.phone, req.email, req.company_name, req.request_details])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, download_name="requests.xlsx", as_attachment=True)

@app.route('/export/pdf')
@login_required
def export_pdf():
    requests = CompanyRequest.query.all()
    buffer = io.BytesIO()

    font_path = os.path.join(app.root_path, 'static', 'fonts', 'NotoSansArabic.ttf')

    if not os.path.exists(font_path):
        flash('PDF font not found. Please upload the file to static/fonts/')
        return redirect(url_for('dashboard'))

    pdfmetrics.registerFont(TTFont('ArabicFont', font_path))

    def format_arabic(text):
        if not text:
            return ""
        reshaped_text = arabic_reshaper.reshape(str(text))
        bidi_text = get_display(reshaped_text)
        return bidi_text

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ArabicTitle', parent=styles['Title'],
        fontName='ArabicFont', fontSize=18, alignment=1,
        textColor=colors.HexColor('#0b6623'),
    )

    arabic_cell_style = ParagraphStyle(
        'ArabicCell', parent=styles['Normal'],
        fontName='ArabicFont', fontSize=9, alignment=2, leading=14,
    )

    header_cell_style = ParagraphStyle(
        'HeaderCell', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10,
        textColor=colors.whitesmoke, alignment=1,
    )

    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(letter),
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    elements = []

    elements.append(Paragraph("Jeddah Superdome - Company Requests Report", title_style))
    elements.append(Spacer(1, 20))

    header_row = [
        Paragraph('ID', header_cell_style),
        Paragraph('Person Name', header_cell_style),
        Paragraph('Job Title', header_cell_style),
        Paragraph('Phone', header_cell_style),  # جديد
        Paragraph('Email', header_cell_style),
        Paragraph('Company Name', header_cell_style),
        Paragraph('Request Details', header_cell_style),
    ]
    data = [header_row]

    for req in requests:
        data.append([
            Paragraph(str(req.id), arabic_cell_style),
            Paragraph(format_arabic(req.person_name), arabic_cell_style),
            Paragraph(format_arabic(req.job_title), arabic_cell_style),
            Paragraph(str(req.phone), arabic_cell_style),  # جديد
            Paragraph(str(req.email), arabic_cell_style),
            Paragraph(format_arabic(req.company_name), arabic_cell_style),
            Paragraph(format_arabic(req.request_details), arabic_cell_style),
        ])

    col_widths = [30, 100, 100, 90, 130, 110, 200]  # تم تعديل العرض

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0b6623')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f4f9f4')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f4f9f4')]),
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return send_file(buffer, download_name="requests.pdf", as_attachment=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)