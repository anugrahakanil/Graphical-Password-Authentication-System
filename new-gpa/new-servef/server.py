from flask import Flask, request, jsonify
import mysql.connector
import bcrypt
import hashlib
import random
import time
import json

app = Flask(__name__)

# ---------- Database Config ----------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "293671",
    "database": "gpa2"
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# ---------- Initialize Database ----------
def initialize_database():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) UNIQUE,
        password_hash VARCHAR(255),
        recovery_hash VARCHAR(255),
        image_name VARCHAR(255),
        attempts INT DEFAULT 0,
        cooldown_until BIGINT DEFAULT 0,
        total_failed_attempts INT DEFAULT 0,
        is_blocked BOOLEAN DEFAULT FALSE
    );
""")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_grid_points (
            user_id INT,
            row_pos INT,
            col_pos INT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    db.commit()
    cursor.close()
    db.close()


initialize_database()


# ---------- Dynamic Recovery Word Generator ----------
def load_word_data():
    with open("words.json", "r") as file:
        return json.load(file)

word_data = load_word_data()
    

def generate_recovery_passphrase(image_name, grid_points):
    combined = image_name + str(grid_points)
    hash_val = int(hashlib.sha256(combined.encode()).hexdigest(), 16)
    random.seed(hash_val)

    subjects = word_data["subjects"]
    verbs = word_data["verbs"]
    objects = word_data["objects"]
    adjectives = word_data["adjectives"]

    subject = random.choice(subjects)
    verb = random.choice(verbs)
    obj = random.choice(objects)
    adjective = random.choice(adjectives)

    return f"{subject} {verb} a {adjective} {obj}."


# ---------- Registration ----------
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username, image, grid_points = data.get("username"), data.get("image"), data.get("grid_point", [])

    if not username or not image or not grid_points:
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    db = get_db_connection()
    cursor = db.cursor()

    # Check existing user
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        return jsonify({"status": "error", "message": "Username already exists"}), 400

    # Password and recovery phrase
    raw_password = image + str(grid_points)
    hashed_password = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt())

    recovery_passphrase = generate_recovery_passphrase(image, grid_points)
    hashed_recovery = bcrypt.hashpw(recovery_passphrase.encode(), bcrypt.gensalt())
    cursor.execute("""
        INSERT INTO users (username, password_hash, image_name, recovery_hash) 
        VALUES (%s, %s, %s, %s)
    """, (username, hashed_password, image, hashed_recovery))
    user_id = cursor.lastrowid

    x = grid_points[0]
    y = grid_points[1]
    cursor.execute("INSERT INTO user_grid_points (user_id, row_pos, col_pos) VALUES (%s, %s, %s)", (user_id, x, y))

    db.commit()
    cursor.close()
    db.close()

    return jsonify({"status": "success", "recovery_passphrase": recovery_passphrase, "message": "Registration successful."}), 200


# ---------- Authentication ----------
@app.route("/authenticate", methods=["POST"])
def authenticate():
    data = request.json
    username, image, grid_points = data.get("username"), data.get("image"), data.get("grid_point", [])

    db = get_db_connection()
    cursor = db.cursor()

    # Fetch user details including attempts and blocking status
    cursor.execute("""
        SELECT id, password_hash, attempts, cooldown_until, total_failed_attempts, is_blocked
        FROM users WHERE username = %s
    """, (username,))
    user = cursor.fetchone()

    if not user:
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401

    user_id, stored_hash, attempts, cooldown_until, total_failed_attempts, is_blocked = user

    # Check if account is blocked
    if is_blocked:
        return jsonify({"status": "error", "message": "Account permanently blocked due to multiple failed attempts."}), 403

    # Check cooldown
    current_time = int(time.time())
    if cooldown_until and current_time < cooldown_until:
        wait_time = cooldown_until - current_time
        return jsonify({"status": "error", "message": f"Too many failed attempts. Try again in {wait_time} seconds."}), 429

    # Validate password
    raw_password = image + str(grid_points)
    if bcrypt.checkpw(raw_password.encode(), stored_hash.encode()):
        # Success - reset attempts and cooldown
        cursor.execute("""
            UPDATE users SET attempts = 0, total_failed_attempts = 0, cooldown_until = 0 WHERE id = %s
        """, (user_id,))
        db.commit()
        return jsonify({"status": "success", "message": "Login successful"}), 200
    else:
        # Failure - update attempts and total failed attempts
        attempts += 1
        total_failed_attempts += 1

        # Handle permanent block after 6 total failed attempts
        if total_failed_attempts >= 6:
            cursor.execute("UPDATE users SET is_blocked = TRUE WHERE id = %s", (user_id,))
            db.commit()
            return jsonify({"status": "error", "message": "Account permanently blocked after 6 failed attempts."}), 403

        # Handle 10 seconds cooldown after 3 attempts
        if attempts >= 3:
            cooldown_until = current_time + 10  # 10 seconds cooldown
            cursor.execute("""
                UPDATE users SET attempts = 0, total_failed_attempts = %s, cooldown_until = %s WHERE id = %s
            """, (total_failed_attempts, cooldown_until, user_id))
            db.commit()
            return jsonify({"status": "error", "message": "Too many failed attempts. Please wait 10 seconds."}), 429
        else:
            # Just increment attempts
            cursor.execute("""
                UPDATE users SET attempts = %s, total_failed_attempts = %s WHERE id = %s
            """, (attempts, total_failed_attempts, user_id))
            db.commit()

        return jsonify({"status": "error", "message": "Invalid credentials."}), 401



# ---------- Forgot Password via Recovery Phrase ----------
@app.route('/recover-password', methods=['POST'])
def recover_password():
    data = request.json
    username, recovery_passphrase = data.get("username"), data.get("recovery_passphrase")

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, recovery_hash, is_blocked FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    if user[2]:  # is_blocked
        return jsonify({"status": "error", "message": "Account is blocked. Please contact support."}), 403

    if bcrypt.checkpw(recovery_passphrase.encode(), user[1].encode()):
        return jsonify({"status": "success", "user_id": user[0], "message": "Recovery verified. You can now reset graphical password."}), 200
    else:
        return jsonify({"status": "error", "message": "Invalid recovery passphrase"}), 400

# ---------- Reset Graphical Password ----------
@app.route('/reset-graphical-password', methods=['POST'])
def reset_graphical_password():
    data = request.json
    user_id, new_image, new_grid_points = data.get("user_id"), data.get("new_image"), data.get("new_grid_points", [])
    new_grid_points = tuple(new_grid_points)
    raw_password = new_image + str(new_grid_points)
    hashed_password = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt())

    recovery_passphrase = generate_recovery_passphrase(new_image, new_grid_points)
    hashed_recovery = bcrypt.hashpw(recovery_passphrase.encode(), bcrypt.gensalt())

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("UPDATE users SET password_hash = %s, image_name = %s, recovery_hash = %s WHERE id = %s",
                   (hashed_password, new_image, hashed_recovery, user_id))

    cursor.execute("DELETE FROM user_grid_points WHERE user_id = %s", (user_id,))
    for row, col in new_grid_points:
        cursor.execute("INSERT INTO user_grid_points (user_id, row_pos, col_pos) VALUES (%s, %s, %s)", (user_id, row, col))

    db.commit()
    cursor.close()
    db.close()

    return jsonify({"status": "success", "message": f"Password reset successfully. New Recovery Passphrase: {recovery_passphrase}"}), 200

if __name__ == "__main__":
    app.run(debug=True)
