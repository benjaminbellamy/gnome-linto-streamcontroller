# Import StreamController modules
from src.backend.PluginManager.ActionBase import ActionBase

# GTK modules for the config rows
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

import os
import weakref

from .linto_ws import LintoClient

DEFAULTS = {"host": "127.0.0.1", "port": 4466, "password": "",
            "top": "elapsed", "middle": "none", "bottom": "bitrate"}
VALUE_KEYS = ["none", "elapsed", "data", "bitrate"]
VALUE_LABELS = ["None", "Elapsed time", "Data sent", "Bitrate"]


class LintoToggle(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        self.status = {}
        self.conn = "offline"      # offline | connected | auth | no-password
        self._save_source = 0
        self._status_row = None

    # -- lifecycle ---------------------------------------------------------

    def on_ready(self):
        self._ensure_image_control()
        self._reconnect()
        self._render()

    def on_remove(self):
        if self._save_source:
            GLib.source_remove(self._save_source)
            self._save_source = 0
        if self.client:
            self.client.stop()
            self.client = None

    # Called when the action instance is dropped on a page reload; stop the
    # client so it does not keep reconnecting in the background.
    def on_removed_from_cache(self):
        self.on_remove()

    def _ensure_image_control(self):
        # A freshly added action is granted label and background control but
        # not image control, so set_media is ignored and no icon shows. Claim
        # image control for this action if it is not already ours.
        try:
            manager = self.get_state().action_permission_manager
            index = self.get_own_action_index()
            if index is not None and manager.get_image_control_index() != index:
                manager.set_image_control_index(index, reload_pages=False,
                                                reload_self=False)
        except Exception:
            pass

    def on_key_down(self):
        if self.client:
            self.client.send_action("toggle")

    # -- connection --------------------------------------------------------

    def _cfg(self):
        merged = dict(DEFAULTS)
        merged.update(self.get_settings() or {})
        return merged

    def _reconnect(self):
        if self.client:
            self.client.stop()
            self.client = None
        cfg = self._cfg()
        if not cfg["password"]:
            self.conn = "no-password"
            self.status = {}
            self._update_status_row()
            return
        # The client holds only a weak reference back to this action, so a
        # discarded instance can be garbage collected and its client shut down
        # instead of lingering as a zombie connection.
        self.client = LintoClient(
            cfg["host"], cfg["port"], cfg["password"],
            owner=weakref.ref(self),
            dispatch=GLib.idle_add,
        )
        self.client.start()

    def _on_status(self, status):
        self.status = status
        self.conn = "connected"
        self._update_status_row()
        self._render()
        return False

    def _on_conn(self, ok, note):
        if ok:
            self.conn = "connected"
        else:
            self.conn = "auth" if note == "auth" else "offline"
            self.status = {}
        self._update_status_row()
        self._render()
        return False

    # -- rendering ---------------------------------------------------------

    def _set_icon(self, name):
        path = os.path.join(self.plugin_base.PATH, "assets",
                            "linto-%s.png" % name)
        if os.path.exists(path):
            self.set_media(media_path=path, size=0.9)
        self.set_background_color([0, 0, 0, 0])

    def _labels(self, top, center, bottom):
        self.set_top_label(top)
        self.set_center_label(center)
        self.set_bottom_label(bottom)

    def _render(self):
        # Not reachable / not authorised: a problem prevents streaming.
        if self.conn != "connected" or not self.status:
            self._set_icon("ko")
            self._labels("", "", "")
            return

        state = self.status.get("state")
        if state == "streaming":
            self._set_icon("streaming")
            cfg = self._cfg()
            self._labels(self._value_for(cfg["top"]),
                         self._value_for(cfg["middle"]),
                         self._value_for(cfg["bottom"]))
        elif state in ("connecting", "reconnecting"):
            self._set_icon("streaming")
            self._labels("", "", "")
        elif self.status.get("ready") and self.status.get("network_ok"):
            self._set_icon("ready")
            self._labels("", "", "")
        else:
            # Idle but something (address, device or network) blocks streaming.
            self._set_icon("ko")
            self._labels("", "", "")

    def _value_for(self, key):
        if key == "elapsed":
            return self._elapsed()
        if key == "data":
            return self._data()
        if key == "bitrate":
            return self._bitrate()
        return ""

    def _elapsed(self):
        seconds = int(self.status.get("elapsed", 0))
        return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60,
                                 seconds % 60)

    def _data(self):
        value = float(self.status.get("data_bytes", 0))
        for unit in ("B", "KiB", "MiB", "GiB"):
            if value < 1024:
                return ("%d %s" if unit == "B" else "%.1f %s") % (value, unit)
            value /= 1024
        return "%.1f TiB" % value

    def _bitrate(self):
        return "%d kb/s" % int(self.status.get("bitrate_kbps", 0))

    # -- config UI ---------------------------------------------------------

    def _status_text(self):
        if self.conn == "no-password":
            return "No password set"
        if self.conn == "auth":
            return "Wrong password"
        if self.conn == "connected":
            return "Connected"
        return "Not connected"

    def _update_status_row(self):
        if self._status_row is not None:
            self._status_row.set_subtitle(self._status_text())

    def get_config_rows(self):
        cfg = self._cfg()
        self._host_row = Adw.EntryRow(title="Host")
        self._host_row.set_text(str(cfg["host"]))
        self._port_row = Adw.EntryRow(title="Port")
        self._port_row.set_text(str(cfg["port"]))
        self._password_row = Adw.PasswordEntryRow(title="Password")
        self._password_row.set_text(str(cfg["password"]))
        self._top_combo = self._value_combo("Top value", cfg["top"])
        self._middle_combo = self._value_combo("Middle value", cfg["middle"])
        self._bottom_combo = self._value_combo("Bottom value", cfg["bottom"])
        self._status_row = Adw.ActionRow(title="Connection")
        self._status_row.set_subtitle(self._status_text())

        for row in (self._host_row, self._port_row, self._password_row):
            row.connect("changed", self._schedule_save)
        return [self._host_row, self._port_row, self._password_row,
                self._top_combo, self._middle_combo, self._bottom_combo,
                self._status_row]

    def _value_combo(self, title, key):
        row = Adw.ComboRow(title=title)
        row.set_model(Gtk.StringList.new(VALUE_LABELS))
        row.set_selected(VALUE_KEYS.index(key) if key in VALUE_KEYS else 0)
        row.connect("notify::selected", self._schedule_save)
        return row

    def _schedule_save(self, *args):
        if self._save_source:
            GLib.source_remove(self._save_source)
        self._save_source = GLib.timeout_add(700, self._commit_settings)

    def _commit_settings(self):
        self._save_source = 0
        settings = self._cfg()
        settings["host"] = self._host_row.get_text().strip() or "127.0.0.1"
        try:
            settings["port"] = int(self._port_row.get_text().strip())
        except ValueError:
            pass
        settings["password"] = self._password_row.get_text().strip()
        settings["top"] = VALUE_KEYS[self._top_combo.get_selected()]
        settings["middle"] = VALUE_KEYS[self._middle_combo.get_selected()]
        settings["bottom"] = VALUE_KEYS[self._bottom_combo.get_selected()]
        self.set_settings(settings)
        self._reconnect()
        self._render()
        return False
