"""
src/ui/dashboard_recap.py
Dedicated module for the Post-Draft Recap screen.
Calculates and displays Pool Grades, Steals, Reaches, and Synergies.
"""

import tkinter
from tkinter import ttk
import threading
from src import constants
from src.ui.styles import Theme
from src.utils import open_file
from src.ui.components import ManaCurvePlot, TypePieChart, CardToolTip, AutoScrollbar
from src.card_logic import get_deck_metrics, identify_top_pairs
from collections import Counter
from src.archetype_loader import (
    archetype_file_exists,
    load_archetypes,
    get_archetype_counts,
)
from src.combo_loader import combo_file_exists, load_combos


class DraftRecapScreen(ttk.Frame):
    def __init__(self, parent, launch_sealed_callback=None, configuration=None):
        super().__init__(parent)
        self.launch_sealed_callback = launch_sealed_callback
        self.configuration = configuration
        self._dynamic_wrap_labels = []
        self._recap_archetypes_data = None
        self._recap_pool_names = []
        self._recap_arch_set = None
        self._recap_card_lookup = {}
        self._build_ui()
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.widget == self and event.width > 100:
            wrap_len = min(550, max(300, event.width - 60))
            for lbl in self._dynamic_wrap_labels:
                if lbl.winfo_exists():
                    lbl.configure(wraplength=wrap_len)

    def _create_stat_box(self, parent, title, text_var_name):
        frame = ttk.Labelframe(parent, text=title, padding=Theme.scaled_val(8))
        lbl = ttk.Label(frame, text="", font=Theme.scaled_font(9), justify="left")
        lbl.pack(anchor="nw", fill="both", expand=True)
        setattr(self, text_var_name, lbl)
        self._dynamic_wrap_labels.append(lbl)
        return frame

    def _make_scrolled_text(self, parent):
        """Create a read-only, vertically scrollable Text filling `parent`.

        Fonts and colors are applied centrally by _style_recap_text_widgets.
        """
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        text = tkinter.Text(
            parent,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=Theme.scaled_val(4),
            pady=Theme.scaled_val(4),
        )
        text.grid(row=0, column=0, sticky="nsew")
        scroll = AutoScrollbar(parent, orient="vertical", command=text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scroll.set, state="disabled")
        text.bind(
            "<MouseWheel>",
            lambda e: text.yview_scroll(int(-e.delta / 120), "units"),
        )
        return text

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # HEADER
        header_frame = ttk.Frame(
            self, padding=Theme.scaled_val(10), style="Card.TFrame"
        )
        header_frame.grid(row=0, column=0, sticky="ew")

        self.lbl_recovery_title = ttk.Label(
            header_frame,
            text="Draft Completed",
            font=Theme.scaled_font(18, "bold"),
            bootstyle="success",
        )
        self.lbl_recovery_title.pack(side="left")

        self.btn_17lands_link = ttk.Button(
            header_frame, text="View Draft on 17Lands 🌐", bootstyle="info-outline"
        )

        self.btn_sealed_studio = ttk.Button(
            header_frame,
            text="⚔️ Enter Sealed Studio",
            bootstyle="warning",
            command=self.launch_sealed_callback,
        )

        # TABBED CONTENT
        self.recap_notebook = ttk.Notebook(self)
        self.recap_notebook.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=Theme.scaled_val(10),
            pady=Theme.scaled_val((10, 0)),
        )

        # --- TAB 1: DRAFT RECAP ---
        tab_recap = ttk.Frame(self.recap_notebook, padding=Theme.scaled_val(15))
        self.recap_notebook.add(tab_recap, text=" 🏆 Draft Recap ")

        top_recap = ttk.Frame(tab_recap)
        top_recap.pack(fill="x", pady=Theme.scaled_val((0, 10)))

        self.lbl_recovery_grade = ttk.Label(
            top_recap,
            text="Pool Power Grade: --",
            font=Theme.scaled_font(16, "bold"),
            bootstyle="primary",
        )
        self.lbl_recovery_grade.pack(anchor="center", pady=Theme.scaled_val((0, 2)))

        self.lbl_recovery_stats = ttk.Label(
            top_recap, text="Top 23 Cards Avg Win Rate: --%", font=Theme.scaled_font(11)
        )
        self.lbl_recovery_stats.pack(anchor="center")

        self.lbl_actual_record = ttk.Label(
            top_recap, text="", font=Theme.scaled_font(11, "bold")
        )

        grid_recap = ttk.Frame(tab_recap)
        grid_recap.pack(fill="both", expand=True)
        grid_recap.columnconfigure((0, 1), weight=1)
        grid_recap.rowconfigure((0, 1), weight=1)

        self._create_stat_box(
            grid_recap, "TOP ARCHETYPES", "lbl_recap_archetypes"
        ).grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(grid_recap, "BEST CARDS DRAFTED", "lbl_recap_best").grid(
            row=0, column=1, sticky="nsew", padx=5, pady=5
        )
        self._create_stat_box(
            grid_recap, "BIGGEST STEALS (LATE PICKS)", "lbl_recap_steals"
        ).grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(
            grid_recap, "BIGGEST REACHES (EARLY PICKS)", "lbl_recap_reaches"
        ).grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        # --- TAB 2: SYNERGY & ROLES ---
        tab_synergy = ttk.Frame(self.recap_notebook, padding=Theme.scaled_val(15))
        self.recap_notebook.add(tab_synergy, text=" 🧩 Synergy & Roles ")

        grid_synergy = ttk.Frame(tab_synergy)
        grid_synergy.pack(fill="both", expand=True)
        grid_synergy.columnconfigure((0, 1), weight=1)
        grid_synergy.rowconfigure((0, 1), weight=1)

        self._create_stat_box(
            grid_synergy, "TOP CREATURE TYPES", "lbl_synergy_tribes"
        ).grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(grid_synergy, "CARD ROLES", "lbl_synergy_roles").grid(
            row=0, column=1, sticky="nsew", padx=5, pady=5
        )
        self._create_stat_box(
            grid_synergy, "PREMIUM STAPLES", "lbl_synergy_staples"
        ).grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(
            grid_synergy, "NON-BASIC LANDS", "lbl_synergy_lands"
        ).grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        # --- TAB 3: MANA & CURVE ---
        tab_analysis = ttk.Frame(self.recap_notebook, padding=Theme.scaled_val(15))
        self.recap_notebook.add(tab_analysis, text=" 📊 Mana & Curve ")
        tab_analysis.columnconfigure((0, 1), weight=1)
        tab_analysis.rowconfigure(0, weight=1)

        charts_frame = ttk.Frame(tab_analysis)
        charts_frame.grid(
            row=0, column=0, sticky="nsew", padx=Theme.scaled_val((0, 10))
        )

        ttk.Label(
            charts_frame,
            text="MANA CURVE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=Theme.scaled_val((0, 5)))
        self.recap_curve_plot = ManaCurvePlot(charts_frame, ideal_distribution=[])
        self.recap_curve_plot.pack(fill="x", pady=Theme.scaled_val((0, 15)))

        ttk.Label(
            charts_frame,
            text="POOL BALANCE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=Theme.scaled_val((0, 5)))
        self.recap_type_chart = TypePieChart(charts_frame)
        self.recap_type_chart.pack(fill="x")

        stats_col = ttk.Frame(tab_analysis)
        stats_col.grid(row=0, column=1, sticky="nsew")
        self._create_stat_box(stats_col, "RARES & MYTHICS", "lbl_recap_rares").pack(
            fill="both", expand=True, pady=Theme.scaled_val((0, 10))
        )

        # --- TAB 4: ARCHETYPES & COMBOS ---
        tab_ac = ttk.Frame(self.recap_notebook, padding=Theme.scaled_val(15))
        self.recap_notebook.add(tab_ac, text=" 🃏 Archetypes & Combos ")
        tab_ac.columnconfigure((0, 1), weight=1)
        tab_ac.rowconfigure(0, weight=1)

        # LEFT: archetype dropdown + breakdown
        ac_left = ttk.Frame(tab_ac)
        ac_left.grid(row=0, column=0, sticky="nsew", padx=Theme.scaled_val((0, 10)))
        ac_left.columnconfigure(0, weight=1)
        ac_left.rowconfigure(1, weight=1)

        selector = ttk.Frame(ac_left)
        selector.grid(row=0, column=0, sticky="ew", pady=Theme.scaled_val((0, 8)))
        ttk.Label(selector, text="Archetype:", font=Theme.scaled_font(9)).pack(
            side="left", padx=(0, Theme.scaled_val(6))
        )
        self.recap_arch_var = tkinter.StringVar(value="")
        self.recap_arch_dropdown = ttk.Combobox(
            selector, textvariable=self.recap_arch_var, state="readonly"
        )
        self.recap_arch_dropdown.pack(side="left", fill="x", expand=True)
        self.recap_arch_dropdown.bind(
            "<<ComboboxSelected>>", self._on_recap_archetype_change
        )

        arch_box = ttk.Labelframe(
            ac_left, text="ARCHETYPE BREAKDOWN", padding=Theme.scaled_val(8)
        )
        arch_box.grid(row=1, column=0, sticky="nsew")
        self.recap_archetype_text = self._make_scrolled_text(arch_box)

        # RIGHT: scrollable list of assembled combos
        combo_box = ttk.Labelframe(
            tab_ac, text="COMBOS ASSEMBLED", padding=Theme.scaled_val(8)
        )
        combo_box.grid(row=0, column=1, sticky="nsew")
        self.recap_combo_text = self._make_scrolled_text(combo_box)
        self.recap_combo_text.bind("<Button-1>", self._on_recap_combo_click)
        self.recap_combo_text.tag_bind(
            "card", "<Enter>", lambda e: self.recap_combo_text.config(cursor="hand2")
        )
        self.recap_combo_text.tag_bind(
            "card", "<Leave>", lambda e: self.recap_combo_text.config(cursor="")
        )
        self._style_recap_text_widgets()
        self.bind_all("<<ThemeChanged>>", self._on_recap_theme_change, add="+")

    def _style_recap_text_widgets(self):
        """(Re)apply colors, fonts, and tags to the two recap Text widgets."""
        try:
            if (
                getattr(self, "recap_archetype_text", None) is not None
                and self.recap_archetype_text.winfo_exists()
            ):
                self.recap_archetype_text.configure(
                    bg=Theme.BG_PRIMARY,
                    fg=Theme.TEXT_MAIN,
                    font=Theme.scaled_font(10),
                )
                self.recap_archetype_text.tag_configure(
                    "cat", font=Theme.scaled_font(10, "bold")
                )
            if (
                getattr(self, "recap_combo_text", None) is not None
                and self.recap_combo_text.winfo_exists()
            ):
                self.recap_combo_text.configure(
                    bg=Theme.BG_PRIMARY,
                    fg=Theme.TEXT_MAIN,
                    font=Theme.scaled_font(11),
                )
                self.recap_combo_text.tag_configure(
                    "card",
                    foreground=Theme.WARNING,
                    font=Theme.scaled_font(11, "bold"),
                )
                self.recap_combo_text.tag_configure(
                    "sep", font=Theme.scaled_font(11)
                )
        except tkinter.TclError:
            pass

    def _on_recap_theme_change(self, event=None):
        self._style_recap_text_widgets()

    def _on_recap_archetype_change(self, event=None):
        self._render_recap_archetype_counts()

    def _render_recap_archetype_counts(self):
        txt = self.recap_archetype_text
        txt.config(state="normal")
        txt.delete("1.0", "end")
        data = self._recap_archetypes_data
        label = self.recap_arch_var.get()
        key = (
            next((k for k, v in data.items() if v.get("label") == label), None)
            if data
            else None
        )
        if not data:
            txt.insert("end", "No archetype data for this set.")
        elif key is not None:
            counts = get_archetype_counts(key, self._recap_pool_names, data)
            if not counts:
                txt.insert("end", "No matching cards.")
            else:
                for entry in counts:
                    txt.insert(
                        "end", f"{entry['name']}: {entry['count']}\n", ("cat",)
                    )
                    matched = entry.get("matched_cards", {})
                    for cname in sorted(matched):
                        cnt = matched[cname]
                        disp = f"{cname} x{cnt}" if cnt > 1 else cname
                        txt.insert("end", f"    {disp}\n")
                    txt.insert("end", "\n")
        txt.config(state="disabled")

    def _insert_recap_combo_side(self, present):
        """Insert one side of a combo into the combos Text with gold card tags."""
        txt = self.recap_combo_text
        for i, (name, count) in enumerate(present):
            if i > 0:
                txt.insert("end", "/", ("sep",))
            disp = f"{name} x{count}" if count > 1 else name
            txt.insert("end", disp, ("card", f"cardname:{name}"))

    def _on_recap_combo_click(self, event):
        """Show the card-image popup for the combo card name that was clicked."""
        if not self.configuration:
            return
        txt = self.recap_combo_text
        index = txt.index(f"@{event.x},{event.y}")
        name = next(
            (
                t[len("cardname:") :]
                for t in txt.tag_names(index)
                if t.startswith("cardname:")
            ),
            None,
        )
        card = self._recap_card_lookup.get(name) if name else None
        if card:
            scale = constants.UI_SIZE_DICT.get(
                self.configuration.settings.ui_size, 1.0
            )
            CardToolTip.create(
                txt, card, self.configuration.features.images_enabled, scale
            )

    def _update_archetypes_combos(self, taken_cards, set_code):
        """Populate the Archetypes & Combos tab from the final pool."""
        self._recap_pool_names = [c.get("name", "") for c in taken_cards]
        self._recap_card_lookup = {c.get("name", ""): c for c in taken_cards}
        pool_counts = Counter(self._recap_pool_names)

        # Archetypes — only repopulate the dropdown when the set changes, so a
        # refresh tick never resets the user's current selection.
        self._recap_archetypes_data = (
            load_archetypes(set_code)
            if set_code and archetype_file_exists(set_code)
            else None
        )
        if set_code != self._recap_arch_set:
            self._recap_arch_set = set_code
            if self._recap_archetypes_data:
                labels = [v["label"] for v in self._recap_archetypes_data.values()]
                self.recap_arch_dropdown.configure(values=labels, state="readonly")
                self.recap_arch_var.set(labels[0] if labels else "")
            else:
                self.recap_arch_dropdown.configure(values=[], state="disabled")
                self.recap_arch_var.set("")
        self._render_recap_archetype_counts()

        # Combos — every combo whose anchor and at least one partner are both in
        # the pool. Both sides render in gold (the "card" tag); sides joined by an
        # arrow, copies shown as xN.
        combos = (
            load_combos(set_code) if set_code and combo_file_exists(set_code) else []
        )
        assembled = []
        for left, right in combos:
            left_present = [(n, pool_counts[n]) for n in left if n in pool_counts]
            right_present = [(n, pool_counts[n]) for n in right if n in pool_counts]
            if left_present and right_present:
                assembled.append((left_present, right_present))

        txt = self.recap_combo_text
        txt.config(state="normal")
        txt.delete("1.0", "end")
        if not combos:
            txt.insert("end", "No combo data for this set.")
        elif not assembled:
            txt.insert("end", "No assembled combos in this pool.")
        else:
            for left_present, right_present in assembled:
                self._insert_recap_combo_side(left_present)
                txt.insert("end", "  →  ", ("sep",))
                self._insert_recap_combo_side(right_present)
                txt.insert("end", "\n")
        txt.config(state="disabled")

    def update_summary(self, taken_cards, metrics, draft_id, event_type, set_code=""):
        if not taken_cards or len(taken_cards) < 40:
            return

        self.lbl_actual_record.pack_forget()
        self.btn_17lands_link.pack_forget()

        def get_gihwr(c):
            return float(
                c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            )

        valid_cards = [
            c
            for c in taken_cards
            if "Basic" not in c.get("types", [])
            and c.get("name") not in constants.BASIC_LANDS
        ]
        if not valid_cards:
            return

        # 1. OVERALL GRADE
        valid_cards.sort(key=get_gihwr, reverse=True)
        top_23 = valid_cards[:23]
        avg_gihwr = sum(get_gihwr(c) for c in top_23) / len(top_23)

        global_mean, global_std = (
            metrics.get_metrics("All Decks", "gihwr") if metrics else (54.5, 3.5)
        )
        if global_mean <= 0:
            global_mean = 54.5
        if global_std <= 0:
            global_std = 3.5

        z_score = (avg_gihwr - global_mean) / global_std
        pool_power = max(0, min(100, 75.0 + (z_score * 12.0)))

        grade_map = [
            (90, "S (God Tier)", "success"),
            (85, "A (Amazing)", "success"),
            (80, "B+ (Great)", "info"),
            (75, "B (Good)", "info"),
            (70, "C (Average)", "warning"),
            (60, "D (Below Average)", "danger"),
        ]
        grade_str, bootstyle = next(
            ((g, s) for threshold, g, s in grade_map if pool_power >= threshold),
            ("F (Trainwreck)", "danger"),
        )

        self.lbl_recovery_grade.config(
            text=f"Pool Quality: {pool_power:.0f}/100 [{grade_str}]",
            bootstyle=bootstyle,
        )
        self.lbl_recovery_stats.config(
            text=f"Top 23 Avg Win Rate: {avg_gihwr:.1f}% (Format Avg: {global_mean:.1f}%)"
        )

        # 2. TOP ARCHETYPES
        from src.utils import normalize_color_string

        top_pairs = identify_top_pairs(taken_cards, metrics)
        arch_data = []
        for pair in top_pairs:
            lane = normalize_color_string("".join(pair))
            wr, _ = metrics.get_metrics(lane, "gihwr") if metrics else (0, 0)
            arch_data.append((constants.COLOR_NAMES_DICT.get(lane, lane), wr))

        arch_data.sort(key=lambda x: x[1], reverse=True)
        arch_text = "".join(
            [f"• {n} ({w:.1f}%)\n" if w > 0 else f"• {n}\n" for n, w in arch_data[:3]]
        )
        self.lbl_recap_archetypes.config(
            text=arch_text if arch_text else "None Identified"
        )

        # 3. BEST CARDS
        best_text = "".join(
            [
                f"• {c.get('name', 'Unknown')} ({get_gihwr(c):.1f}%)\n"
                for c in top_23[:6]
            ]
        )
        self.lbl_recap_best.config(text=best_text)

        # 4. STEALS & REACHES
        total_cards = len(taken_cards)
        cards_per_pack = (
            15
            if total_cards >= 45
            else (
                14
                if total_cards >= 42
                else (total_cards // 3 if total_cards >= 3 else 14)
            )
        )

        steals, reaches = [], []
        for i, c in enumerate(taken_cards):
            name = c.get("name", "")
            if "Basic" in c.get("types", []) or name in constants.BASIC_LANDS:
                continue

            pack, pick = (i // cards_per_pack) + 1, (i % cards_per_pack) + 1
            gihwr, alsa, ata = (
                get_gihwr(c),
                float(c.get("deck_colors", {}).get("All Decks", {}).get("alsa", 0.0)),
                float(c.get("deck_colors", {}).get("All Decks", {}).get("ata", 0.0)),
            )

            if alsa > 0 and pick > alsa + 1.5 and gihwr >= 55.0:
                steals.append((name, pack, pick, alsa, pick - alsa))
            if ata > 0 and ata > pick + 1.5 and gihwr < 54.0:
                reaches.append((name, pack, pick, ata, ata - pick))

        steals.sort(key=lambda x: x[4], reverse=True)
        reaches.sort(key=lambda x: x[4], reverse=True)

        self.lbl_recap_steals.config(
            text="".join(
                [
                    f"• {n} (P{pa}P{pi} | ALSA {a:.1f} | +{d:.1f})\n"
                    for n, pa, pi, a, d in steals[:6]
                ]
            )
            or "No major steals detected."
        )
        self.lbl_recap_reaches.config(
            text="".join(
                [
                    f"• {n} (P{pa}P{pi} | ATA {a:.1f} | -{d:.1f})\n"
                    for n, pa, pi, a, d in reaches[:6]
                ]
            )
            or "No major reaches detected."
        )

        # 5. SYNERGY & ROLES
        subs_counts, tags_count, non_basics = {}, {}, []
        for c in taken_cards:
            if "Basic" in c.get("types", []) or c.get("name") in constants.BASIC_LANDS:
                continue
            if "Land" in c.get("types", []):
                non_basics.append(c)
            if "Creature" in c.get("types", []):
                for s in c.get("subtypes", []):
                    subs_counts[s] = subs_counts.get(s, 0) + 1
            for t in c.get("tags", []):
                tags_count[t] = tags_count.get(t, 0) + 1

        top_tribes = sorted(subs_counts.items(), key=lambda x: x[1], reverse=True)
        self.lbl_synergy_tribes.config(
            text="".join([f"• {t} ({c})\n" for t, c in top_tribes[:6] if c >= 3])
            or "No creature types with 3+ cards."
        )

        self.lbl_synergy_roles.config(
            text="".join(
                [
                    f"• {constants.TAG_VISUALS.get(t, t.capitalize())} ({c})\n"
                    for t, c in sorted(
                        tags_count.items(), key=lambda x: x[1], reverse=True
                    )[:6]
                ]
            )
            or "No Scryfall tags matched."
        )

        staples = [
            c
            for c in valid_cards
            if str(c.get("rarity", "")).lower() in ["common", "uncommon"]
            and get_gihwr(c) >= 57.0
        ]
        staples.sort(key=get_gihwr, reverse=True)
        self.lbl_synergy_staples.config(
            text="".join(
                [f"• {c.get('name')} ({get_gihwr(c):.1f}%)\n" for c in staples[:6]]
            )
            or "No premium staples drafted."
        )

        non_basics.sort(key=get_gihwr, reverse=True)
        self.lbl_synergy_lands.config(
            text="".join(
                [f"• {c.get('name')} ({get_gihwr(c):.1f}%)\n" for c in non_basics[:6]]
            )
            or "No non-basic lands drafted."
        )

        # 6. RARES & MYTHICS
        rares = [
            c
            for c in valid_cards
            if str(c.get("rarity", "")).lower() in ["rare", "mythic"]
        ]
        rares.sort(key=get_gihwr, reverse=True)
        self.lbl_recap_rares.config(
            text="".join(
                [f"• {c.get('name')} ({get_gihwr(c):.1f}%)\n" for c in rares[:10]]
            )
            or "No Rares or Mythics drafted."
        )

        # 7. CHARTS
        deck_metrics = get_deck_metrics(taken_cards)
        self.recap_curve_plot.update_curve(deck_metrics.distribution_all)

        type_counts = {
            "Creature": 0,
            "Planeswalker": 0,
            "Battle": 0,
            "Instant": 0,
            "Sorcery": 0,
            "Enchantment": 0,
            "Artifact": 0,
            "Land": 0,
        }
        for card in taken_cards:
            types = card.get("types", [])
            if "Basic" in types or card.get("name") in constants.BASIC_LANDS:
                continue
            for t in [
                "Creature",
                "Planeswalker",
                "Battle",
                "Instant",
                "Sorcery",
                "Enchantment",
                "Artifact",
                "Land",
            ]:
                if t in types:
                    type_counts[t] += 1
        self.recap_type_chart.update_counts(type_counts)

        # 8. SEALED STUDIO BTN
        if "Sealed" in (event_type or ""):
            self.btn_sealed_studio.pack(side="right", padx=Theme.scaled_val(10))
        else:
            self.btn_sealed_studio.pack_forget()

        # 9. 17LANDS API FETCH
        if draft_id:

            def fetch_17lands_record():
                from src.seventeenlands import Seventeenlands

                record = Seventeenlands().get_draft_record(draft_id)

                def apply_ui():
                    if record and record.get("wins") is not None:
                        w, l = record["wins"], record["losses"]
                        self.lbl_actual_record.config(
                            text=f"Actual 17Lands Record: {w} Wins - {l} Losses",
                            bootstyle=(
                                "success"
                                if w >= 3
                                else ("warning" if w >= 1 else "danger")
                            ),
                        )
                        self.lbl_actual_record.pack(
                            anchor="center", pady=Theme.scaled_val((5, 0))
                        )
                        self.btn_17lands_link.config(
                            command=lambda: open_file(record["url"])
                        )
                        self.btn_17lands_link.pack(
                            side="right", padx=Theme.scaled_val((0, 10))
                        )

                try:
                    self.after(0, apply_ui)
                except RuntimeError:
                    pass

            threading.Thread(target=fetch_17lands_record, daemon=True).start()

        # 10. ARCHETYPES & COMBOS TAB
        self._update_archetypes_combos(taken_cards, set_code)
