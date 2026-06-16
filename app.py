from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import json
import random
import re
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
# 引入OpenAI客户端
from openai import OpenAI

# 加载环境变量
load_dotenv()

# 初始化AI客户端（兼容OpenAI接口）
client = OpenAI(
    api_key=os.getenv("AI_API_KEY"),
    base_url=os.getenv("AI_BASE_URL")
)
AI_MODEL = os.getenv("AI_MODEL")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ===================== 数据库模型 =====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(50), unique=True, nullable=False)
    nickname = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)

    # 角色 & 游戏基础信息
    gender = db.Column(db.String(10), default="female")
    role_name = db.Column(db.String(50), default="")
    x_name = db.Column(db.String(50), default="")
    x_personality = db.Column(db.String(100), default="")

    # 游戏天数 & 阶段（0:晨间 1:日间 2:晚间 3:深夜）
    current_day = db.Column(db.Integer, default=1)
    current_stage = db.Column(db.Integer, default=0)

    # 4位可攻略嘉宾好感度 0-100
    like_ex = db.Column(db.Integer, default=50)    # 前任
    like_a = db.Column(db.Integer, default=50)      # 嘉宾A
    like_b = db.Column(db.Integer, default=50)      # 嘉宾B
    like_c = db.Column(db.Integer, default=50)      # 嘉宾C

    # 嘉宾名字（自动生成后存储）
    guest_names = db.Column(db.Text, default="[]")

    # 依恋型人格数据
    attach_safe = db.Column(db.Integer, default=45)
    attach_anxious = db.Column(db.Integer, default=30)
    attach_avoid = db.Column(db.Integer, default=15)
    attach_mix = db.Column(db.Integer, default=10)

    # 心动短信列表 JSON
    messages = db.Column(db.Text, default="[]")

# 启动时创建数据表
with app.app_context():
    db.create_all()

# ===================== 全局常量 =====================
WEEK_LIST = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
MAX_GAME_DAY = 21
STAGE_NAMES = ["晨间宿舍", "白天录制", "晚餐聚会", "深夜短信时间"]

# 【新增：21天固定节目事件表】
DAY_EVENT = {
    1: "入住小屋、初次见面",
    2: "共同准备早餐",
    3: "第一次心动短信",
    4: "随机分组活动",
    5: "泳池派对",
    6: "匿名问题箱",
    7: "第一次正式约会",
    8: "约会后的返程夜晚",
    9: "前任任务公开",
    10: "匿名信环节",
    11: "秘密聊天室",
    12: "咖啡馆双人约会",
    13: "深夜谈心",
    14: "回忆屋开启",
    15: "观看旧照片",
    16: "前任专属约会",
    17: "情绪爆发日",
    18: "海岛旅行开始",
    19: "双人房间分配",
    20: "最后一次心动短信",
    21: "最终选择"
}

# 韩系风格嘉宾名字库
MALE_NAMES = ["金道允", "李智宇", "崔宥彬", "郑宰焕", "河正浩", "尹道赫"]
FEMALE_NAMES = ["尹智雅", "韩瑞妍", "姜知允", "徐多恩", "吴荷娜", "李彩琳"]

# 临时存储：当日心境（单用户会话临时数据）
today_mood_cache = {}

