# OpenEnglishTranslation_adapter
An adapter/exporter to create custom versions of the *Open English Translation of the Bible*

## Running the program

`OET_adapter.py` is a single Python program with a simple Tkinter GUI. It only uses the Python standard library, so there's nothing extra to `pip install`.

### Requirements

- **Python 3.11 or later** (for the built-in `tomllib` module)
- **Tkinter** (Python's standard GUI toolkit; included with most Python installs)
- **Git** (optional, needed only to download the OET repo with `git clone` and refresh it with `git pull`; without it, use the "temporarily download the files" option)

### Windows

1. Install Python from https://www.python.org/downloads/ (Tkinter is included). Tick "Add python.exe to PATH" during installation.
2. Optionally install Git from https://git-scm.com/download/win
3. Open a Command Prompt in this folder and run:

```bash
py OET_adapter.py
```

(or double-click `OET_adapter.py` in File Explorer).

### macOS

1. Install Python from https://www.python.org/downloads/ (Tkinter is included).
   If you use Homebrew instead: `brew install python python-tk`
2. Git is available with the Xcode command line tools (`xcode-select --install`) or `brew install git`
3. Open Terminal in this folder and run:

```bash
python3 OET_adapter.py
```

### Linux

1. Make sure Python 3.11+ and Tkinter are installed, e.g.
   - Debian/Ubuntu: `sudo apt install python3 python3-tk git`
   - Fedora: `sudo dnf install python3 python3-tkinter git`
   - Arch: `sudo pacman -S python tk git`
2. Open a terminal in this folder and run:

```bash
python3 OET_adapter.py
```

## How the program works

### 1. Finding the OET source files

The program exports from the ESFM files in the [OET repo](https://GitHub.com/Freely-Given-org/OpenEnglishTranslation--OET).
At startup it looks for that repo in a parallel folder (`../OpenEnglishTranslation--OET`):

- If it's found, it asks whether to refresh it (`git pull`) before each export.
- If it's not found, you can download (`git clone`) it into the parallel folder or somewhere else, point to an existing copy, or just download the needed files temporarily from GitHub for each export.

These choices are saved in `globalSettings.toml` so you're only asked once. Use the **Change…** button to change them later.

### 2. Export settings

If you've saved export settings before (`*.export.toml` files), the program offers to re-use one.
Otherwise, or if you choose **New export settings…**, it asks these questions one at a time (with **Back**, **Next** and **Cancel** buttons):

| Question | Choices (default first) |
| --- | --- |
| Version(s) | OET-RV, OET-LV, or both |
| Books | Any combination of front matter, OT, DC, NT, back matter (default all) |
| Book order (if RV included) | OET-RV book order, or traditional order (used to number the ESFM and VPL files) |
| Included parts | Any combination (or none) of book introductions, section headings, footnotes, cross-references (default all) |
| Spelling | Remain in British spelling, or change to American spelling and terminology |
| Divine name (if RV included) | Leave ‘Yahweh’, or change to ‘the LORD’ |
| Names (if RV included) | Use the OET-RV names, or change back to traditional names |
| Word numbers | Remove them (and the `\rem WORDTABLE` line), or keep them |
| File types (if word numbers removed) | Any combination of ESFM, USFM (default), VPL |
| ESFM markers (if ESFM exported) | Leave the additional formatting markers, or just keep the essential ones |

If word numbers are kept, only ESFM files are exported.

Each question has a "Save this answer as a global setting" checkbox. Saved answers are stored in `globalSettings.toml` and then you can skip those questions in future
(the first page offers **No**, **Yes (skip questions with preselected global settings)**, or **Yes, and then delete all global export settings**).

When you finish, the settings are saved as `XXX.export.toml`, where `XXX` is built from your answers, e.g.
`RVLV_ALLBks_RVOrder_NoFNs_UK_LORD_TradNames_NoWordNums_ALLFormats_Simple`. The selected answers are shown in the main window.

### 3. Running the export

Click **Run export**. Files are written to `exportedFiles/XXX/` (if that folder already exists, you're asked before it's replaced).
`ESFM/`, `USFM/` and `VPL/` subfolders are only created when more than one file type is exported.

- USFM filenames start with the standard USFM (Paratext) book number, whatever book order was chosen, e.g. `01_OET-RV_GEN.USFM`, `41_OET-RV_MAT.USFM`, `68_OET-RV_TOB.USFM`, `A0_OET-RV_FRT.USFM`, `C3_OET-RV_LAO.USFM`.
- ESFM and VPL filenames start with a number (from 01) giving the chosen book order, e.g. with OET-RV order `01_OET-RV_FRT.ESFM`, `08_OET-RV_JOB.ESFM`, `01_OET-RV_GEN.vpl`, `06_OET-RV_JOB.vpl` (VPL has no front matter files as they have no verses).
- ESFM files keep the OET's own book codes (e.g. `OET-RV_KI1.ESFM`). USFM and VPL files use USFM book abbreviations (e.g. `OET-RV_1KI.USFM`).
- If word numbers are kept, the word table files that the ESFM files refer to are copied too.
- The OET text `LICENSE` file (CC BY-SA 4.0) is copied into the export folder.
- A `README.md` is written into the export folder. It covers:
  - the title (‘Adapted Open English Translation…’, or ‘…USA edition’)
  - the export date and the source (the OET repo commit, if it’s a local clone)
  - the contents, file types and export settings
  - a list of the changes from the original OET (as the licence requires)
  - the copyright, licence and suggested attribution
  - the upstream source attributions from the OET text folders’ own READMEs
- USFM files have the ESFM-specific formatting removed (based on `convert_OET-LV-RV_ESFM_to_USFM.py` in the OET repo):
  - `\add` fields that start with one of `+=<>≡&@*#%^$≈` (optionally with `?`) lose their markers but keep their text.
  - `\add !` name explanations become plain `\add` fields (or are deleted completely when changing back to traditional names).
  - Plain `\add` fields stay (any `?` at the start is removed).
  - The Psalm parallelism (`≈`) and reordering (`⇔`) markers are removed.
- ESFM files with "just keep the essential ones" get the same marker changes as the USFM files (but keep everything else ESFM).
- VPL files have one file per book, with one line per verse like `GEN 1:1<tab>verse text` (Psalm titles go in verse 0). All character formatting markers and the `≈` and `⇔` markers are removed.

### Text changes

In every exported file (RV and LV), each ‘Open English Translation’ and ‘OET’ (including ‘OET-RV’ and ‘OET-LV’) becomes ‘Adapted Open English Translation’ / ‘Adapted OET’, e.g. on `\id` lines and in the front matter and introductions. Figures (`\fig`), URLs and filenames (like the `\rem WORDTABLE` line) are left unchanged.

The exception is a **USA edition**: when American spelling is the only text change (all parts included, ‘Yahweh’ and the RV names left, all ESFM markers kept) and both the RV and LV are exported as ESFM files with word numbers. Then nothing is renamed to ‘Adapted’, and instead the RV `\id` lines get ‘USA edition’ before the version number, e.g. `\id MRK - Open English Translation—Readers' Version (OET-RV) USA edition v0.5.11`. (The book selection and book order don’t affect this.)

Whenever American spelling is chosen:

- the LV `\id` lines get ‘ USA edition’ added to the end, e.g. `\id MRK USA edition`
- the front matter (FRT) gets `\mt3 USA edition` before its first `\pc` line, and its `\li1` line about British spelling becomes ‘This USA edition has been created by changing some spelling and vocabulary from the British edition.’

These apply to the RV and LV:

- **Included parts:** Unselected parts are removed: book introductions (except in front and back matter books), section headings (including `\ms`, `\mr`, `\r`, `\sr` and the OET-RV’s extra `\rem /s1` headings), footnotes, and/or cross-references.
- **American spelling:** British spellings are changed using a built-in list (e.g. honour → honor, realise → realize, metre → meter, travelled → traveled, judgement → judgment, towards → toward, grey → gray, axe → ax, burnt → burned but not in ‘burnt offering(s)’ or ‘burnt sacrifice(s)’). Capitalisation is kept, and URLs, filenames and marker attributes aren’t changed. A few words are also changed to American terms: rubbish → garbage, corn → grain, tonnes → metric tons, biscuits → wafers, fortnight → two weeks. ‘Spelt’ becomes ‘spelled’ only where it’s about spelling (not the grain), and ‘Tyre’ (the city) is left alone.

These apply to the OET-RV only:

- **Traditional names:** where the text explains a name, e.g. `Yeshua \add !(Jesus; Grk. Yesus)\add*`, the whole thing becomes `Jesus`, and that choice is used for the rest of the book. Other names are changed using `OET-RV_names_table.tsv`, but only when the table gives one clear traditional name. Forms like `Havah/Eve` become `Eve`. Names that are ambiguous are left unchanged.
- **The LORD:** `Yahweh` becomes `the \nd Lord\nd*` (which is displayed as L + small-caps ORD), or `The` at the start of a sentence or heading. There's no article when Yahweh is being addressed (e.g. "Take action, LORD."). VPL files use plain `LORD`. Quoted mentions (‘Yahweh’), compound names (Yahweh-nissi), book introductions and footnotes aren't changed.

## Files

| File | Purpose |
| --- | --- |
| `OET_adapter.py` | The program |
| `globalSettings.toml` | Source repo settings and saved global export answers (created by the program) |
| `*.export.toml` | Saved, named export settings (created by the program) |
| `exportedFiles/` | Exported files |

## Additional notes

The format codes in the original *OET* [ESFM](https://GitHub.com/Freely-Given-org/ESFM) files are explained [here](https://OpenEnglishTranslation.Bible/Resources/Formats/).
