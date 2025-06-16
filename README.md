# Prereq Fetcher  
*A Mod Organizer 2 plug-in that finds, displays & queues every Nexus
**requirement** for a newly-downloaded mod – recursively.*

![Preview](preview.mp4)

---

## ✨ Why would I want this?

Mod pages on Nexus often hide essential **prerequisites** two or three
levels deep:

1. You download “Awesome Overhaul”.
2. It depends on “Framework A” and “Patcher B”.
3. **Framework A** depends on “Address Library” …  
   **Patcher B** needs a specific *main* file of “SKSE64”.

Manually chasing those links is tedious. *Prereq Fetcher* does it for
you:

* Scrapes every “**Nexus requirements**” & “**Off-site requirements**”
  table **recursively**.  
  (No Nexus API needed for that – only raw HTML.)
* Shows a tree where **every downloadable file** is a check-box.  
  *Duplicates stay in-sync; already downloaded/installed items are
  greyed-out.*
* Queues any still-checked files via MO2’s
  `startDownloadNexusFile()` **and keeps a progress dialog open until
  the last one finishes**.
* Ignores its *own* downloads, so you never recurse forever.
* Optional TRACE log for debugging curious edge-cases.

However, it does **NOT** pull in *optional* requirements. You’ll still
need to verify that your chosen options make sense with the rest of your
load-order.

---

## ▶️ Quick start

|                           |                                                      |
|---------------------------|------------------------------------------------------|
| **Requires**              | • Mod Organizer ≥ **2.5** <br>• Python plug-in loader |
| **Install**               | 1. Clone / download to `…\plugins\prereq_fetcher` <br>2. Check *Settings ▸ Plugins ▸ Prereq Fetcher* **enabled** |
| **Setup once**            | Paste your **Nexus API key** (needed only for friendly names & file lists). |
| **Use**                   | 1. Download *any* Nexus archive <br>2. If that mod (recursively) has dependencies → the tree pops up <br>3. Tick / untick files → **OK** ⭐ |
| **Debug log**             | Toggle *Settings ▸ Plugins ▸ Prereq Fetcher ▸ debug* = **True** to write `plugins/prereq_fetcher/debug.log` |

---

## 👀 Coming Soon
* **Auto-notes** – after installation, mods will be annotated in their  
  *Notes* field with concise “dashboard” tags (e.g. `F: SKSE, SPID, DynDO`)  
  and a *Needed By* list, all kept in-sync if you later uninstall a mod.  
  (Opt-in, preserves any personal notes you already wrote.)

---

## 📦 Features (v1.0)

| 🚩 | Feature |
|----|---------|
| 🔍 | **Recursive HTML scrape** – no MO2–Nexus bridge required |
| ✔️ | Object-level selection: every “Main” file becomes a check-box |
| 🔄 | Duplicates propagate: tick once, all identical leaves toggle |
| 🕵️‍♂️ | Detects *already downloaded* archives and *already installed* mods |
| 🛡️ | Never analyses a download it started itself |
| 🌐 | Off-site rows rendered as external links |
| 🪵 | Optional *TRACE* log for bug-hunting |
