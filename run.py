import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    # Binding all interfaces is required inside a container: the process
    # cannot know the address the platform will route to it. This entry
    # point is for local runs only; production serves through gunicorn.
    app.run(
        host="0.0.0.0",  # noqa: S104
        port=port,
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
