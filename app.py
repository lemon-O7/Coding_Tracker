from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
import os
import requests
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash,check_password_hash
import re
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

def get_db_connection():
    conn = psycopg2.connect(
        os.environ.get("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )
    return conn

@app.route("/")
def root():

    if "user_id" in session:
        return redirect("/dashboard")

    return redirect("/register")

@app.route("/dashboard")
def home():
    if "user_id" not in session:
        return redirect("/login")
    
    conn = get_db_connection()
    difficulty_filter = request.args.get("difficulty")
    search = request.args.get("search")
    sort = request.args.get("sort", "latest")

    query = """
    SELECT * FROM problems
    WHERE user_id = %s
    """
    params = [session["user_id"]]

    if difficulty_filter and difficulty_filter != "All":
        query += " AND difficulty = %s"
        params.append(difficulty_filter)
    
    if search:
        query += " AND title LIKE %s"
        params.append(f"%{search}%")

    if sort == "latest":
        query += " ORDER BY date DESC"
    
    elif sort == "oldest":
        query += " ORDER BY date ASC"
    
    elif sort == "easy":
        query += """
        ORDER BY
        CASE
            WHEN difficulty = 'Easy' THEN 1
            WHEN difficulty = 'Medium' THEN 2
            WHEN difficulty = 'Hard' THEN 3
        END
        """
    
    elif sort == "hard":
        query += """
        ORDER BY
        CASE
            WHEN difficulty = 'Hard' THEN 1
            WHEN difficulty = 'Medium' THEN 2
            WHEN difficulty = 'Easy' THEN 3
        END
        """

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()

    conn.close()

    problems = []

    for r in rows:
        p = dict(r)

        if isinstance(p["date"], str):
            p_date = datetime.strptime(p["date"], "%Y-%m-%d").date()
        else:
            p_date = p["date"]

        p["date"] = p_date
        p["formatted_date"] = p_date.strftime("%d-%m-%Y")

        problems.append(p)
    
    # ✅ STATS
    total = len(problems)
    easy = sum(1 for p in problems if p["difficulty"] == "Easy")
    medium = sum(1 for p in problems if p["difficulty"] == "Medium")
    hard = sum(1 for p in problems if p["difficulty"] == "Hard")

    # 🔥 STREAK (clean version)
    unique_dates = sorted(set(p["date"] for p in problems), reverse=True)

    streak = 0
    today = datetime.today().date()

    current_day = today

    for d in sorted(unique_dates, reverse=True):
        if d == current_day:
            streak += 1
            current_day = current_day - timedelta(days=1)
        else:
            break
        
    daily_counts = {}
    for p in problems:
        date = p["formatted_date"]
        if date in daily_counts:
            daily_counts[date] += 1
        else:
            daily_counts[date] = 1
    
    badges = []

    # First problem badge
    if total >= 1:
        badges.append("🚀 First Problem Solved")

    # 10 problems badge
    if total >= 10:
        badges.append("🎯 10 Problems Solved")

    # 50 problems badge
    if total >= 50:
        badges.append("💯 50 Problems Solved")

    # Hard problems badge
    if hard >= 5:
        badges.append("⚔️ Hard Problem Master")

    # Streak badge
    if streak >= 7:
        badges.append("🔥 7 Day Streak")

    xp = 0

    for p in problems:

        if p["difficulty"] == "Easy":
            xp += 10

        elif p["difficulty"] == "Medium":
            xp += 20

        elif p["difficulty"] == "Hard":
            xp += 30

    level = xp // 100 + 1

    current_level_xp = xp % 100

    heatmap_data = {}

    for p in problems:
    
        date = p["date"]
    
        if date in heatmap_data:
            heatmap_data[date] += 1
        else:
            heatmap_data[date] = 1
            
    return render_template(
        "index.html",
        problems=problems,
        total=total,
        easy=easy,
        medium=medium,
        hard=hard,
        streak=streak,
        daily_counts=daily_counts,
        badges=badges,
        xp=xp,
        level=level,
        current_level_xp=current_level_xp,
        heatmap_data=heatmap_data,
        username = session["username"]
    )

@app.route("/leetcode", methods=["POST"])
def leetcode():
    if "user_id" not in session:
        return redirect("/login")
    
    username=request.form["username"]
    url="https://leetcode.com/graphql"

    query = """
        query getRecentSubmissions($username: String!) {

            recentAcSubmissionList(username: $username) {

                title
                titleSlug
                timestamp

            }
        }
        """
    
    variables = {"username": username }

    response = requests.post(url, json={"query": query,
                                        "variables": variables})    

    data = response.json()
    if data["data"]["recentAcSubmissionList"] is None:
        return "User not found"

    submissions = data["data"]["recentAcSubmissionList"]

    return render_template(
        "leetcode.html",
        submissions=submissions,
        username=username
    )

@app.route("/import", methods=["POST"])
def import_problems():
    if "user_id" not in session:
        return redirect("/login")
    
    selected = request.form.getlist("selected")

    conn = get_db_connection()

    difficulty_query = """
        query getQuestionDetail($titleSlug: String!) {

            question(titleSlug: $titleSlug) {

                difficulty

            }
        }
        """
    cur = conn.cursor()
    for item in selected:


        title, slug, timestamp = item.split("|")

        submission_date = datetime.fromtimestamp(
                int(timestamp)
            ).strftime("%Y-%m-%d")
        
        #check duplicates

        cur.execute(
            """
            SELECT * FROM problems
            WHERE user_id = %s
            AND title = %s
            AND date = %s
            """,
            (
                session["user_id"],
                title,
                submission_date
            )
        )

        existing = cur.fetchone()
    
        difficulty_response = requests.post(
            "https://leetcode.com/graphql",
            json={
                "query": difficulty_query,
                "variables": {
                    "titleSlug": slug
                }
            }
        )
        
        difficulty_data = difficulty_response.json()
        
        difficulty = difficulty_data["data"]["question"]["difficulty"]

        if not existing:
            cur.execute(
            """
            INSERT INTO problems
            (user_id, title, difficulty, date)
            VALUES (%s, %s, %s, %s)
            """,
            (
                session["user_id"],
                title,
                difficulty,
                submission_date
            )
            )
    cur.close()
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect("/login")

    title = request.form["title"]
    difficulty = request.form["difficulty"]
    date = request.form["date"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO problems
        (user_id, title, difficulty, date)
        VALUES (%s, %s, %s, %s)
        """,
        (
            session["user_id"],
            title,
            difficulty,
            date
        )
    )

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")

@app.route("/delete/<int:id>")
def delete(id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM problems
        WHERE id = %s
        AND user_id = %s
        """,
        (
            id,
            session["user_id"]
        )
    )

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "GET":

        cur.execute(
            """
            SELECT * FROM problems
            WHERE id = %s
            AND user_id = %s
            """,
            (id, session["user_id"])
        )

        problem = cur.fetchone()

        cur.close()
        conn.close()

        return render_template(
            "edit.html",
            problem=problem
        )

    title = request.form["title"]
    difficulty = request.form["difficulty"]
    date = request.form["date"]

    cur.execute(
        """
        UPDATE problems
        SET title = %s,
            difficulty = %s,
            date = %s
        WHERE id = %s
        AND user_id = %s
        """,
        (
            title,
            difficulty,
            date,
            id,
            session["user_id"]
        )
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect("/")

@app.route("/register" , methods=["GET", "POST"])
def register() :
    if request.method == "GET":
        return render_template("register.html")

    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]

    email_pattern = r"^[^@]+@[^@]+\.[^@]+$"

    if not re.match(email_pattern, email):
        return render_template(
            "register.html",
            error="Please enter a valid email address."
        )
    if len(password) < 8:
        return render_template(
            "register.html",
            error="Password must be at least 8 characters."
        )
    if not any(char.isalpha() for char in password):
        return render_template(
            "register.html",
            error="Password must contain at least one letter."
        )
    if not any(char.isdigit() for char in password):
        return render_template(
            "register.html",
            error="Password must contain at least one number."
    )
    if len(username) < 3:
        return render_template(
            "register.html",
            error="Username must be at least 3 characters."
        )
    
    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE email = %s",
        (email,)
    )

    existing_user = cur.fetchone()

    if existing_user:
        cur.close()
        conn.close()

        return render_template(
            "register.html",
            error="Email already registered."
        )

    cur.execute(
        """
        INSERT INTO users
        (username, email, password_hash, created_at)

        VALUES (%s, %s, %s, %s)
        """,
        (
            username,
            email,
            password_hash,
            datetime.today().strftime("%Y-%m-%d")
        )
    )

    conn.commit()
    conn.close()

    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    email = request.form["email"]
    password = request.form["password"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE email = %s",
        (email,)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        return render_template(
            "login.html",
            error="User not found"
        )

    if not check_password_hash(
        user["password_hash"],
        password
    ):
        return render_template(
            "login.html",
            error="Incorrect password"
        )

    session["user_id"] = user["id"]
    session["username"] = user["username"]

    return redirect("/")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")

@app.route("/profile")
def profile() :
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT * FROM users
        WHERE id = %s
        """,
        (session["user_id"],)
    )

    user = cur.fetchone()

    query = """
    SELECT * FROM problems
    WHERE user_id = %s
    """
    params = [session["user_id"]]
    cur.execute(query, params)
    rows = cur.fetchall()
    problems = []

    for r in rows:
        p = dict(r)

        problems.append(p)

    total_solved = len(problems)
    easy = sum(1 for p in problems if p["difficulty"] == "Easy")
    medium = sum(1 for p in problems if p["difficulty"] == "Medium")
    hard = sum(1 for p in problems if p["difficulty"] == "Hard")

    xp = 0

    for p in problems:

        if p["difficulty"] == "Easy":
            xp += 10

        elif p["difficulty"] == "Medium":
            xp += 20

        elif p["difficulty"] == "Hard":
            xp += 30
    
    level = xp // 100 + 1

    unique_dates = sorted(
    {p["date"] for p in problems},
    reverse=True
    )

    streak = 0
    today = datetime.today().date()

    for i, d in enumerate(unique_dates):

        current_date = datetime.strptime(
            d,
            "%Y-%m-%d"
        ).date()

        if i == 0:

            if (today - current_date).days > 1:
                break

        else:

            prev_date = datetime.strptime(
                unique_dates[i - 1],
                "%Y-%m-%d"
            ).date()

            if (prev_date - current_date).days != 1:
                break

        streak += 1
        
    cur.close()
    conn.close()

    stats = {
        "easy": easy,
        "medium": medium,
        "hard": hard,
        "total_solved": total_solved,
        "xp": xp,
        "level": level,
        "streak": streak
    }

    user = dict(user)   
    user["stats"] = stats

    return render_template(
        "profile.html",
        user=user
    )

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

if __name__ == "__main__":
    app.run()