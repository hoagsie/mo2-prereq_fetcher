#!/usr/bin/env python3
# =============================================================================
#  PrereqFetcher v-1.0.0  –  Nexus-mod prerequisite explorer & auto-downloader
# =============================================================================
#  License ─ GNU GENERAL PUBLIC LICENSE, Version 3
#  ---------------------------------------------------------------------------
#  Copyright © 2025 sacredwitness aka hoagsie
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#  SPDX-License-Identifier: GPL-3.0-or-later
# =============================================================================
#  What it does ───────────────────────────────────────────────────────────────
#  • Hooks the **Mod Organizer 2** (MO2) *download-complete* signal.
#  • Reads the companion “*.meta” file of every freshly-downloaded archive to
#    learn  ➜ game slug | mod ID | file ID.
#  • Builds a **recursive dependency tree** by scraping each mod’s public
#    *Requirements* table (no unofficial Nexus API required, so it works even
#    for hidden files / VR mods, etc.).
#  • Presents a **checkbox UI** where the *leaf* rows are *files*, not mods.
#        ↳ Duplicates stay in sync.  
#        ↳ Anything already **downloaded** *or* **installed** is greyed out.  
#  • Queues every still-checked file via `startDownloadNexusFile()`.
#  • Tracks the files it queued so it ① doesn’t re-analyse its own work and
#    ② keeps a progress bar open until the last of them hits 100 %.
#
#  Edge-cases considered ─────────────────────────────────────────────────────
#  • Mods with **multiple “MAIN” files** – all are shown.  
#  • Circular / duplicate dependency links – rendered once; later references
#    become stub “↪ duplicate” rows.  
#  • Mods that have *only* off-site requirements – a dummy “Prerequisites”
#    header is inserted so the UI isn’t empty.  
#  • Works with **disabled plug-in** checkbox, first-run (no stored value),
#    and any QVariant type that MO2 may return.  
#  • **Debug logging** is optional. When `trace_logging` is off (default),
#    *no* log file is created and `_log()` becomes a cheap no-op.
#
#  Journey recap – milestones for future maintainers ─────────────────────────
#    0.1.x → 0.8.x :  basic HTML scrape, single-level, fragile enabled check  
#    0.9.x → 1.1.2 :  duplicate-safe recursion, per-file check-boxes, owned
#                     detection, progress-suppression loop  
#    1.1.3 → 1.1.7 :  fixed self-trigger loops, robust `_enabled`, crash-free
#                     duplicate tracking (`seen_mods`)  
#    1.0.0        :  production polish, optional logging, full GPL header
# =============================================================================
"""
Settings (MO2 → Settings → Plugins → Prereq Fetcher)
────────────────────────────────────────────────────
enabled        : bool  – master on/off switch (default ✓ on)
api_key        : str   – personal Nexus REST key (only used for
                         mod names & file lists; scraper still works
                         without it, but names fall back to “Mod <ID>”)
trace_logging  : bool  – write verbose ./debug.log (default ✕ off)
"""
# =============================================================================

from __future__ import annotations

# ─────────────────────────── stdlib / third-party ──────────────────────────
from pathlib import Path
from typing  import Dict, List, Tuple, Set
import configparser, functools, html, re, time, requests, mobase

from PyQt6.QtCore    import Qt, QCoreApplication
from PyQt6.QtGui     import QIcon
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QDialogButtonBox, QMessageBox, QProgressDialog,
)

# ────────────────────────────── module globals ─────────────────────────────
API_ROOT   = "https://api.nexusmods.com/v1"
HERE       = Path(__file__).resolve().parent
LOG_FILE   = HERE / "debug.log"

DEBUG: bool = False          # becomes True in `init()` if trace_logging is on

# ────────────────────────────── tiny logger ────────────────────────────────
def _log(msg: str) -> None:
    """Cheap logger – does nothing unless DEBUG is turned on."""
    if not DEBUG:
        return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fp:
        fp.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

# ───────────────────────────── helper functions ────────────────────────────
def _meta_ids(archive: str) -> Tuple[str, int, int] | None:
    """Read `<archive>.meta` and return (gameSlug, modID, fileID)."""
    meta = Path(archive).with_suffix(Path(archive).suffix + ".meta")
    if not meta.is_file():
        return None
    cp = configparser.ConfigParser()
    cp.read(meta, encoding="utf-8")
    try:
        return (cp["General"]["gameName"],
                cp["General"].getint("modID"),
                cp["General"].getint("fileID"))
    except Exception:
        return None


