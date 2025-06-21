import re
import os
import sys
from datetime import datetime
from pathlib import Path

# 进度条支持
try:
    from tqdm import tqdm

    has_tqdm = True
except ImportError:
    has_tqdm = False


def format_question_block(block, new_number=None, question_type=None):
    """处理单个题目块，添加锚点和标记功能"""
    if not block.strip():
        return "", "", "", ""

    lines = [line.rstrip() for line in block.splitlines() if line.strip()]

    # 提取原始编号
    original_number = ""
    if lines and re.match(r'^\d+\.', lines[0]):
        original_number = re.match(r'^(\d+)\.', lines[0]).group(1)

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
        correct_letters = [letter.strip() for letter in answer_line.split(":")[1].split() if letter.strip()]

    # 判断题特殊处理
    if q_type == "judge":
        options = ["A. 正确", "B. 错误"]
        if correct_letters:
            option_correct = [correct_letters[0] == "A", correct_letters[0] == "B"]
    else:
        # 处理选择题选项
        while i < len(lines) and re.match(r'^[A-D]\.?$', lines[i]):
            letter = lines[i].replace('.', '')
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

    # 重新编号第一行
    if new_number is not None and question_desc:
        question_desc[0] = re.sub(r'^\d+\.', f'{new_number}.', question_desc[0])

    # 生成唯一锚点ID
    anchor_id = f"q{new_number}" if new_number else f"q{original_number}"

    # 构建HTML
    html_result = []
    # 添加题型类名
    question_class = "question-block"
    if q_type == "single":
        question_class += " single-choice"
    elif q_type == "multi":
        question_class += " multi-choice"
    elif q_type == "judge":
        question_class += " judge-question"

    html_result.append(f'<div class="{question_class}" id="{anchor_id}">')
    html_result.append('  <div class="question-header">')
    html_result.append(f'    <div class="question-marker" onclick="toggleBookmark(\'{anchor_id}\')">📌</div>')
    for desc in question_desc:
        html_result.append(f'    <div class="question-desc">{desc}</div>')
    html_result.append('  </div>')

    if options:  # 只有有选项时才添加选项部分
        html_result.append('  <div class="options">')
        for idx, option in enumerate(options):
            # 所有选项初始样式相同，使用data-correct属性标记正确答案
            html_result.append(
                f'    <div class="option" data-correct="{str(option_correct[idx]).lower()}" data-letter="{option[0]}">{option}</div>')
        html_result.append('  </div>')

        # 添加按钮容器（确认在左，重置在右）
        html_result.append('  <div style="display: flex; justify-content: space-between; margin-top: 10px;">')
        html_result.append(
            f'    <button class="check-btn" onclick="checkSingleAnswer(\'{anchor_id}\')">确认答案</button>')
        html_result.append(f'    <button class="reset-btn" onclick="resetQuestion(\'{anchor_id}\')">重置</button>')
        html_result.append('  </div>')

    # 添加反馈区域
    html_result.append('  <div class="answer-feedback" style="display:none;"></div>')

    if answer_line:
        html_result.append(f'  <div class="correct-answer" style="display:none;">{answer_line}</div>')
    html_result.append('</div>')

    return "\n".join(html_result), original_number, q_type, anchor_id


