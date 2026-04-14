import logging
import os

from flask import Flask
from flask_cors import CORS

from config import ALLOWED_ORIGINS, SECRET_KEY


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), "frontend", "dist"),
        static_url_path="",
    )
    app.config["SECRET_KEY"] = SECRET_KEY

    # CORS — restrict to ALLOWED_ORIGINS in prod
    origins = ALLOWED_ORIGINS.split(",") if ALLOWED_ORIGINS != "*" else "*"
    CORS(app, resources={r"/api/*": {"origins": origins}})

    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Register blueprints
    from routes.api import api_bp
    app.register_blueprint(api_bp)

    # Serve React SPA for all non-API routes
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        if not app.static_folder or not os.path.isdir(app.static_folder):
            return "Frontend not built. Run: cd frontend && npm run build", 503
        target = os.path.join(app.static_folder, path)
        if path and os.path.exists(target):
            return app.send_static_file(path)
        index = os.path.join(app.static_folder, "index.html")
        if os.path.exists(index):
            return app.send_static_file("index.html")
        return "Frontend not built. Run: cd frontend && npm run build", 503

    # Global JSON error handler for API routes
    from flask import jsonify
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(Exception)
    def handle_exception(e):
        from flask import request as req
        if isinstance(e, HTTPException):
            return e
        if req.path.startswith("/api/"):
            logging.exception("Unhandled exception")
            return jsonify({"error": "An unexpected error occurred."}), 500
        raise e

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
