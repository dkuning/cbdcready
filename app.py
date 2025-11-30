# app.py
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import pyotp
import os
import modules.legalDetails as legalDetails
import logging


app = Flask(__name__, static_folder='static', template_folder='templates')

# Получаем секретный ключ из переменной окружения
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'JROFFXC5EVY6N2DY')

# Получаем TOTP-секрет из переменной окружения
TOTP_SECRET = os.environ.get('TOTP_SECRET', 'DS4LZV52ZI3QNN72')

# Настройка логирования
LOG_DIR = './logs'
LOG_FILE = os.path.join(LOG_DIR, 'cbdcReadyApp.log')
logger = logging.getLogger('cbdcReadyApp')
logger.setLevel(logging.INFO)

def generate_totp():
    totp = pyotp.TOTP(TOTP_SECRET)
    return totp.now()

def verify_totp(token):
    totp = pyotp.TOTP(TOTP_SECRET)
    return totp.verify(token)

@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
def auth():
    token = request.form.get('otp')
    if verify_totp(token):
        session['logged_in'] = True
        return redirect(url_for('index'))
    else:
        # Перенаправляем обратно на login с параметром ошибки
        return redirect(url_for('login', error='invalid'))

def is_logged_in():
    return session.get('logged_in', False)

@app.route('/check_inn', methods=['GET'])
def check_inn():
    if not is_logged_in():
        return jsonify({"error": "Access denied. Please log in"}), 401

    return legalDetails.get_data(request.args.get('inn'))

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
    logger.info(f"Приложение запущено на порту {port}")