# ===================== 通用AI调用核心函数 =====================
def ai_call(prompt):
    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """
你是《换乘恋爱3》官方总导演兼编剧。
核心规则：
1. 文风贴合原版韩综镜头叙事，多用眼神、停顿、细微动作刻画情绪；
2. 情感克制慢热，禁止直白告白、霸总、狗血冲突、校园剧情；
3. 分阶段严格匹配节目流程，规避重复事件，每一天独有专属环节；
4. 前任拉扯、吃醋、犹豫、遗憾为核心情绪，多营造修罗场氛围感；
5. 严格遵循用户指定JSON格式输出，无多余解释、无前言后语。
"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.9
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("AI调用失败：", e)
        return ""

# ===================== 路由 =====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        account = request.form['account']
        password = request.form['password']
        user = User.query.filter_by(account=account).first()
        if user and user.password == password:
            session['user'] = account
            return redirect(url_for('choose_role'))
        return render_template('login.html', error="账号或密码错误，请重新登录")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        account = request.form['account']
        nickname = request.form['nickname']
        password = request.form['password']
        confirm_pwd = request.form['confirm_pwd']

        if password != confirm_pwd:
            return render_template('register.html', error="两次输入的密码不一致")
        if User.query.filter_by(account=account).first():
            return render_template('register.html', error="该账号已被注册")

        new_user = User(
            account=account,
            nickname=nickname,
            password=password
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(account=session['user']).first()

    # 根据玩家性别决定可攻略嘉宾头像
    if user.gender == 'female':
        guest_imgs = ['male1.png', 'male2.png', 'male3.png', 'male4.png']
    else:
        guest_imgs = ['female1.png', 'female2.png', 'female3.png', 'female4.png']

    # 读取短信
    messages = json.loads(user.messages) if user.messages else []
    # 读取嘉宾名字
    guest_names = json.loads(user.guest_names) if user.guest_names else []

    user_data = {
        "nickname": user.nickname,
        "role_name": user.role_name,
        "gender": user.gender,
        "current_day": user.current_day,
        "current_stage": user.current_stage,
        "x_name": user.x_name,
        "x_personality": user.x_personality,
        "guest_names": guest_names,
        "likes": [
            {
                "img": guest_imgs[0],
                "value": user.like_ex,
                "name": guest_names[0] if len(guest_names) > 0 else "前任"
            },
            {
                "img": guest_imgs[1],
                "value": user.like_a,
                "name": guest_names[1] if len(guest_names) > 1 else "嘉宾A"
            },
            {
                "img": guest_imgs[2],
                "value": user.like_b,
                "name": guest_names[2] if len(guest_names) > 2 else "嘉宾B"
            },
            {
                "img": guest_imgs[3],
                "value": user.like_c,
                "name": guest_names[3] if len(guest_names) > 3 else "嘉宾C"
            }
        ],
        "messages": messages,
        "profile": {
            "依恋型": {
                "安全型": user.attach_safe,
                "焦虑型": user.attach_anxious,
                "回避型": user.attach_avoid,
                "混合型": user.attach_mix
            }
        }
    }

    return render_template('profile.html', user=user_data)

@app.route('/choose_role', methods=['GET', 'POST'])
def choose_role():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        gender = request.form['gender']
        role = request.form['role']
        x_name = request.form['x_name']
        x_personality = request.form.get('x_personality', "")

        # 生成随机嘉宾名单
        if gender == 'female':
            shuffled_names = random.sample(MALE_NAMES, 6)
        else:
            shuffled_names = random.sample(FEMALE_NAMES, 6)

        # 玩家角色N → 对应编号位置设为自定义前任名
        try:
            role_num = int(role.replace("嘉宾", ""))
            idx = role_num - 1
            if x_name and 0 <= idx < len(shuffled_names):
                shuffled_names[idx] = x_name
        except Exception as e:
            print("角色编号错误：", e)

        # 保存数据
        user = User.query.filter_by(account=session['user']).first()
        user.gender = gender
        user.role_name = f"{('女性' if gender == 'female' else '男性')}{role}"
        user.x_name = x_name
        user.x_personality = x_personality
        user.guest_names = json.dumps(shuffled_names)
        db.session.commit()

        return redirect(url_for('main_game'))
    return render_template('choose_role.html')

@app.route('/main_game')
def main_game():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(account=session['user']).first()

    day = user.current_day
    stage = user.current_stage
    weekday = WEEK_LIST[(day - 1) % 7]
    guest_names = json.loads(user.guest_names) if user.guest_names else []
    mood = today_mood_cache.get(session['user'], "平淡")

    return render_template(
        'main_game.html',
        game_day=day,
        game_stage=stage,
        current_weekday=weekday,
        stage_name=STAGE_NAMES[stage],
        like_ex=user.like_ex,
        like_a=user.like_a,
        like_b=user.like_b,
        like_c=user.like_c,
        guests=guest_names,
        mood_tag=mood,
        user=user
    )

# 推进阶段
@app.route('/next_stage')
def next_stage():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(account=session['user']).first()

    # 深夜阶段生成匿名心动短信
    if user.current_stage == 3:
        generate_heart_message(user)
        # 游戏天数判定：满21天跳转结局页面
        if user.current_day >= MAX_GAME_DAY:
            if session['user'] in today_mood_cache:
                del today_mood_cache[session['user']]
            # 跳转结局页面
            return redirect(url_for('ending_page'))
        user.current_day += 1
        user.current_stage = 0
    else:
        user.current_stage += 1

    db.session.commit()
    return redirect(url_for('main_game'))

# ===================== AI 心动短信生成 =====================
def generate_heart_message(user):
    guest_names = json.loads(user.guest_names) if user.guest_names else []
    # 定位前任所在下标
    try:
        ex_idx = guest_names.index(user.x_name)
    except:
        ex_idx = 0

    # 80%概率前任发送短信
    if random.random() < 0.8:
        sender_idx = ex_idx
    else:
        other_idx = [i for i in range(4) if i != ex_idx]
        sender_idx = random.choice(other_idx)

    sender_name = guest_names[sender_idx]
    personality = user.x_personality if sender_idx == ex_idx else "温柔内敛，心思细腻"

    # 构造短信提示词
    prompt = f"""
