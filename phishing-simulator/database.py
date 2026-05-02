import mysql.connector
from mysql.connector import Error
import logging
from config import Config


class Database:
    def __init__(self):
        self.config = {
            "host": Config.MYSQL_HOST,
            "user": Config.MYSQL_USER,
            "password": Config.MYSQL_PASSWORD,
            "database": Config.MYSQL_DB,
        }
        self.connection = None
        self.connect()

    def connect(self):
        try:
            self.connection = mysql.connector.connect(**self.config)
            logging.info("✅ Подключение к MySQL установлено")
        except Error as e:
            logging.error(f"❌ Ошибка подключения к MySQL: {e}")

    def detect_device_type(self, user_agent):
        if not user_agent:
            return "desktop"
        ua = user_agent.lower()
        if "mobile" in ua or "android" in ua or "iphone" in ua:
            return "mobile"
        if "tablet" in ua or "ipad" in ua:
            return "tablet"
        return "desktop"

    def save_user(self, user_data, campaign_id=None):
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            cursor = self.connection.cursor()
            # 1. users
            cursor.execute("INSERT INTO users (is_test_data) VALUES (TRUE)")
            user_id = cursor.lastrowid
            # 2. profiles
            cursor.execute(
                """INSERT INTO profiles (user_id, first_name, last_name, middle_name)
                   VALUES (%s, %s, %s, %s)""",
                (
                    user_id,
                    user_data["first_name"],
                    user_data["last_name"],
                    user_data.get("middle_name", ""),
                ),
            )
            # 3. contacts
            cursor.execute(
                """INSERT INTO contacts (user_id, email, phone, ip_address, user_agent)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    user_id,
                    user_data["email"],
                    user_data.get("phone", ""),
                    user_data["ip_address"],
                    user_data["user_agent"],
                ),
            )
            # 4. Если пришёл из кампании – обновить статус
            if campaign_id:
                device = self.detect_device_type(user_data["user_agent"])
                cursor.execute(
                    """UPDATE email_campaigns
                       SET submitted = TRUE, submitted_date = NOW(),
                           device_type = %s, user_agent = %s, ip_address = %s
                       WHERE unique_id = %s""",
                    (
                        device,
                        user_data["user_agent"],
                        user_data["ip_address"],
                        campaign_id,
                    ),
                )
            self.connection.commit()
            logging.info(
                f"👤 Пользователь {user_data['first_name']} {user_data['last_name']} сохранён"
            )
            return user_id
        except Error as e:
            if self.connection:
                self.connection.rollback()
            logging.error(f"Ошибка сохранения пользователя: {e}")
            return None

    def get_statistics(self):
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) AS total FROM users")
            total_users = cursor.fetchone()["total"]
            cursor.execute("SELECT COUNT(*) AS total FROM profiles")
            total_profiles = cursor.fetchone()["total"]
            cursor.execute("SELECT COUNT(*) AS total FROM contacts")
            total_contacts = cursor.fetchone()["total"]
            return total_users, total_profiles, total_contacts
        except Error as e:
            logging.error(f"Ошибка статистики: {e}")
            return 0, 0, 0

    def get_recent_users(self, limit=20):
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            limit = int(limit)
            if limit < 1:
                limit = 20
            if limit > 100:
                limit = 100
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT u.user_id, u.created_at, p.first_name, p.last_name,
                       c.email, c.ip_address
                FROM users u
                LEFT JOIN profiles p ON u.user_id = p.user_id
                LEFT JOIN contacts c ON u.user_id = c.user_id
                ORDER BY u.created_at DESC
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Ошибка получения пользователей: {e}")
            return []