from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
import logging
import re
from bleach.sanitizer import Cleaner
from config import Config
from database import Database

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
logging.basicConfig(level=logging.INFO)

db = Database()
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_REGEX = re.compile(r"^[0-9+\-\s()]{5,20}$")
ALLOWED_CAMPAIGNS = {"urgent", "password", "docs", "marketplace", "invoice"}

TEMPLATES_LIBRARY = {
    "urgent": {
        "title": "Срочное обновление учетной записи",
        "description": "Классический сценарий давления по времени.",
        "endpoint": "index",
    },
    "marketplace": {
        "title": "Имитация маркетплейса",
        "description": "Поддельное уведомление о заказе на популярной площадке.",
        "endpoint": "marketplace_template",
    },
    "docs": {
        "title": "Запрос доступа к Google Docs",
        "description": "Письмо о доступе к документу от неизвестного отправителя.",
        "endpoint": "docs_template",
    },
    "password": {
        "title": "Истечение пароля",
        "description": "Требование срочной смены пароля в корпоративном портале.",
        "endpoint": "password_template",
    },
    "invoice": {
        "title": "Подозрительный счет от бухгалтерии",
        "description": "Вложение со счетом и призыв открыть документ.",
        "endpoint": "invoice_template",
    },
}

HTML_CLEANER = Cleaner(
    tags=["b", "i", "strong", "em", "p", "br", "ul", "ol", "li", "a"],
    attributes={"a": ["href", "title", "target", "rel"]},
    strip=True,
)


def _sanitize_text(value, max_length=120):
    if value is None:
        return ""
    return str(value).strip()[:max_length]


def _sanitize_rich_html(value):
    if value is None:
        return ""
    return HTML_CLEANER.clean(str(value))


def _validate_user_data(user_data):
    if not user_data["first_name"] or not user_data["last_name"]:
        return "Имя и фамилия обязательны."
    if not EMAIL_REGEX.match(user_data["email"]):
        return "Некорректный формат email."
    if user_data["phone"] and not PHONE_REGEX.match(user_data["phone"]):
        return "Некорректный формат телефона."
    return None


@app.after_request
def add_security_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

@app.route('/')
def index():
    logging.info(f"Главная страница – IP: {request.remote_addr}")
    return render_template("index.html", templates_library=TEMPLATES_LIBRARY)

@app.route('/register', methods=['GET', 'POST'])
def register():
    campaign_id = _sanitize_text(request.args.get("campaign"), max_length=30)
    if campaign_id and campaign_id not in ALLOWED_CAMPAIGNS:
        abort(400, description="Некорректный идентификатор кампании.")

    if request.method == 'POST':
        user_data = {
            "first_name": _sanitize_text(request.form.get("first_name")),
            "last_name": _sanitize_text(request.form.get("last_name")),
            "middle_name": _sanitize_text(request.form.get("middle_name")),
            "email": _sanitize_text(request.form.get("email"), max_length=255).lower(),
            "phone": _sanitize_text(request.form.get("phone"), max_length=40),
            "ip_address": _sanitize_text(request.remote_addr, max_length=45),
            "user_agent": _sanitize_text(request.headers.get("User-Agent", ""), max_length=255),
        }
        validation_error = _validate_user_data(user_data)
        if validation_error:
            return render_template(
                "register.html",
                campaign_id=campaign_id,
                validation_error=validation_error,
            ), 400

        db.save_user(user_data, campaign_id)
        return redirect(url_for("caught"))
    return render_template("register.html", campaign_id=campaign_id)

@app.route('/caught')
def caught():
    ua = request.headers.get('User-Agent', '').lower()
    is_mobile = 'mobile' in ua or 'android' in ua or 'iphone' in ua
    quiz_questions = [
        {
            "id": 1,
            "question": "Какой признак на странице чаще всего указывает на фишинг?",
            "options": [
                "Официальный домен компании",
                "Срочный призыв ввести данные или пароль",
                "Наличие HTTPS в адресной строке",
            ],
            "correct": 1,
        },
        {
            "id": 2,
            "question": "Что делать при получении подозрительного письма?",
            "options": [
                "Перейти по ссылке и проверить",
                "Переслать в ИБ/IT отдел и не вводить данные",
                "Удалить и никому не сообщать",
            ],
            "correct": 1,
        },
    ]
    return render_template("caught.html", is_mobile=is_mobile, quiz_questions=quiz_questions)


@app.route("/quiz/check", methods=["POST"])
def quiz_check():
    selected_answers = request.form.getlist("answers")
    expected = ["1", "1"]
    score = sum(1 for selected, expected_answer in zip(selected_answers, expected) if selected == expected_answer)
    return jsonify({"passed": score == len(expected), "score": score, "max_score": len(expected)})


@app.route("/template/marketplace")
def marketplace_template():
    return render_template("template_marketplace.html")


@app.route("/template/docs")
def docs_template():
    return render_template("template_docs.html")


@app.route("/template/password")
def password_template():
    return render_template("template_password.html")


@app.route("/template/invoice")
def invoice_template():
    return render_template("template_invoice.html")


@app.route("/admin/template-preview", methods=["POST"])
def admin_template_preview():
    raw_html = request.form.get("body", "")
    safe_html = _sanitize_rich_html(raw_html)
    return jsonify({"preview_html": safe_html})

@app.route('/admin/stats')
def admin_stats():
    total_users, total_profiles, total_contacts = db.get_statistics()
    users = db.get_recent_users()
    return render_template('admin.html',
                           total_users=total_users,
                           total_profiles=total_profiles,
                           total_contacts=total_contacts,
                           users=users)

if __name__ == '__main__':
    print("🚀 Фишинг-симулятор запущен")
    print(f"🌐 Доступен по адресу: http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)