def _api(path: str, key: str) -> Dict:
    """Thin wrapper around `requests.get` that honours DEBUG logging."""
    _log(f"[GET] {path}")
    r = requests.get(API_ROOT + path,
                     headers={"apikey": key, "accept": "application/json"},
                     timeout=25)
    _log(f"      status {r.status_code}")
    r.raise_for_status()
    return r.json()


@functools.lru_cache(maxsize=None)
def _html(game: str, mid: int) -> str:
    """Download & cache the public HTML page of a mod."""
    url = f"https://www.nexusmods.com/{game}/mods/{mid}"
    _log(f"[HTML] {url}")
    return requests.get(url, timeout=25).text


# REGEX to harvest the <Requirements> tables
REQ_RX  = re.compile(
    r'<h3>(Nexus requirements|Off-site requirements)</h3>.*?<tbody>(.*?)</tbody>',
    re.S | re.I)
LINK_RX = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)

def _html_rows(page: str) -> List[Tuple[str, str, str]]:
    """Return [(cat,name,url)] for every link inside the requirements tables."""
    rows: List[Tuple[str, str, str]] = []
    for hdr, body in REQ_RX.findall(page):
        cat = "nexus" if hdr.lower().startswith("nexus") else "offsite"
        for href, txt in LINK_RX.findall(body):
            rows.append((cat,
                         html.unescape(re.sub(r"\s+", " ", txt).strip()),
                         href))
    return rows