《换乘恋爱》匿名心动短信
嘉宾名字：{sender_name}
人物性格：{personality}
录制第 {user.current_day} 天
要求：
1. 字数30~50字；
2. 氛围心动、克制、有遗憾感；
3. 不直接表白、不出现任何人名字；
4. 贴合韩综温柔细腻风格。
只返回短信正文，不要额外内容。
"""
    message_content = ai_call(prompt)
    if not message_content:
        message_content = "今天偶然看到你的身影，心绪悄悄泛起了涟漪。"

    # 保存短信
    messages = json.loads(user.messages) if user.messages else []
    messages.append({
        "day": user.current_day,
        "stage": "深夜",
        "from": sender_name,
        "content": message_content
    })
    user.messages = json.dumps(messages)
    db.session.commit()

# ===================== 【完全重构】AI动态剧情+选项生成接口 =====================
@app.route('/api/ai_generate_plot', methods=['POST'])
def ai_generate_plot():
    if 'user' not in session:
        return jsonify({
            "plot_text":"未登录",
            "choice_list":[],
            "mood":"平淡"
        })

    data = request.get_json()
    day = data.get("day",1)
    stage = data.get("stage",0)
    ex_name = data.get("ex_name","")
    all_guest = data.get("all_guest",[])

    # 阶段场景映射
    stage_map = {
        0:"晨间宿舍",
        1:"白天录制",
        2:"晚餐聚会",
        3:"深夜短信时间"
    }

    # 分阶段节目剧情指引
    if day <= 6:
        phase_tip = """
前期阶段。
大家刚入住恋爱小屋。
重点：陌生、观察、试探。
前任双方刻意保持距离。
不能快速确定关系。
"""
    elif day <= 13:
        phase_tip = """
中期阶段。
正式约会开启。
重点：吃醋、匿名信、夜间聊天。
开始出现修罗场。
"""
    elif day <= 17:
        phase_tip = """
回忆屋阶段。
重点：旧照片、录音、前任回忆、允许出现眼泪和遗憾。
"""
    elif day <= 20:
        phase_tip = """
海岛旅行阶段。
重点：多人修罗场、房间分配、情绪爆发。
"""
    else:
        phase_tip = """
