from flask import Flask, request, jsonify
import requests
import time
import mysql.connector
from mysql.connector import Error
import yaml

app = Flask(__name__)

# Load Configuration from YAML
def load_config():
    with open("config.yml", "r") as file:
        return yaml.safe_load(file)

config = load_config()

# Extract Configuration Values
SXM_ACCOUNT_DETAILS_REST_URL = config["sxm"]["account_details_url"]
SXM_TOKEN_REST_URL = config["sxm"]["token_rest_url"]
SXM_TOKEN_SECRET = config["sxm"]["token_secret"]
SXM_SOURCE_NAME = config["sxm"]["source_name"]
SXM_TRANSACTION_ID = config["sxm"]["transaction_id"]

DB_CONFIG = {
    "host": config["database"]["host"],
    "user": config["database"]["user"],
    "password": config["database"]["password"],
    "database": config["database"]["name"]
}

# Token Storage (Caching for 24 hours)
token_data = {
    "token": None,
    "expires_at": 0
}

def get_token():
    """Fetch a new OAuth token if expired or not available"""
    current_time = time.time()
    if token_data["token"] is None or current_time >= token_data["expires_at"]:
        headers = {
            "Authorization": SXM_TOKEN_SECRET,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(SXM_TOKEN_REST_URL, headers=headers, data="grant_type=client_credentials")

        if response.status_code == 200:
            response_json = response.json()
            token_data["token"] = response_json.get("access_token")
            token_data["expires_at"] = current_time + (24 * 60 * 60)  # Token valid for 24 hours
        else:
            raise Exception(f"Failed to obtain token: {response.text}")

    return token_data["token"]

def store_data(account_number, data, is_success, error_msg=None):
    """Store CRM data in the database"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = """
        INSERT INTO siriusxmdata (AccountNumber, Data, IsSuccess, Comments) 
        VALUES (%s, %s, %s, %s) 
        ON DUPLICATE KEY UPDATE Data = %s;
        """

        cursor.execute(query, (account_number, str(data), is_success, error_msg, str(data)))
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Database error: {e}")

@app.route("/LookupAccount/<account_number>", methods=["GET"])
def lookup_account(account_number):
    """Fetch CRM data for a single account number and store it in the database"""
    try:
        if not account_number:
            return jsonify({"error": "Account number is required"}), 400

        # Get valid token
        token = get_token()

        # Construct API request URL
        crm_url = SXM_ACCOUNT_DETAILS_REST_URL.format(account_number)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Fetch CRM data
        response = requests.get(crm_url, headers=headers)

        if response.status_code == 200:
            crm_data = response.json()
            store_data(account_number, crm_data, True)  # Store success response
            return jsonify({"account_number": account_number, "data": crm_data, "success": True})
        else:
            store_data(account_number, None, False, response.text)  # Store failure
            return jsonify({"account_number": account_number, "error": response.text, "success": False}), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
