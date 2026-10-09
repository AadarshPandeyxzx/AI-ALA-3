
from flask import Flask, render_template, request, jsonify
from chatbot import find_answer, reload_data

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"response": "Please type a question."}), 400

    try:
        response = find_answer(message)
        return jsonify({"response": response})

    except Exception as error:
        app.logger.exception("Chatbot error: %s", error)
        return jsonify({
            "response": "Something went wrong. Please try again."
        }), 500


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "message": "GMIU chatbot is running."
    })


@app.route("/reload-data", methods=["POST"])
def reload_scraped_data():
    # Reloads local JSON data; it does not scrape the website.
    count = reload_data()

    return jsonify({
        "status": "ok",
        "pages_loaded": count
    })


if __name__ == "__main__":
    app.run(debug=True)

