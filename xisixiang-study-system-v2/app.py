'''
@Project: app.py
@Author: 郗禄辉
@Date: 2025/6/22 14:10
'''

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
import os
import re
from datetime import datetime
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 数据库模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 初始化数据库
with app.app_context():
    db.create_all()
    # 创建默认管理员
    if not User.query.filter_by(username=app.config['ADMIN_USERNAME']).first():
        admin = User(
            username=app.config['ADMIN_USERNAME'],
            display_name=app.config['ADMIN_DISPLAY_NAME'],
            password=generate_password_hash(app.config['ADMIN_PASSWORD'])
        )
        db.session.add(admin)
        db.session.commit()

def get_type_label(q_type):
    """获取题目类型标签"""
    return {
        "single": "单选题",
        "multi": "多选题",
        "judge": "判断题"
    }.get(q_type, "单选题")

def parse_question_block(block, new_number=None, question_type=None):
    """解析单个题目块"""
    if not block.strip():
        return None

    lines = [line.rstrip() for line in block.splitlines() if line.strip()]

    # 提取原始编号（处理各种格式：1. 1、 1 ）
    original_number = ""
    if lines and re.match(r'^\d+[\.、\s]', lines[0]):
        original_number = re.match(r'^(\d+)[\.、\s]', lines[0]).group(1)

    # 提取题目类型
    detected_type = ""
    question_desc = []
    i = 0
    while i < len(lines) and not re.match(r'^[A-D]\.?$', lines[i]) and not lines[i].startswith("正确答案"):
        if lines[i] and not lines[i].startswith("答案解释"):
            if "单选题" in lines[i]:
                detected_type = "single"
            elif "多选题" in lines[i]:
                detected_type = "multi"
            elif "判断题" in lines[i]:
                detected_type = "judge"
            question_desc.append(lines[i])
        i += 1

    # 使用传入的类型（如果提供），否则使用检测到的类型
    q_type = question_type if question_type else detected_type

    # 处理选项
    options = []
    option_correct = []
    correct_letters = []
    answer_line = next((line for line in lines if line.startswith("正确答案")), "")

    if answer_line:
        correct_letters = [letter.strip().upper() for letter in answer_line.split(":")[1].split() if letter.strip()]

    # 判断题特殊处理
    if q_type == "judge":
        options = ["A. 正确", "B. 错误"]
        if correct_letters:
            option_correct = [correct_letters[0] == "A", correct_letters[0] == "B"]
    else:
        # 处理选择题选项
        while i < len(lines) and re.match(r'^[A-D]\.?$', lines[i]):
            letter = lines[i].replace('.', '').upper()
            i += 1
            if i < len(lines) and lines[i] == '.':
                i += 1

            content_lines = []
            while i < len(lines) and not re.match(r'^[A-D]\.?$', lines[i]) and not lines[i].startswith("正确答案"):
                if lines[i] and lines[i] != '.':
                    content_lines.append(lines[i].strip())
                i += 1

            option_content = ''.join(content_lines).strip()
            if option_content:
                options.append(f"{letter}. {option_content}")
                option_correct.append(letter in correct_letters)

    # 重新编号第一行（使用统一编号）
    if new_number is not None and question_desc:
        question_desc[0] = re.sub(r'^\d+[\.、\s]', f'{new_number}. ', question_desc[0])

    # 生成唯一锚点ID
    anchor_id = f"q{new_number}" if new_number else f"q{original_number}"

    return {
        'desc': "\n".join(question_desc),
        'type': q_type,
        'options': options,
        'correct_answers': correct_letters,
        'answer_line': answer_line,
        'anchor_id': anchor_id,
        'option_correct': option_correct
    }

def generate_question_html(question, qid):
    """生成题目HTML"""
    question_id = question['anchor_id']
    type_class = {
        "single": "single-choice",
        "multi": "multi-choice",
        "judge": "judge-question"
    }.get(question["type"], "single-choice")

    html = [
        f'<div class="question-block {type_class}" id="{question_id}">',
        '  <div class="question-header">',
        f'    <span class="question-type">{get_type_label(question["type"])}</span>',
        f'    <div class="question-marker" onclick="toggleBookmark(\'{question_id}\')">📌</div>',
    ]

    # 添加题目描述
    for desc in question['desc'].split('\n'):
        html.append(f'    <div class="question-desc">{desc}</div>')

    html.extend([
        '  </div>',
        '  <div class="options">'
    ])

    # 判断题特殊处理
    if question["type"] == "judge":
        html.extend([
            '    <div class="judge-options">',
            f'      <div class="judge-option" data-letter="A" onclick="selectOption(this)">正确</div>',
            f'      <div class="judge-option" data-letter="B" onclick="selectOption(this)">错误</div>',
            '    </div>'
        ])
    else:
        # 选择题选项
        for idx, option in enumerate(question['options']):
            html.append(
                f'    <div class="option" data-correct="{str(question["option_correct"][idx]).lower()}" '
                f'data-letter="{option[0]}" onclick="selectOption(this)">{option}</div>'
            )

    html.extend([
        '  </div>',
        '  <div class="question-footer">',
        f'    <button class="check-btn" onclick="checkAnswer(\'{question_id}\')">确认答案</button>',
        f'    <button class="reset-btn" onclick="resetQuestion(\'{question_id}\')">重置</button>',
        '  </div>',
        '  <div class="answer-feedback" style="display:none;"></div>'
    ])

    if question['answer_line']:
        html.append(f'  <div class="correct-answer" style="display:none;">{question["answer_line"]}</div>')

    html.append('</div>')

    return '\n'.join(html)