def process_folder(input_folder, output_html):
    """处理文件夹中的所有txt文件"""
    txt_files = [os.path.join(input_folder, f) for f in os.listdir(input_folder)
                 if f.endswith('.txt') and os.path.isfile(os.path.join(input_folder, f))]

    if not txt_files:
        print(f"错误: 文件夹 {input_folder} 中没有找到任何txt文件")
        return

    single_choice_blocks = []
    multi_choice_blocks = []
    judge_blocks = []
    total_questions = 0
    single_counter = 1
    multi_counter = 1
    judge_counter = 1
    bookmark_js = []

    # 处理每个文件
    for txt_file in txt_files:
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"读取文件 {txt_file} 出错: {e}")
            continue

        blocks = re.split(r'(?=\n\d+\.)', content)
        blocks = [b for b in blocks if b.strip()]

        print(f"处理文件: {os.path.basename(txt_file)} (共 {len(blocks)} 题)")

        for block in tqdm(blocks) if has_tqdm else blocks:
            # 先检测题目类型
            _, _, q_type, _ = format_question_block(block)

            # 根据类型使用不同的计数器
            if q_type == "single":
                html_block, original_num, q_type, anchor_id = format_question_block(block, single_counter, q_type)
                single_choice_blocks.append(html_block)
                single_counter += 1
            elif q_type == "multi":
                html_block, original_num, q_type, anchor_id = format_question_block(block, multi_counter, q_type)
                multi_choice_blocks.append(html_block)
                multi_counter += 1
            elif q_type == "judge":
                html_block, original_num, q_type, anchor_id = format_question_block(block, judge_counter, q_type)
                judge_blocks.append(html_block)
                judge_counter += 1
            else:
                # 默认作为单选题处理
                html_block, original_num, q_type, anchor_id = format_question_block(block, single_counter, "single")
                single_choice_blocks.append(html_block)
                single_counter += 1

            if html_block:
                bookmark_js.append(f'"{anchor_id}":false')

        total_questions += len(blocks)

    # 生成完整HTML
    html_content = f"""<!DOCTYPE html> 
<html lang="zh-CN"> 
<head> 
  <meta charset="UTF-8"> 
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"> 
  <title>习思想选择合集</title> 
  <style> 
    body {{  
      font-family: "Microsoft YaHei", sans-serif;  
      line-height: 1.6;  
      max-width: 800px;  
      margin: 0 auto;  
      padding: 20px;  
      background-color: #f5f5f5;  
      padding-right: 280px; 
    }} 
    .question-block {{  
      background-color: white;  
      border-radius: 8px;  
      padding: 15px;  
      margin-bottom: 20px;  
      box-shadow: 0 2px 5px rgba(0,0,0,0.1);  
      position: relative; 
    }} 
    .question-header {{  
      margin-bottom: 10px;  
      font-weight: bold;  
      padding-left: 30px; 
    }} 
    .question-marker {{ 
      position: absolute; 
      left: 10px; 
      top: 10px; 
      cursor: pointer; 
      font-size: 1.2em; 
      user-select: none; 
    }} 
    .question-marker.marked {{  
      color: gold;  
      text-shadow: 0 0 2px black;  
    }} 
    .options {{ margin-left: 20px; }} 
    .option {{  
      margin-bottom: 5px;  
      padding: 5px; 
      border-radius: 4px; 
      cursor: pointer; 
      transition: all 0.2s; 
    }} 
    .option:hover {{ 
      background-color: #f0f0f0; 
    }} 
    .option.selected {{ 
      background-color: #e0e0e0 !important; 
    }} 
    .option.correct {{ 
      background-color: #e8f5e9 !important; 
      color: #2e7d32; 
      font-weight: bold; 
    }} 
    .option.wrong {{ 
      background-color: #ffebee !important; 
      color: #c62828; 
      text-decoration: line-through; 
    }} 
    .correct-answer {{  
      margin-top: 10px;  
      padding-top: 10px;  
      border-top: 1px dashed #ccc;  
      font-style: italic;  
      color: #2c3e50; 
      display: none; 
    }} 
    .answer-feedback {{ 
      margin-top: 10px; 
      font-weight: bold; 
      display: none; 
    }} 
    .check-btn {{ 
      padding: 5px 10px; 
      background-color: #1e88e5; 
      color: white; 
      border: none; 
      border-radius: 3px; 
      cursor: pointer; 
    }} 
    .check-btn:hover {{ 
      background-color: #1565c0; 
    }} 
    .reset-btn {{ 
      padding: 5px 10px; 
      background-color: #757575; 
      color: white; 
      border: none; 
      border-radius: 3px; 
      cursor: pointer; 
    }} 
    .reset-btn:hover {{ 
      background-color: #616161; 
    }} 
    h1 {{ text-align: center; color: #2c3e50; }} 
    h2 {{ 
      color: #1e88e5; 
      margin-top: 30px; 
      border-bottom: 1px solid #eee; 
      padding-bottom: 5px; 
      scroll-margin-top: 20px; 
    }} 
    .info-bar {{  
      text-align: center;  
      margin-bottom: 20px;  
      font-size: 0.9em;  
      color: #7f8c8d;  
    }} 
    .nav-panel {{ 
      position: fixed; 
      top: 20px; 
      right: 20px; 
      background: white; 
      padding: 10px; 
      border-radius: 5px; 
      box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
      max-height: 80vh; 
      overflow-y: auto; 
      width: 250px; 
      z-index: 1000; 
    }} 
    .nav-buttons {{ 
      display: flex; 
      justify-content: center; 
      gap: 10px; 
      margin-bottom: 15px; 
      flex-wrap: wrap; 
    }} 
    .bookmark-list {{ 
      max-height: 300px; 
      overflow-y: auto; 
      margin-top: 10px; 
    }} 
    .bookmark-item {{ 
      padding: 5px; 
      cursor: pointer; 
      border-bottom: 1px solid #eee; 
      display: flex; 
      justify-content: space-between; 
    }} 
    .bookmark-item:hover {{ 
      background-color: #f0f0f0; 
    }} 
    button {{ 
      padding: 5px 10px; 
      background-color: #1e88e5; 
      color: white; 
      border: none; 
      border-radius: 3px; 
      cursor: pointer; 
    }} 
    button:hover {{ 
      background-color: #1565c0; 
    }} 
    #searchInput {{ 
      width: 100%; 
      padding: 5px; 
      margin-bottom: 10px; 
      box-sizing: border-box; 
    }} 
    .section-nav {{ 
      margin-bottom: 15px; 
    }} 
    .section-nav h3 {{ 
      margin-bottom: 5px; 
      color: #1e88e5; 
    }} 
    .section-nav-list {{ 
      list-style: none; 
      padding-left: 10px; 
    }} 
    .section-nav-list li {{ 
      margin-bottom: 5px; 
      cursor: pointer; 
      color: #1e88e5; 
    }} 
    .section-nav-list li:hover {{ 
      text-decoration: underline; 
    }} 
    .toggle-answers-btn {{ 
      background-color: #43a047; 
    }} 
    .toggle-answers-btn:hover {{ 
      background-color: #2e7d32; 
    }} 
    .clear-bookmarks-btn {{ 
      background-color: #e53935; 
    }} 
    .clear-bookmarks-btn:hover {{ 
      background-color: #c62828; 
    }} 
    .correct-highlight {{ 
      background-color: #ffebee !important; 
      color: #c62828 !important; 
      font-weight: bold !important; 
      border-left: 3px solid #c62828; 
      padding-left: 8px; 
    }}
    /* 跳转高亮效果 */
    .question-block.highlight {{
        animation: highlight-fade 2s ease-out;
        box-shadow: 0 0 0 2px #1e88e5;
    }}
    @keyframes highlight-fade {{
        0% {{
            box-shadow: 0 0 0 6px rgba(30, 136, 229, 0.5);
            transform: scale(1.02);
        }}
        100% {{
            box-shadow: 0 0 0 2px rgba(30, 136, 229, 0);
            transform: scale(1);
        }}
    }}

    /* 移动端适配 */ 
    @media (max-width: 768px) {{ 
      body {{ 
        padding-right: 20px; 
      }} 
      .nav-panel {{ 
        position: static; 
        width: auto; 
        max-height: none; 
        margin-bottom: 20px; 
      }} 
      .question-header {{ 
        padding-left: 30px; 
      }} 
    }} 

    /* 移动端菜单按钮 */ 
    .mobile-menu-btn {{ 
      display: none; 
      position: fixed; 
      top: 10px; 
      right: 10px; 
      background: #1e88e5; 
      color: white; 
      border: none; 
      border-radius: 50%; 
      width: 40px; 
      height: 40px; 
      font-size: 20px; 
      z-index: 1001; 
    }} 

    @media (max-width: 768px) {{ 
      .mobile-menu-btn {{ 
        display: block; 
      }} 
      .nav-panel {{ 
        display: none; 
        position: fixed; 
        top: 60px; 
        right: 10px; 
        width: calc(100% - 20px); 
        max-height: calc(100vh - 80px); 
      }} 
      .nav-panel.show {{ 
        display: block; 
      }} 
    }} 
  </style> 
</head> 
<body> 
  <button class="mobile-menu-btn" onclick="toggleMobileMenu()">☰</button> 

  <div class="nav-panel" id="navPanel"> 
    <div class="nav-buttons"> 
      <button onclick="scrollToTop()">顶部</button> 
      <button onclick="scrollToBottom()">底部</button>
      <button class="toggle-answers-btn" id="toggleAnswersBtn" onclick="toggleAllAnswers()">显示所有答案</button>
      <button class="clear-bookmarks-btn" onclick="clearAllBookmarks()">清除所有标记</button>
    </div> 

    <!-- 题目分类导航 -->
    <div class="section-nav">
      <h3>题目分类</h3>
      <ul class="section-nav-list">
        <li onclick="scrollToSection('single-choice-section')">一、单选题 ({len(single_choice_blocks)})</li>
        <li onclick="scrollToSection('multi-choice-section')">二、多选题 ({len(multi_choice_blocks)})</li>
        <li onclick="scrollToSection('judge-section')">三、判断题 ({len(judge_blocks)})</li>
      </ul>
    </div>

    <h3>题目导航</h3> 
    <div> 
      <input type="text" id="searchInput" placeholder="搜索题目..." oninput="searchQuestions()"> 
    </div> 
    <h3>标记题目</h3> 
    <div class="bookmark-list" id="bookmarkList"> 
      <div style="color:#999; text-align:center;">暂无标记题目</div> 
    </div> 
  </div> 

  <h1>习思想选择合集</h1> 
  <div class="info-bar"> 
    共 {total_questions} 道题目 | 作者：2167143949@qq.com | 生成时间: {datetime.now().strftime('%Y.%m')} 
  </div> 

  <h2 id="single-choice-section">一、单选题</h2> 
  {"".join(single_choice_blocks)} 
  <h2 id="multi-choice-section">二、多选题</h2> 
  {"".join(multi_choice_blocks)} 
  <h2 id="judge-section">三、判断题</h2> 
  {"".join(judge_blocks)} 

  <script> 
    // 存储标记状态 
    let bookmarks = loadBookmarks() || {{{','.join(bookmark_js)}}}; 
    // 存储每道题的正确选项 
    const correctAnswers = {{}}; 
    // 存储用户选择的答案 
    const userSelections = {{}}; 
    // 跟踪答案显示状态
    let answersVisible = false;

    // 从本地存储加载书签
    function loadBookmarks() {{
      const saved = localStorage.getItem('questionBookmarks');
      return saved ? JSON.parse(saved) : null;
    }}

    // 保存书签到本地存储
    function saveBookmarks() {{
      localStorage.setItem('questionBookmarks', JSON.stringify(bookmarks));
    }}

    // 初始化题目数据 
    document.addEventListener('DOMContentLoaded', function() {{ 
      // 初始化标记状态 
      Object.keys(bookmarks).forEach(id => {{ 
        if (bookmarks[id]) {{ 
          const marker = document.querySelector(`#${{id}} .question-marker`); 
          if (marker) marker.classList.add('marked'); 
        }} 
      }}); 
      updateBookmarkList(); 

      // 移动端检测 
      if (window.innerWidth <= 768) {{ 
        document.body.style.paddingRight = '20px'; 
      }} 

      // 设置正确选项和用户选择 
      document.querySelectorAll('.question-block').forEach(block => {{ 
        const id = block.id; 
        const correctOptions = []; 
        const options = block.querySelectorAll('.option'); 

        // 收集正确答案 
        options.forEach(option => {{ 
          if (option.dataset.correct === 'true') {{ 
            correctOptions.push(option.dataset.letter); 
          }} 
        }}); 

        correctAnswers[id] = correctOptions; 
        userSelections[id] = []; 

        // 添加选项点击事件 
        options.forEach(option => {{ 
          option.addEventListener('click', function() {{ 
            const questionId = this.closest('.question-block').id; 
            const optionLetter = this.dataset.letter; 

            // 获取当前题目的所有选项
            const currentOptions = this.closest('.question-block').querySelectorAll('.option');

            // 如果是单选题或判断题，先清除所有选中状态
            if (block.classList.contains('single-choice') || block.classList.contains('judge-question')) {{
              currentOptions.forEach(opt => opt.classList.remove('selected'));
              userSelections[questionId] = [];
            }}

            // 切换选中状态
            if (this.classList.contains('selected')) {{
              this.classList.remove('selected');
              const index = userSelections[questionId].indexOf(optionLetter);
              if (index !== -1) {{
                userSelections[questionId].splice(index, 1);
              }}
            }} else {{
              this.classList.add('selected');
              userSelections[questionId].push(optionLetter);
            }}
          }}); 
        }}); 
      }}); 
    }}); 

    // 滚动到指定分类
    function scrollToSection(sectionId) {{
      const element = document.getElementById(sectionId);
      if (element) {{
        element.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      }}
    }}

    // 检查单个题目答案 
    function checkSingleAnswer(questionId) {{ 
      const block = document.getElementById(questionId); 
      const userAnswer = [...userSelections[questionId]]; // 复制数组
      const correctAnswer = [...correctAnswers[questionId]]; // 复制数组
      const feedback = block.querySelector('.answer-feedback'); 
      const correctAnswerDiv = block.querySelector('.correct-answer'); 
      const options = block.querySelectorAll('.option'); 

      // 重置所有选项样式 
      options.forEach(opt => {{ 
        opt.classList.remove('selected', 'correct', 'wrong'); 
      }}); 

      // 标记正确答案和错误答案 
      options.forEach(option => {{ 
        if (option.dataset.correct === 'true') {{ 
          option.classList.add('correct'); // 所有正确答案都标记为绿色
        }} 
        if (userSelections[questionId].includes(option.dataset.letter) && 
            option.dataset.correct !== 'true') {{ 
          option.classList.add('wrong'); // 用户选中的错误答案标记为红色
        }} 
      }}); 

      // 检测题型
      const isMultiChoice = block.classList.contains('multi-choice');
      const isJudgeQuestion = block.classList.contains('judge-question');

      let isCorrect = false;

      if (isMultiChoice) {{
        // 多选题：必须满足两个条件：
        // 1. 用户选择的选项数量等于正确答案数量
        // 2. 用户选择的所有选项都是正确答案
        isCorrect = userAnswer.length === correctAnswer.length && 
                    userAnswer.every(letter => correctAnswer.includes(letter));
      }} else if (isJudgeQuestion) {{
        // 判断题：直接比较第一个选项
        isCorrect = userAnswer.length === 1 && userAnswer[0] === correctAnswer[0];
      }} else {{
        // 单选题：直接比较第一个选项
        isCorrect = userAnswer.length === 1 && userAnswer[0] === correctAnswer[0];
      }}

      if (isCorrect) {{ 
        feedback.textContent = '✓ 回答正确'; 
        feedback.style.color = 'green'; 
      }} else {{ 
        feedback.textContent = '✗ 回答错误'; 
        feedback.style.color = 'red'; 
      }} 

      // 清空用户选择
      userSelections[questionId] = [];

      feedback.style.display = 'block'; 
      correctAnswerDiv.style.display = 'block'; 
    }} 

    // 重置题目状态
    function resetQuestion(questionId) {{
      const block = document.getElementById(questionId);
      const options = block.querySelectorAll('.option');
      const feedback = block.querySelector('.answer-feedback');
      const correctAnswerDiv = block.querySelector('.correct-answer');

      // 清除所有选项样式
      options.forEach(opt => {{
          opt.classList.remove('selected', 'correct', 'wrong', 'correct-highlight');
      }});

      // 清除用户选择记录
      userSelections[questionId] = [];

      // 隐藏反馈和正确答案
      feedback.style.display = 'none';
      correctAnswerDiv.style.display = 'none';
    }}

    // 跳转到指定题目 
    function scrollToQuestion(id) {{ 
      const element = document.getElementById(id); 
      if (element) {{ 
        // 移除之前的高亮
        document.querySelectorAll('.question-block.highlight').forEach(el => {{
            el.classList.remove('highlight');
        }});

        // 添加新的高亮
        element.classList.add('highlight');

        // 2秒后自动移除高亮
        setTimeout(() => {{
            element.classList.remove('highlight');
        }}, 2000);

        element.scrollIntoView({{ behavior: 'smooth', block: 'center' }}); 
      }} 
    }} 

    // 标记/取消标记题目 
    function toggleBookmark(id) {{ 
      const marker = document.querySelector(`#${{id}} .question-marker`); 
      bookmarks[id] = !bookmarks[id]; 

      if (bookmarks[id]) {{ 
        marker.classList.add('marked'); 
      }} else {{ 
        marker.classList.remove('marked'); 
      }} 

      updateBookmarkList(); 
      saveBookmarks(); // 保存到本地存储
    }} 

    // 更新标记列表 
    function updateBookmarkList() {{ 
      const list = document.getElementById('bookmarkList'); 
      list.innerHTML = ''; 

      let hasBookmarks = false; 

      Object.keys(bookmarks).forEach(id => {{ 
        if (bookmarks[id]) {{ 
          hasBookmarks = true; 
          const question = document.getElementById(id); 
          if (question) {{ 
            const title = question.querySelector('.question-desc').textContent.trim(); 
            const item = document.createElement('div'); 
            item.className = 'bookmark-item'; 
            item.innerHTML = `${{title.substring(0, 30)}}${{title.length > 30 ? '...' : ''}} <button onclick="scrollToQuestion('${{id}}')">跳转</button>`; 
            list.appendChild(item); 
          }} 
        }} 
      }}); 

      if (!hasBookmarks) {{ 
        list.innerHTML = '<div style="color:#999; text-align:center;">暂无标记题目</div>'; 
      }} 
    }} 

    // 清除所有标记
    function clearAllBookmarks() {{
      if (confirm('确定要清除所有标记题目吗？')) {{
        // 重置所有标记状态
        Object.keys(bookmarks).forEach(id => {{
          bookmarks[id] = false;
          const marker = document.querySelector(`#${{id}} .question-marker`);
          if (marker) marker.classList.remove('marked');
        }});

        updateBookmarkList();
        saveBookmarks();
      }}
    }}

    // 搜索题目 
    function searchQuestions() {{ 
      const searchTerm = document.getElementById('searchInput').value.toLowerCase(); 
      const blocks = document.querySelectorAll('.question-block'); 

      blocks.forEach(block => {{ 
        const text = block.textContent.toLowerCase(); 
        if (searchTerm === '' || text.includes(searchTerm)) {{ 
          block.style.display = 'block'; 
        }} else {{ 
          block.style.display = 'none'; 
        }} 
      }}); 
    }} 

    // 滚动到顶部 
    function scrollToTop() {{ 
      window.scrollTo({{ top: 0, behavior: 'smooth' }}); 
    }} 

    // 滚动到底部 
    function scrollToBottom() {{ 
      window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }}); 
    }} 

    // 移动端菜单切换 
    function toggleMobileMenu() {{ 
      const panel = document.getElementById('navPanel'); 
      panel.classList.toggle('show'); 
    }} 

    // 切换所有答案显示状态
    function toggleAllAnswers() {{
      const btn = document.getElementById('toggleAnswersBtn');
      answersVisible = !answersVisible;

      document.querySelectorAll('.question-block').forEach(block => {{
        const correctAnswerDiv = block.querySelector('.correct-answer');
        const options = block.querySelectorAll('.option');

        if (answersVisible) {{
          // 显示答案并高亮正确选项
          if (correctAnswerDiv) correctAnswerDiv.style.display = 'block';
          options.forEach(option => {{
            if (option.dataset.correct === 'true') {{
              option.classList.add('correct-highlight');
            }}
          }});
        }} else {{
          // 隐藏答案并取消高亮
          if (correctAnswerDiv) correctAnswerDiv.style.display = 'none';
          options.forEach(option => {{
            option.classList.remove('correct-highlight');
          }});
        }}
      }});

      btn.textContent = answersVisible ? '隐藏所有答案' : '显示所有答案';
    }}
  </script> 
</body> 
</html> 
"""

    # 写入文件
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n处理完成! 共处理 {len(txt_files)} 个文件")
    print(f"一、单选题: {len(single_choice_blocks)} 道 (编号: 1-{single_counter - 1})")
    print(f"二、多选题: {len(multi_choice_blocks)} 道 (编号: 1-{multi_counter - 1})")
    print(f"三、判断题: {len(judge_blocks)} 道 (编号: 1-{judge_counter - 1})")
    print(f"HTML文件已保存到: {os.path.abspath(output_html)}")


