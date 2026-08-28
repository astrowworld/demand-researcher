from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, request

import db


def create_app(db_path: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path

    @app.route("/")
    def index():
        categorie = request.args.get("categorie") or None
        conn = db.get_conn(app.config["DB_PATH"])
        db.init_db(conn)
        signals = db.get_signals(conn, categorie=categorie)
        conn.close()
        return render_template("index.html", signals=signals, categorie=categorie)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