最终选择阶段。
重点：最后短信、最终约会、最终告白。
"""

    # 获取当日专属节目事件
    today_event = DAY_EVENT.get(day,"普通的一天")

    # 重构完整版Prompt
    prompt = f"""
你是韩综《换乘恋爱3》的总导演。
今天是第{day}天。
当前节目事件：
{today_event}
当前时间：
{stage_map[stage]}
女主前任：
{ex_name}
全体嘉宾：
{all_guest}
{phase_tip}

硬性要求：
1. 风格对标真正《换乘恋爱3》未播幕后片段；
2. 依靠眼神、细微动作、停顿沉默传递情绪，禁止直白说喜欢；
3. 禁止霸总、狗血、校园剧情，感情全程慢热；
4. 允许吃醋、误会、犹豫拉扯、前任遗憾羁绊；
5. 规避重复过往剧情，每日使用专属节目环节；
6. 剧情正文严格控制100-150字；
7. 4个选项无标准答案，每条选项对应独立好感与依恋人格变化；

分阶段剧情参考方向：
【前期1-6天】早餐、做饭、集体聚餐、泳池、小游戏、匿名短信
【中期7-13天】咖啡馆双人约会、散步、匿名信件、夜间谈心
【回忆屋14-17天】旧照片、私人录音、两人过往回忆
【海岛18-20天】集体旅行、分房、多人修罗场冲突
【最终21天】终极心动短信、一对一最终告白约会

仅输出纯JSON字符串，无任何多余文字、注释、说明，严格遵循下方结构：
{{
"plot_text":"",
"choice_list":[
{{
"choice_text":"",
"affect":"ex+5 或 a+5 或 b+5 或 c+5",
"attach":"safe+3 或 anxious+3 或 avoid+3 或 mix+3"
}},
{{
"choice_text":"",
"affect":"",
"attach":""
}},
{{
"choice_text":"",
"affect":"",
"attach":""
}},
{{
"choice_text":"",
"affect":"",
"attach":""
}}
],
"mood":""
}}
"""
    res = ai_call(prompt)

    # 正则容错解析（替换原简易json.loads）
    try:
        match = re.search(r'\{.*\}', res, re.S)
        if match:
            ret = json.loads(match.group())
        else:
            raise Exception("未匹配到JSON块")
    except Exception as e:
        print("JSON解析失败:",e)
        print("AI原始返回内容：",res)
        # 兜底默认剧情
        ret = {
            "plot_text":"夜色渐深，合宿的气氛依旧微妙，每个人似乎都藏着没有说出口的话。",
            "choice_list":[
                {
                    "choice_text":"主动寻找前任聊天",
                    "affect":"ex+5",
                    "attach":"anxious+3"
                },
                {
                    "choice_text":"和另一位嘉宾一起准备夜宵",
                    "affect":"a+5",
                    "attach":"safe+3"
                },
                {
                    "choice_text":"独自待在房间整理心情",
                    "affect":"b+5",
                    "attach":"avoid+3"
                },
                {
                    "choice_text":"加入大家的深夜聊天",
                    "affect":"c+5",
                    "attach":"mix+3"
                }
            ],
            "mood":"复杂"
        }
    # 缓存当日心境供前端读取
    today_mood_cache[session['user']] = ret.get("mood", "平淡")
    return jsonify(ret)

# ===================== 好感度、人格数值更新接口 =====================
@app.route('/api/change_all_data', methods=['POST'])
def change_all_data():
    if 'user' not in session:
        return jsonify({"code": 403})
    d = request.get_json()
    user = User.query.filter_by(account=session['user']).first()

    delta_ex = d.get("de", 0)
    delta_a = d.get("da", 0)
    delta_b = d.get("db", 0)
    delta_c = d.get("dc", 0)

    user.like_ex = max(0, min(100, user.like_ex + delta_ex))
    user.like_a  = max(0, min(100, user.like_a + delta_a))
    user.like_b  = max(0, min(100, user.like_b + delta_b))
    user.like_c  = max(0, min(100, user.like_c + delta_c))

    delta_safe = d.get("ds", 0)
    delta_anx = d.get("dan", 0)
    delta_avoid = d.get("dav", 0)
    delta_mix = d.get("dm", 0)

    user.attach_safe += delta_safe
    user.attach_anxious += delta_anx
    user.attach_avoid += delta_avoid
    user.attach_mix += delta_mix

    db.session.commit()
    return jsonify({"code": 200})

@app.route('/api/send_daily_msg', methods=['POST'])
def send_daily_msg():
    if 'user' not in session:
        return jsonify({"has_msg": False, "anon_msg_content": ""})
    target = request.get_json().get("target", 0)
    add_val = 12
    user = User.query.filter_by(account=session['user']).first()

    if target == 0:
        user.like_ex = max(0, min(100, user.like_ex + add_val))
    elif target == 1:
        user.like_a = max(0, min(100, user.like_a + add_val))
    elif target == 2:
        user.like_b = max(0, min(100, user.like_b + add_val))
    elif target == 3:
        user.like_c = max(0, min(100, user.like_c + add_val))
    db.session.commit()

    has_msg = random.random() < 0.7
    anon_content = ""
    if has_msg:
        prompt = """
