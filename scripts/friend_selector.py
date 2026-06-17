import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter import font as tkfont
import yaml
import json
import os
import threading
import urllib.request
from pathlib import Path

# Font setup
_FONT_FAMILY = "Segoe UI"
try:
    tkfont.Font(family=_FONT_FAMILY, size=10)
except:
    _FONT_FAMILY = "TkDefaultFont"

FONT = (_FONT_FAMILY, 10)
FONT_BOLD = (_FONT_FAMILY, 11, "bold")
FONT_SMALL = (_FONT_FAMILY, 9)

CONFIG_PATH = Path(__file__).parent / "config.yaml"
CACHE_PATH = Path(__file__).parent / ".friends_cache.json"


class FriendSelector:
    def __init__(self, root):
        self.root = root
        self.root.title("QQ Auto Reply - Friend Manager")
        self.root.geometry("600x520")
        self.root.resizable(False, False)

        self.friends = {}
        self.all_friends = []
        self.friend_vars = {}

        self.load_config()

        style = ttk.Style()
        style.configure(".", font=FONT)

        self.setup_ui()

    def load_config(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.friends = {}
            for item in data.get("friends", []):
                qq = item.get("qq")
                name = item.get("name", str(qq))
                if qq:
                    self.friends[int(qq)] = name

    def save_config(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["friends"] = [{"qq": qq, "name": name} for qq, name in self.friends.items()]
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        messagebox.showinfo("Saved", "Config saved. Restart the service to apply.")

    def setup_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="Friends configured for auto-reply:", font=FONT_BOLD).pack(anchor=tk.W)

        list_frame = ttk.Frame(main)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=FONT)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        self.refresh_list()

        btn1 = ttk.Frame(main)
        btn1.pack(fill=tk.X, pady=5)
        ttk.Button(btn1, text="Add Friend", command=self.add_friend).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn1, text="Remove Selected", command=self.remove_friend).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn1, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=3)

        ttk.Separator(main, orient="horizontal").pack(fill=tk.X, pady=8)

        ttk.Label(main, text="Fetch friends list from QQ:", font=FONT_BOLD).pack(anchor=tk.W)
        ttk.Label(main, text="Requires the auto-reply service to be running", foreground="gray", font=FONT_SMALL).pack(anchor=tk.W)

        btn2 = ttk.Frame(main)
        btn2.pack(fill=tk.X, pady=5)
        self.fetch_btn = ttk.Button(btn2, text="Fetch from QQ", command=self.fetch_friends)
        self.fetch_btn.pack(side=tk.LEFT, padx=3)
        ttk.Button(btn2, text="Select All", command=self.select_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn2, text="Deselect All", command=self.deselect_all).pack(side=tk.LEFT, padx=3)

        self.check_frame = ttk.Frame(main)
        self.check_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.load_cached_friends()

        btn3 = ttk.Frame(main)
        btn3.pack(fill=tk.X, pady=8)
        ttk.Button(btn3, text="Save Config", command=self.save_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn3, text="Close", command=self.root.destroy).pack(side=tk.RIGHT, padx=5)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for qq, name in self.friends.items():
            self.listbox.insert(tk.END, f"{qq}  ({name})")
        count = self.listbox.size()
        self.root.title(f"QQ Auto Reply - {count} friend(s)")

    def add_friend(self):
        qq = simpledialog.askstring("Add Friend", "Enter QQ number:", parent=self.root)
        if not qq:
            return
        qq = qq.strip()
        if not qq.isdigit():
            messagebox.showerror("Error", "QQ number must be digits only")
            return
        qq = int(qq)
        name = simpledialog.askstring("Add Friend", "Nickname (optional):", parent=self.root)
        name = name.strip() if name else str(qq)
        self.friends[qq] = name
        self.refresh_list()

    def remove_friend(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("Info", "Select a friend first")
            return
        text = self.listbox.get(sel[0])
        qq = int(text.split()[0])
        if qq in self.friends:
            del self.friends[qq]
            self.refresh_list()

    def clear_all(self):
        if messagebox.askyesno("Confirm", "Remove all friends from the list?"):
            self.friends.clear()
            self.refresh_list()

    def fetch_friends(self):
        self.fetch_btn.config(state="disabled", text="Fetching...")
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def _do_fetch(self):
        try:
            req = urllib.request.Request("http://127.0.0.1:8082/friends", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                self.all_friends = data.get("friends", [])
                with open(CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                self.root.after(0, self._update_checkboxes)
        except Exception as e:
            err = str(e)[:80]
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to fetch\n{err}"))
        finally:
            self.root.after(0, lambda: self.fetch_btn.config(state="normal", text="Fetch from QQ"))

    def load_cached_friends(self):
        if CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.all_friends = data.get("friends", [])
                self._update_checkboxes()
            except:
                pass

    def _update_checkboxes(self):
        for w in self.check_frame.winfo_children():
            w.destroy()
        self.friend_vars.clear()

        if not self.all_friends:
            ttk.Label(self.check_frame, text="No data. Click 'Fetch from QQ' to load.", foreground="gray", font=FONT_SMALL).pack()
            return

        canvas = tk.Canvas(self.check_frame, highlightthickness=0, bg="white")
        scrollbar = ttk.Scrollbar(self.check_frame, orient="vertical", command=canvas.yview)
        scroll_inner = ttk.Frame(canvas)
        scroll_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for item in self.all_friends:
            qq = item.get("qq", 0)
            nickname = item.get("nickname", str(qq))
            var = tk.BooleanVar(value=qq in self.friends)
            self.friend_vars[qq] = var
            cb = ttk.Checkbutton(scroll_inner, text=f"{qq}  ({nickname})", variable=var,
                command=lambda q=qq, v=var: self._on_check(q, v))
            cb.pack(anchor=tk.W, padx=5, pady=1)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _on_check(self, qq, var):
        if var.get():
            name = str(qq)
            for item in self.all_friends:
                if item.get("qq") == qq:
                    name = item.get("nickname", str(qq))
                    break
            self.friends[qq] = name
        else:
            self.friends.pop(qq, None)
        self.refresh_list()

    def select_all(self):
        for item in self.all_friends:
            qq = item.get("qq", 0)
            nickname = item.get("nickname", str(qq))
            self.friends[qq] = nickname
            if qq in self.friend_vars:
                self.friend_vars[qq].set(True)
        self.refresh_list()

    def deselect_all(self):
        self.friends.clear()
        for var in self.friend_vars.values():
            var.set(False)
        self.refresh_list()


if __name__ == "__main__":
    root = tk.Tk()
    app = FriendSelector(root)
    root.mainloop()
