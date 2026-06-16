"""
Launcher GUI pour l'analyse d'adoption Butler.
Interface tkinter — aucune dépendance web, tout reste local.
4 fichiers en entrée : Conversations, Tickets ALL, Tickets CID, Hotel List
2 fichiers en sortie : General_adoption.xlsx, Adoption_per_week.xlsx
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import traceback
import re
from datetime import date

import pandas as pd
import adoption_2 as adoption


# =============================================================================
# Utilitaires lecture fichier
# =============================================================================

def read_file(path: str) -> pd.DataFrame:
    if path.endswith(".xlsx"):
        return pd.read_excel(path)
    if path.endswith(".csv"):
        for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin1"]:
            try:
                return pd.read_csv(path, encoding=encoding)
            except Exception:
                pass
        raise ValueError(f"Impossible de lire {path} avec les encodages testés.")
    raise ValueError(f"Format non supporté : {path}")


# =============================================================================
# Interface tkinter
# =============================================================================

BG = "#f5f5f5"
FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_LABEL = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 8)
FONT_BTN   = ("Segoe UI", 10)
BLUE       = "#0063b2"

FILE_SLOTS = [
    ("conv",     "Export Conversations (xlsx/csv)"),
    ("tickets",  "Export Tickets — ALL (xlsx/csv)"),
]

HOTEL_LIST_PATH = "hotel_list.csv"  # fichier figé dans le même dossier que l'exe


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analyse Adoption Butler")
        self.resizable(False, False)
        self.configure(padx=24, pady=20, bg=BG)

        # Stockage des chemins et DataFrames
        self.paths   = {k: tk.StringVar() for k, _ in FILE_SLOTS}
        self.dfs     = {k: None           for k, _ in FILE_SLOTS}
        self.dfs["hotels"] = None  # chargé depuis hotel_list.csv au démarrage

        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        row = 0

        # Titre
        tk.Label(self, text="Analyse Adoption Butler",
                 font=FONT_TITLE, bg=BG).grid(
            row=row, column=0, columnspan=3, pady=(0, 16), sticky="w")
        row += 1

        # Sections fichiers
        for key, label in FILE_SLOTS:
            tk.Label(self, text=label, font=FONT_LABEL, bg=BG).grid(
                row=row, column=0, sticky="w", pady=(6, 0))
            row += 1

            tk.Entry(self, textvariable=self.paths[key],
                     width=52, state="readonly").grid(
                row=row, column=0, columnspan=2, sticky="ew")

            tk.Button(self, text="Parcourir…", font=FONT_BTN,
                      command=lambda k=key: self._browse(k)).grid(
                row=row, column=2, padx=(8, 0))
            row += 1

        # Séparateur
        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=14)
        row += 1

        # Dates
        tk.Label(self, text="Période d'analyse :", font=FONT_LABEL, bg=BG).grid(
            row=row, column=0, columnspan=3, sticky="w")
        row += 1

        tk.Label(self, text="Du :", font=FONT_LABEL, bg=BG).grid(
            row=row, column=0, sticky="w", pady=(4, 0))
        self.start_entry = tk.Entry(self, width=14, font=FONT_LABEL, state="disabled")
        self.start_entry.grid(row=row, column=1, sticky="w", padx=(4, 0))
        row += 1

        tk.Label(self, text="Au :", font=FONT_LABEL, bg=BG).grid(
            row=row, column=0, sticky="w", pady=(4, 0))
        self.end_entry = tk.Entry(self, width=14, font=FONT_LABEL, state="disabled")
        self.end_entry.grid(row=row, column=1, sticky="w", padx=(4, 0))
        tk.Label(self, text="(AAAA-MM-JJ)", font=FONT_SMALL, bg=BG, fg="#888").grid(
            row=row, column=2, sticky="w", padx=(6, 0))
        row += 1

        # Séparateur
        ttk.Separator(self, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=14)
        row += 1

        # Bouton lancer
        self.btn_run = tk.Button(
            self, text="▶  Lancer l'analyse",
            font=("Segoe UI", 11, "bold"),
            bg=BLUE, fg="white", activebackground="#004f8f",
            padx=12, pady=6,
            command=self._run, state="disabled")
        self.btn_run.grid(row=row, column=0, columnspan=3, sticky="ew")
        row += 1

        # Progression
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=480)
        self.progress.grid(row=row, column=0, columnspan=3,
                           sticky="ew", pady=(10, 0))
        row += 1

        # Statut
        self.status_var = tk.StringVar(value="En attente des fichiers…")
        tk.Label(self, textvariable=self.status_var,
                 font=("Segoe UI", 9), bg=BG, fg="#444",
                 wraplength=480, justify="left").grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self.columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    def _browse(self, key: str):
        path = filedialog.askopenfilename(
            title=f"Sélectionner — {dict(FILE_SLOTS)[key]}",
            filetypes=[("Excel / CSV", "*.xlsx *.csv"), ("Tous", "*.*")]
        )
        if not path:
            return
        self.paths[key].set(path)
        self.status_var.set(f"Chargement de {path.split('/')[-1]}…")
        self.update()
        try:
            self.dfs[key] = read_file(path)
        except Exception as e:
            messagebox.showerror("Erreur de lecture", str(e))
            self.status_var.set("Erreur lors du chargement.")
            return

        self._try_unlock()

    # ------------------------------------------------------------------
    def _try_unlock(self):
        """Active les dates et le bouton dès que conv + tickets sont chargés."""
        conv    = self.dfs["conv"]
        tickets = self.dfs["tickets"]

        if conv is None or tickets is None:
            return

        try:
            conv_dates = pd.to_datetime(
                conv["started"].str.replace(" Europe/Paris", "", regex=False),
                errors="coerce"
            ).dt.tz_localize("Europe/Paris")
            ticket_dates = pd.to_datetime(tickets["Créé le"], errors="coerce")

            min_d = max(conv_dates.min().date(), ticket_dates.min().date())
            max_d = min(conv_dates.max().date(), ticket_dates.max().date())
        except Exception as e:
            messagebox.showerror("Erreur dates", str(e))
            return

        for entry, val in [(self.start_entry, min_d), (self.end_entry, max_d)]:
            entry.config(state="normal")
            entry.delete(0, tk.END)
            entry.insert(0, str(val))

        # Active le bouton dès que conv + tickets sont chargés
        if all(self.dfs[k] is not None for k, _ in FILE_SLOTS):
            self.btn_run.config(state="normal")
            self.status_var.set(
                f"✔ Fichiers chargés — période disponible : {min_d} → {max_d}"
            )
        else:
            missing = [label for (k, label) in FILE_SLOTS if self.dfs[k] is None]
            self.status_var.set(f"En attente : {', '.join(missing)}")

    # ------------------------------------------------------------------
    def _run(self):
        # Validation dates
        try:
            start = date.fromisoformat(self.start_entry.get().strip())
            end   = date.fromisoformat(self.end_entry.get().strip())
        except ValueError:
            messagebox.showerror("Date invalide", "Format attendu : AAAA-MM-JJ")
            return
        if start > end:
            messagebox.showerror("Dates invalides",
                                 "La date de début doit être avant la date de fin.")
            return

        # Choisir le dossier de sortie
        out_dir = filedialog.askdirectory(title="Dossier de sortie")
        if not out_dir:
            return

        out_general = f"{out_dir}/General_adoption_{start}_{end}.xlsx"
        out_pw      = f"{out_dir}/Adoption_per_week_{start}_{end}.xlsx"

        self.btn_run.config(state="disabled")
        self.progress.start(10)
        self.status_var.set("Analyse en cours…")

        def worker():
            try:
                hotels = read_file(HOTEL_LIST_PATH)
                global_adoption, adoption_pw = adoption.adoption_analytics(
                    self.dfs["conv"],
                    self.dfs["tickets"],
                    hotels,
                    start,
                    end,
                )
                global_adoption.to_excel(out_general, index=False)
                adoption_pw.to_excel(out_pw, index=False)
                self.after(0, lambda: self._on_success(out_general, out_pw,
                                                        len(global_adoption),
                                                        len(adoption_pw)))
            except Exception:
                err = traceback.format_exc()
                self.after(0, lambda: self._on_error(err))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    def _on_success(self, path_general, path_pw, n1, n2):
        self.progress.stop()
        self.btn_run.config(state="normal")
        self.status_var.set(f"✔ Analyse terminée — {n1} hôtels, {n2} lignes hebdo.")
        messagebox.showinfo(
            "Terminé",
            f"Analyse terminée !\n\n"
            f"• {n1} lignes → {path_general.split('/')[-1]}\n"
            f"• {n2} lignes → {path_pw.split('/')[-1]}\n\n"
            f"Fichiers enregistrés dans :\n{path_general.rsplit('/', 1)[0]}"
        )

    def _on_error(self, err):
        self.progress.stop()
        self.btn_run.config(state="normal")
        self.status_var.set("✘ Une erreur s'est produite.")
        messagebox.showerror("Erreur", f"L'analyse a échoué :\n\n{err}")


# =============================================================================

if __name__ == "__main__":
    app = App()
    app.mainloop()