《换乘恋爱》匿名心动短信，写给女主，30-50字，温柔含蓄，克制心动，韩综风格，不出现名字。
只返回短信内容。
"""
        anon_content = ai_call(prompt)
        if not anon_content:
            anon_content = "今晚的夜色很温柔，看到你的时候，心里也悄悄软了一块。"
    return jsonify({
        "has_msg": has_msg,
        "anon_msg_content": anon_content
    })

@app.route('/api/get_now_like_data', methods=['GET', 'POST'])
def get_now_like_data():
    if 'user' not in session:
        return jsonify({"ex":0,"a":0,"b":0,"c":0,"mood":"平淡"})
    user = User.query.filter_by(account=session['user']).first()
    mood = today_mood_cache.get(session['user'], "平淡")
    data = {
        "ex": user.like_ex,
        "a": user.like_a,
        "b": user.like_b,
        "c": user.like_c,
        "mood": mood
    }
    return jsonify(data)

@app.route('/api/change_like', methods=['POST'])
def change_like():
    if 'user' not in session:
        return jsonify({"status":"fail"})
    data = request.get_json()
    delta_ex = int(data.get("delta_ex", 0))
    delta_a = int(data.get("delta_a", 0))
    delta_b = int(data.get("delta_b", 0))
    delta_c = int(data.get("delta_c", 0))

    user = User.query.filter_by(account=session['user']).first()
    user.like_ex = max(0, min(100, user.like_ex + delta_ex))
    user.like_a  = max(0, min(100, user.like_a + delta_a))
    user.like_b  = max(0, min(100, user.like_b + delta_b))
    user.like_c  = max(0, min(100, user.like_c + delta_c))
    db.session.commit()
    return jsonify({
        "status":"success",
        "like_ex":user.like_ex,
        "like_a":user.like_a,
        "like_b":user.like_b,
        "like_c":user.like_c
    })

# ===================== 结局页面路由 /ending （已完全适配数据库，无session硬编码） =====================
@app.route("/ending")
def ending_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(account=session['user']).first()
    guest_names = json.loads(user.guest_names) if user.guest_names else []

    # 1. 计算四位嘉宾总好感，选出数值最高的作为最终选择对象
    like_list = [
        {"idx":0, "val": user.like_ex},
        {"idx":1, "val": user.like_a},
        {"idx":2, "val": user.like_b},
        {"idx":3, "val": user.like_c}
    ]
    max_item = max(like_list, key=lambda x: x["val"])
    final_idx = max_item["idx"]
    total_heart = max_item["val"]
    final_name = guest_names[final_idx] if len(guest_names) > final_idx else "嘉宾"

    # 2. 根据玩家性别匹配对应嘉宾图片
    if user.gender == "female":
        img_list = ["male1.png", "male2.png", "male3.png", "male4.png"]
    else:
        img_list = ["female1.png", "female2.png", "female3.png", "female4.png"]
    final_img = f"/static/img/{img_list[final_idx]}"

    # 组装传给前端的嘉宾数据
    final_char = {
        "img_url": final_img,
        "name": final_name,
        "heart_value": total_heart
    }

    # 3. 构造AI结局生成提示词，复用全局ai_call函数，不调用外部接口
    prompt = f"""
