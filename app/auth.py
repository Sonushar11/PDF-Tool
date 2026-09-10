from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

auth_bp = Blueprint("auth", __name__)

# Routes reachable without being logged in.
_PUBLIC_ENDPOINTS = {"auth.login", "static"}


def require_login():
    if request.endpoint in _PUBLIC_ENDPOINTS or request.endpoint is None:
        return None
    if not session.get("logged_in"):
        return redirect(url_for("auth.login", next=request.path))
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password and password == current_app.config["APP_PASSWORD"]:
            session["logged_in"] = True
            next_url = request.form.get("next") or url_for("viewer.index")
            return redirect(next_url)
        error = "Incorrect password."
    return render_template("login.html", error=error, next=request.args.get("next", ""))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
