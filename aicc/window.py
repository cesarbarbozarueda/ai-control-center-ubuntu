#!/usr/bin/python3
"""Desktop window for the panel (GTK 3 + WebKitGTK from the system).

Runs with the system Python so it works the same from the .deb and the snap:
  /usr/bin/python3 window.py http://127.0.0.1:8765
Exits with code 3 right away if GTK/WebKit are missing, so the caller can fall
back to the web browser. Links to other sites open in the default browser.
"""
import sys
import webbrowser

APP_ID = "com.devcibr.AIControlCenter"
NO_TOOLKIT = 3


def load_toolkit():
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        for version in ("4.1", "4.0"):
            try:
                gi.require_version("WebKit2", version)
                break
            except ValueError:
                continue
        else:
            return None
        from gi.repository import Gio, GLib, Gtk, WebKit2
        return Gio, GLib, Gtk, WebKit2
    except (ImportError, ValueError):
        return None


def main(argv):
    url = argv[1] if len(argv) > 1 else "http://127.0.0.1:8765"
    toolkit = load_toolkit()
    if toolkit is None:
        return NO_TOOLKIT
    Gio, GLib, Gtk, WebKit2 = toolkit
    GLib.set_prgname("ai-control-center")
    GLib.set_application_name("AI Control Center")

    def is_local(uri):
        return uri.startswith(url) or uri.startswith("about:")

    def on_policy(_view, decision, kind):
        if kind in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION, WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
            uri = decision.get_navigation_action().get_request().get_uri()
            if kind == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION or not is_local(uri):
                webbrowser.open(uri)
                decision.ignore()
                return True
        return False

    def on_activate(app):
        windows = app.get_windows()
        if windows:  # second launch: bring the existing window to the front
            windows[0].present()
            return
        win = Gtk.ApplicationWindow(application=app, title="AI Control Center")
        win.set_default_size(1280, 860)
        win.set_icon_name("ai-control-center")
        view = WebKit2.WebView()
        settings = view.get_settings()
        settings.set_enable_developer_extras(False)
        view.connect("decide-policy", on_policy)
        view.load_uri(url)
        win.add(view)
        win.show_all()

    app = Gtk.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
    app.connect("activate", on_activate)
    return app.run([argv[0]])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
