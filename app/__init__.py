import os

from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB upload cap
    app.config["APP_PASSWORD"] = os.environ.get("APP_PASSWORD", "change-me")

    from app.auth import auth_bp, require_login
    from app.routes.viewer import viewer_bp
    from app.routes.merge_split import merge_split_bp
    from app.routes.convert import convert_bp
    from app.routes.annotate import annotate_bp
    from app.routes.forms import forms_bp
    from app.routes.redact import redact_bp
    from app.routes.security import security_bp
    from app.routes.textedit import textedit_bp
    from app.routes.extract import extract_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(viewer_bp)
    app.register_blueprint(merge_split_bp)
    app.register_blueprint(convert_bp)
    app.register_blueprint(annotate_bp)
    app.register_blueprint(forms_bp)
    app.register_blueprint(redact_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(textedit_bp)
    app.register_blueprint(extract_bp)

    app.before_request(require_login)

    @app.context_processor
    def inject_doc_state():
        """Undo/redo availability for the global keyboard shortcuts.

        Every page needs this, not just the editor, because Ctrl+Z works
        wherever a document is loaded.
        """
        from app.doc_session import get_current_doc

        _token, doc = get_current_doc()
        return {
            "has_doc": doc is not None,
            "can_undo": bool(doc and doc.history),
            "can_redo": bool(doc and doc.future),
        }

    return app