韩系恋爱综艺《换乘恋爱》21天完整合宿最终结局生成，严格只输出纯JSON，无任何多余文字。
基础数据：
最终选择嘉宾：{final_name}，总心动好感：{total_heart}
前任姓名：{user.x_name}
依恋人格分数**四项总和必须等于100，每项0~100之间，禁止出现超过100的数值**：
安全型：{user.attach_safe}
焦虑型：{user.attach_anxious}
回避型：{user.attach_avoid}
混合型：{user.attach_mix}

输出JSON固定结构：
{{
    "ending_title": "4-8字结局标题",
    "ending_desc": "300字左右细腻韩系氛围感结局正文，结合21天合宿经历",
    "attach_safe": 0~100整数,
    "attach_anx": 0~100整数,
    "attach_avoid": 0~100整数,
    "attach_mix": 0~100整数,
    "love_tips": "根据心理学家鲍尔比和巴塞洛斯的成人依恋理论生成贴合你依恋人格的专属恋爱建议，1000字左右,最后注明由ai生成，请理性看待",
    "x_letter": "{user.x_name}留给你的临别信件，2000字以内，温柔克制有遗憾氛围感，根据这21天的选择和剧情进行写作，以第一视角写出心路历程"
}}
要求：安全型+焦虑型+回避型+混合型 = 100
"""
    
    ai_raw = ai_call(prompt)
    # AI返回解析兜底
    try:
        ai_data = json.loads(ai_raw)
    except Exception as e:
        print("结局AI JSON解析失败：", e, "原始返回：", ai_raw)
        # 按好感阈值兜底静态文案
        if total_heart >= 85:
            ai_data = {
                "ending_title": "心动共鸣结局",
                "ending_desc": "你们在相互试探与了解中逐渐靠近，跨越了过去的影子，选择彼此，勇敢地迈向了新的未来。这是一段从心动到坚定，从陪伴到承诺的旅程。",
                "attach_safe": user.attach_safe,
                "attach_anx": user.attach_anxious,
                "attach_avoid": user.attach_avoid,
                "attach_mix": user.attach_mix,
                "love_tips": "保持你的真诚与勇敢，你已经拥有了建立健康亲密关系的能力。在未来的日子里，继续倾听彼此的心声，在平凡的生活中创造属于你们的浪漫。",
                "x_letter": "遇见你，大概是我这段旅程中，最美好的意外。这段同居的时光我会一直珍藏，往后无论走多远，我都不会忘记客厅灯光下和你共处的每个傍晚。"
            }
        elif total_heart >= 50:
            ai_data = {
                "ending_title": "暧昧拉扯结局",
                "ending_desc": "你们始终停留在朋友之上恋人未满的界限，彼此心动却不敢彻底交付真心，顾虑太多过往，没能迈出确定关系的一步。",
                "attach_safe": user.attach_safe,
                "attach_anx": user.attach_anxious,
                "attach_avoid": user.attach_avoid,
                "attach_mix": user.attach_mix,
                "love_tips": "你内心渴望亲密却害怕受伤，习惯性退缩。试着放下过去的枷锁，不要用逃避掩盖自己的心动。",
                "x_letter": "我能感受到你的犹豫，其实我也一样。或许我们都需要一点时间，才能放下从前，坦然拥抱新的人。"
            }
        else:
            ai_data = {
                "ending_title": "遗憾错过结局",
                "ending_desc": "短暂的相处过后，你们看清彼此并不适合长久相伴，好感不足以支撑磨合，最终体面分开，回归陌生人的距离。",
                "attach_safe": user.attach_safe,
                "attach_anx": user.attach_anxious,
                "attach_avoid": user.attach_avoid,
                "attach_mix": user.attach_mix,
                "love_tips": "你在亲密关系里极度缺乏安全感，习惯封闭自己，很难完全信任他人。先学会接纳自己，再去爱人。",
                "x_letter": "很遗憾我们没能走到最后，谢谢你这段时间的陪伴，愿我们各自安好，找到真正契合自己的人。"
            }

    # 传给模板的用户信息（前任名字）
    user_info = {
        "x_name": user.x_name
    }

    return render_template(
        "ending.html",
        final_char=final_char,
        ai_data=ai_data,
        user=user_info
    )

# ===================== 依恋人格分析结果页 =====================
@app.route('/result')
def result():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(account=session['user']).first()

    prompt = f"""
