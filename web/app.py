from flask import Flask

from core.config import settings


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB
    app.config["UPLOAD_FOLDER"] = settings.upload_folder

    from web.routes import main_bp
    app.register_blueprint(main_bp)

    return app