def load_questions_from_file(filepath):
    """从文件加载题目并按统一编号排序（保留题型分类）"""
    if not os.path.exists(filepath):
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.split(r'(?=\n\d+[\.、\s])', content)
    questions = []
    question_counter = 1  # 统一编号计数器

    for block in blocks:
        if not block.strip() or "此题未答" in block:
            continue

        # 先检测题目类型
        question_data = parse_question_block(block)
        if not question_data:
            continue

        # 使用统一编号
        question_data = parse_question_block(block, question_counter, question_data['type'])
        questions.append({
            'number': question_counter,
            'type': question_data['type'],
            'html': generate_question_html(question_data, question_counter)
        })
        question_counter += 1

    return questions

# 路由
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    questions_data = load_questions_from_file(app.config['QUESTIONS_FILE'])

    # 分类统计
    single_count = len([q for q in questions_data if q['type'] == 'single'])
    multi_count = len([q for q in questions_data if q['type'] == 'multi'])
    judge_count = len([q for q in questions_data if q['type'] == 'judge'])
    total_count = len(questions_data)

    # 提取HTML内容
    questions = [q['html'] for q in questions_data]

    return render_template('index.html',
                         questions=questions,
                         single_count=single_count,
                         multi_count=multi_count,
                         judge_count=judge_count,
                         total_count=total_count,
                         current_time=datetime.now().strftime('%Y.%m'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['display_name'] = user.display_name
            return redirect(url_for('index'))

        return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# API接口
@app.route('/api/bookmarks', methods=['GET'])
def get_bookmarks():
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401

    bookmarks = Bookmark.query.filter_by(user_id=session['user_id']).all()
    return jsonify({
        'bookmarks': [b.question_id for b in bookmarks]
    })

@app.route('/api/bookmark', methods=['POST'])
def toggle_bookmark():
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401

    data = request.get_json()
    bookmark = Bookmark.query.filter_by(
        user_id=session['user_id'],
        question_id=data['question_id']
    ).first()

    if bookmark:
        db.session.delete(bookmark)
        db.session.commit()
        return jsonify({'status': 'removed'})
    else:
        new_bookmark = Bookmark(
            user_id=session['user_id'],
            question_id=data['question_id'],
            created_at=datetime.utcnow()
        )
        db.session.add(new_bookmark)
        db.session.commit()
        return jsonify({'status': 'added'})

@app.route('/api/check_answer', methods=['POST'])
def check_answer():
    """检查答案是否正确"""
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401

    data = request.get_json()
    question_id = data['question_id']
    user_answer = data.get('user_answer', [])

    # 从问题数据中获取正确答案
    questions = load_questions_from_file(app.config['QUESTIONS_FILE'])
    question_data = None

    # 查找对应的问题
    for q in questions:
        if f'id="{question_id}"' in q['html']:
            # 从HTML中解析出正确答案
            html = q['html']
            correct_div_start = html.find('correct-answer')
            if correct_div_start != -1:
                correct_div = html[correct_div_start:].split('>')[1].split('<')[0]
                correct_answers = []
                if '正确答案' in correct_div:
                    correct_answers = [a.strip().upper() for a in correct_div.split(':')[1].split() if a.strip()]
            else:
                correct_answers = []

            # 确定题目类型
            question_data = {
                'type': q['type'],
                'correct_answers': correct_answers
            }
            break

    if not question_data:
        return jsonify({'error': '题目未找到'}), 404

    # 统一转为大写字母比较
    user_answer = [a.upper() for a in user_answer]
    correct_answers = [a.upper() for a in question_data['correct_answers']]

    # 判断答案是否正确
    is_correct = False
    if question_data['type'] == 'multi':
        # 多选题：必须完全匹配所有正确答案
        is_correct = (len(user_answer) == len(correct_answers) and
                     set(user_answer) == set(correct_answers))
    else:
        # 单选题和判断题：只需匹配第一个正确答案
        is_correct = len(user_answer) == 1 and user_answer[0] == correct_answers[0]

    return jsonify({
        'is_correct': is_correct,
        'correct_answers': correct_answers,
        'question_type': question_data['type']
    })

if __name__ == '__main__':
    app.run(debug=True)