基于依恋人格分值做恋爱心理分析：
安全型：{user.attach_safe}
焦虑型：{user.attach_anxious}
回避型：{user.attach_avoid}
混合型：{user.attach_mix}

输出JSON格式（只返回纯JSON）：
{{
    "main_type":"主导人格类型",
    "title":"人格标题",
    "analysis":"300字左右详细恋爱性格分析，贴合综艺人物状态",
    "suggest":"简短恋爱小建议"
}}
"""
    res = ai_call(prompt)
    try:
        analysis_data = json.loads(res)
    except Exception as e:
        print("人格分析解析失败：", e)
        analysis_data = {
            "main_type": "安全型",
            "title": "温和清醒的恋爱者",
            "analysis": "你在亲密关系里情绪稳定，懂得把握边界，既愿意付出真心，也不会丢失自我。面对前任与新的心动对象，你始终保持理性，慢热且真诚。",
            "suggest": "遵从内心感受，勇敢奔赴喜欢的人。"
        }

    return render_template('result.html', analysis=analysis_data, user=user)

@app.route('/letters')
def letters():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(account=session['user']).first()
    msg_list = json.loads(user.messages) if user.messages else []
    return render_template('letters.html', letters=msg_list)

# ===================== AI 一对一对话（聊天室） =====================
@app.route('/api/ai_dialogue', methods=['POST'])
def ai_dialogue():
    data = request.get_json()
    user_input = data.get('input', '')
    if not user_input or 'user' not in session:
        return jsonify({"response": "暂无回应"})

    user = User.query.filter_by(account=session['user']).first()
    x_name = user.x_name
    x_personality = user.x_personality

    prompt = f"""
你是《换乘恋爱》中的嘉宾：{x_name}，性格人设：{x_personality}。
现在和女主面对面聊天，语气自然、细腻、暧昧克制，符合韩综氛围，不要暴露AI。
用户说：{user_input}
直接回复对话内容即可。
"""
    response = ai_call(prompt)
    if not response:
        response = "我明白你的感受。"
    return jsonify({"response": response})

# 重置本局游戏数据
@app.route('/end_game')
def end_game():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(account=session['user']).first()

    user.gender = ""
    user.role_name = ""
    user.x_name = ""
    user.x_personality = ""
    user.current_day = 1
    user.current_stage = 0
    user.like_ex = 50
    user.like_a = 50
    user.like_b = 50
    user.like_c = 50
    user.guest_names = "[]"
    user.messages = "[]"
    db.session.commit()

    return redirect(url_for('index'))

# 退出登录
@app.route('/logout')
def logout():
    if session.get('user') and session['user'] in today_mood_cache:
        del today_mood_cache[session['user']]
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    print("=== 换乘恋爱 服务已启动 ===")
    print("访问地址：http://127.0.0.1:5000")
    app.run(debug=True)