# ────────────────────────────────── PLUG-IN ─────────────────────────────────
class PrereqFetcher(mobase.IPluginTool):
    VER = mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.FINAL)

    # ── basic metadata (shown in MO2’s plug-in list) ──────────────────────
    def name        (self): return "Prereq Fetcher"
    def author      (self): return "sacredwitness"
    def description (self): return "Recursively explores Nexus prerequisites"
    def version     (self): return self.VER
    def displayName (self): return "Prereq Fetcher"
    def tooltip     (self): return "Explore & queue Nexus prerequisites"
    def icon        (self): return QIcon()   # default folder icon

    # ── settings visible in the MO2 UI ────────────────────────────────────
    def settings(self):
        return [
            mobase.PluginSetting("enabled",      "Enable plug-in",          True),
            mobase.PluginSetting("api_key",      "Nexus API key",           ""),
            mobase.PluginSetting("trace_logging","Verbose debug log file",  False),
        ]

    # ── constructor ──────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()
        self._pending  : Set[tuple[int, int]]   = set()   # (modID,fileID) awaiting finish
        self._progress : QProgressDialog | None = None    # live progress bar

    # ── enabled?  (robust against QVariant oddities) ─────────────────────
    def _enabled(self) -> bool:
        raw = self._org.pluginSetting(self.name(), "enabled")
        if raw in (None, ""):                # first run
            return True
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return raw != 0
        return not str(raw).strip().lower().startswith(("f", "n", "0"))

    # ── MO2 initialisation – install hooks & configure logging ───────────
    def init(self, org: mobase.IOrganizer):
        global DEBUG
        self._org = org

        # decide logging *once*
        DEBUG = bool(org.pluginSetting(self.name(), "trace_logging"))
        if DEBUG:
            # fresh log for this MO2 session
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            LOG_FILE.write_text("", encoding="utf-8")
            _log("─" * 34 + " TRACE START " + "─" * 34)

        dm = org.downloadManager()
        dm.onDownloadComplete(self._on_download_complete)   # main logic
        dm.onDownloadComplete(self._on_download_progress)   # progress-bar RMS
        _log("[init] hooks installed")
        return True

    # ── helper: key for the pending-set ----------------------------------
    @staticmethod
    def _key(mid: int, fid: int) -> tuple[int, int]:
        return (mid, fid)

    # ── progress hook – called for *every* finished download -------------
    def _on_download_progress(self, dl_id: int):
        """Tick down the progress bar if the file belongs to our queue."""
        if not self._pending:
            return

        ids = _meta_ids(self._org.downloadManager().downloadPath(dl_id))
        if not ids:
            return

        key = self._key(ids[1], ids[2])
        if key not in self._pending:
            return

        self._pending.discard(key)
        if self._progress:
            done = self._progress.maximum() - len(self._pending)
            self._progress.setValue(done)
            if not self._pending:
                self._progress.close()
                self._progress = None
                _log("[progress] all queued downloads completed")

    # ── main download-complete hook -------------------------------------
    def _on_download_complete(self, dl_id: int):
        """
        Fires for **every** finished download.
        * Skips files that were queued by PrereqFetcher itself.
        * Ignores if the plug-in is disabled.
        * Spawns the analysis UI for brand-new, user-initiated downloads.
        """
        ids = _meta_ids(self._org.downloadManager().downloadPath(dl_id))
        if not ids:
            return

        if self._key(ids[1], ids[2]) in self._pending:   # we started this
            return
        if not self._enabled():
            return

        # ── gather roots / settings
        game = self._org.managedGame().gameNexusName()
        key  = self._org.pluginSetting(self.name(), "api_key").strip()
        root_mod  = ids[1]
        root_name = _api(f"/games/{game}/mods/{root_mod}.json", key).get("name",
                                                                         f"Mod {root_mod}")
        _log(f"[hook] analysing root={root_mod} «{root_name}»")

        # ── progress spin while scraping
        parent = getattr(self, "_parentWidget", lambda: None)()
        spin   = QProgressDialog("Inspecting prerequisites…", "", 0, 0, parent)
        spin.setWindowModality(Qt.WindowModality.WindowModal)
        spin.setCancelButton(None)
        spin.show(); QCoreApplication.processEvents()

        try:
            tree, off_rows = self._build_dependency_tree(game, root_mod, key)
        except Exception as exc:
            spin.close()
            _log(f"[error] {exc}")
            QMessageBox.warning(parent or None, self.name(), str(exc))
            return
        spin.close()

        # ── interactive UI
        self._show_ui(parent, game, root_name, tree, off_rows, key)

    # ── helper – recursive HTML scrape -----------------------------------
    def _build_dependency_tree(self, game: str, root: int, key: str):
        visited: set[int]          = set()
        offsite: Dict[str, str]    = {}
        nexus_rx = re.compile(rf"/{re.escape(game)}/mods/(\d+)", re.I)

        @functools.lru_cache(maxsize=None)
        def _name(mid: int) -> str:
            return _api(f"/games/{game}/mods/{mid}.json", key).get("name", f"Mod {mid}")

        def walk(mid: int):
            if mid in visited:
                return None
            visited.add(mid)

            node = {"id": mid, "name": _name(mid), "children": []}
            for cat, n, u in _html_rows(_html(game, mid)):
                if cat == "offsite":
                    offsite[u] = n
                else:
                    m = nexus_rx.search(u)
                    if m:
                        cid = int(m.group(1))
                        node["children"].append(
                            walk(cid) or {"id": cid, "name": _name(cid), "children": []}
                        )
            return node

        root_node = walk(root) or {"id": root, "name": _name(root), "children": []}
        return root_node, list(offsite.items())

    # ── big UI routine ----------------------------------------------------
    def _show_ui(self, parent, game: str, root_name: str,
                 root: Dict, off_rows: List[Tuple[str, str]], key: str):
                     
        if not root["children"] and not off_rows:
            _log("[UI] no prerequisites detected – skipping dialog")
            return

        # ---------- helper: file list for a mod
        @functools.lru_cache(maxsize=None)
        def _files(mid: int) -> List[Dict]:
            if mid <= 0:
                return []
            js = _api(f"/games/{game}/mods/{mid}/files.json", key).get("files", [])
            mains = [f for f in js if str(f.get("category_name", "")).upper() == "MAIN"]
            return mains or js

        # ---------- already-owned detection
        dl_dir = Path(self._org.downloadsPath())
        owned_dl = {(int(m.group(1)), int(m.group(2)))
                    for f in dl_dir.iterdir() if f.is_file()
                    for m in [re.search(r"-(\d+)-(\d+)-.*\.(?:7z|zip|rar)$", f.name)]
                    if m}

        mods_root = Path(self._org.modsPath())
        owned_mod: set[int] = set()
        
        for internal in self._org.modList().allMods():
            meta_ini = mods_root / internal / "meta.ini"
            if not meta_ini.is_file():
                continue                       # non-MO2 mod or missing metadata
            cp = configparser.ConfigParser()
            cp.read(meta_ini, encoding="utf-8")
        
            try:
                mod_id = cp["General"].getint("modid")
            except (KeyError, ValueError):
                continue                       # missing or malformed entry
            owned_mod.add(mod_id)

        # ---------- dialog skeleton
        dlg = QDialog(parent)
        dlg.setWindowTitle(f"Prerequisites — {root_name}")
        lay = QVBoxLayout(dlg)
        tw  = QTreeWidget()
        tw.setHeaderHidden(True)
        lay.addWidget(tw)

        sync: Dict[Tuple[int, int], List[QTreeWidgetItem]] = {}
        seen_mods: Set[int] = set()

        seeds = root["children"] or [{"id": 0, "name": "Prerequisites", "children": []}]

        # ---------- recursive tree builder
        def build(parent_item, node):
            if node["id"] <= 0:                                   # UI header
                hdr = QTreeWidgetItem(parent_item, [node["name"]])
                hdr.setFlags(Qt.ItemFlag.ItemIsEnabled)
                for ch in node["children"]:
                    build(hdr, ch)
                return

            if node["id"] in seen_mods:                           # duplicate mod
                QTreeWidgetItem(parent_item, [f"↪ {node['name']} (duplicate)"])
                return
            seen_mods.add(node["id"])

            mod_it = QTreeWidgetItem(parent_item, [node["name"]])
            mod_it.setFlags(mod_it.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)

            # all candidate files
            for file in _files(node["id"]):
                fid   = int(file["file_id"])
                size  = file.get("size_kb", 0) / 1024
                label = f'{file["name"]}  ({size:.1f} MB)'
                owned = ((node["id"], fid) in owned_dl) or (node["id"] in owned_mod)

                leaf  = QTreeWidgetItem(mod_it,
                         [label + (" (owned)" if owned else "")])
                leaf.setData(0, Qt.ItemDataRole.UserRole, (node["id"], fid))

                if owned:
                    leaf.setFlags(Qt.ItemFlag.ItemIsEnabled)
                else:
                    leaf.setCheckState(0, Qt.CheckState.Checked)
                    sync.setdefault((node["id"], fid), []).append(leaf)

            for ch in node["children"]:
                build(mod_it, ch)

        for seed in seeds:
            build(tw.invisibleRootItem(), seed)

        tw.expandAll()
        
        dlg.resize(dlg.width(), 700)

        # ---------- off-site links
        if off_rows:
            lay.addWidget(QLabel("<b>Off-site requirements:</b>"))
            for n, u in off_rows:
                link = QLabel(f'<a href="{u}">{n}</a>')
                link.setOpenExternalLinks(True)
                lay.addWidget(link)

        # ---------- keep duplicate leaves in sync
        def propagate(item, *_):
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, tuple):
                for peer in sync.get(data, []):
                    if peer is not item:
                        peer.setCheckState(0, item.checkState(0))
        tw.itemChanged.connect(propagate)

        # ---------- OK / Cancel buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel,
                                Qt.Orientation.Horizontal, dlg)
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        # ---------- execute dialog
        if dlg.exec() != QDialog.DialogCode.Accepted:
            _log("[UI] cancelled")
            return

        queue = [
            key for key, leaves in sync.items()
            if leaves[0].checkState(0) == Qt.CheckState.Checked and
               key not in owned_dl and key[0] not in owned_mod
        ]

        if not queue:
            _log("[UI] nothing to queue")
            return

        # ---------- progress bar covering all queued downloads
        self._pending.update(queue)
        self._progress = QProgressDialog("Downloading prerequisites…",
                                         None,
                                         0, len(self._pending),
                                         parent or dlg)
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setCancelButton(None)
        self._progress.show()
        QCoreApplication.processEvents()

        # ---------- fire away
        dm = self._org.downloadManager()
        for mid, fid in queue:
            _log(f"    startDownloadNexusFile {mid}/{fid}")
            dm.startDownloadNexusFile(mid, fid)

    # ─────────────────────────────────────────────────────────────
    # IPluginTool interface: what happens when the user opens the
    # tool *manually* from MO2’s “Tools” menu or toolbar.
    # We don’t have a standalone window, so we just explain that.
    # ─────────────────────────────────────────────────────────────
    def display(self):
        """
        Invoked when the user selects “Prereq Fetcher” from MO2’s
        *Tools* menu.  We don’t need a full UI here, so a brief info
        box is enough.
        """
        QMessageBox.information(
            self._parentWidget() if hasattr(self, "_parentWidget") else None,
            "Prereq Fetcher",
            ("Prereq Fetcher runs automatically whenever a download "
             "completes.\n\n"
             "If the downloaded archive has Nexus/Off-site requirements, "
             "a tree view will appear so you can queue them.\n\n"
             "There’s nothing to configure in this manual window.")
        )