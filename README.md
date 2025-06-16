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
  (No Nexus API needed for that – only HTML.)
* Shows a tree where **every downloadable file** is a check-box.  
  *Duplicates stay in-sync; already downloaded/installed items are
  greyed-out.*
* Queues any still-checked files via MO2’s
  `startDownloadNexusFile()` **and keeps a progress dialog open until
  the last one finishes**.
* Ignores its *own* downloads, so you never recurse forever.
* Optional trace log for debugging curious edge-cases.

However, it does NOT pull in any optional requirements. You'll still have to do some due diligence to make sure your mod installations are complete considering all your other in-use mods.

---

## ▶️ Quick start

|                           |                                                      |
|---------------------------|------------------------------------------------------|
| **Requires**              | • Mod Organizer ≥ **2.5** <br>• Python plug-in loader |
| **Install**               | 1. Download/clone the repo → `…\plugins\prereq_fetcher` <br>2. Check *Settings ▸ Plugins ▸ Prereq Fetcher* **enabled** |
| **Setup once**            | Paste your **Nexus API key** (used only to resolve friendly names & file lists). |
| **Use**                   | 1. Download *any* Nexus archive as usual <br>2. If that mod (recursively) has dependencies → a tree pops up <br>3. Tick/untick what you want → **OK** ⭐ |
| **Debug log**             | Set *Settings ▸ Plugins ▸ Prereq Fetcher ▸ debug* = **True** to write `plugins/prereq_fetcher/debug.log` |

---

## 📦 Features

| 🚩 | Feature |
|----|---------|
| 🔍 | **Recursive HTML scrape** – no MO2‐Nexus bridge required |
| ✔️ | Object-level selection: every “Main” file is a check-box |
| 🔄 | Duplicates propagate: tick it once, all identical leaves toggle |
| 🕵️‍♂️ | Detects *already downloaded* archives (downloads folder) **and** *already installed* mods (reads `meta.ini`) |
| 🛡️ | Never analyses a download it started itself |
| 🗺️ | Off-site rows are rendered as external hyperlinks |
| 🪵 | Optional *TRACE* log for support issues |

---

## 📂 Repository layout