def select_input_folder():
    """选择输入文件夹"""
    print("\n请输入包含题目txt文件的文件夹路径:")
    print("示例: E:/my_questions")
    folder_path = input("文件夹路径: ").strip()
    return folder_path.replace('\\', '/')


if __name__ == "__main__":
    print("习思想选择题合集生成工具 v1.5")
    print("=" * 50)
    print("功能说明:")
    print("1. 自动处理文件夹中的所有txt文件")
    print("2. 题目标记与跳转功能")
    print("3. 题目搜索功能")
    print("4. 按题型分类显示")
    print("5. 每题独立确认答案功能")
    print("6. 题目重置功能")
    print("7. 标记状态本地保存功能")
    print("8. 题目分类导航功能")
    print("9. 一键显示/隐藏所有答案功能")
    print("10. 一键清除所有标记题目功能")
    print("=" * 50)

    input_folder = select_input_folder()
    if not os.path.isdir(input_folder):
        print("错误: 指定的路径不是文件夹或不存在")
        sys.exit(1)

    default_output = os.path.join(input_folder, "习思想选择合集.html")
    output_html = input(f"输出HTML文件路径(默认: {default_output}): ").strip() or default_output

    process_folder(input_folder, output_html)

    if sys.platform.startswith('win'):
        input("\n按Enter键退出...")