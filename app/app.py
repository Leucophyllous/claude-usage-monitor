"""Claude Usage Monitor - Standalone v5"""
import tkinter as tk
from tkinter import messagebox
import threading, time, os
from datetime import datetime
import scraper

BG='#ffffff'; BG2='#f5f5f5'; BORDER='#e0e0e0'
TEXT='#1a1a1a'; TEXT2='#666666'
BLUE='#1a73e8'; BLUE_L='#e8f0fe'
GREEN='#1e8e3e'; ORANGE='#e37400'; RED='#d93025'
ACCENT='#d97757'; HDR_BG='#0c0c18'; HDR_FG='#ffffff'

STATUS_COLORS = {
    "ok":       ('#4ade80', '#4ade80'),
    "warn":     ('#fbbf24', '#fbbf24'),
    "error":    ('#f87171', '#f87171'),
    "fetching": ('#60a5fa', '#60a5fa'),
    "login":    ('#fbbf24', '#fbbf24'),
    None:       ('#888899', '#555566'),
}

state = {"visible": True, "current_page": "main"}


class App:
    def __init__(self, root):
        self.root = root
        root.title("Claude Usage")
        root.geometry("460x640")
        root.minsize(380, 500)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.hide)
        self._last_data = None
        self._build()
        self._start_tray()
        self._start_scraper()

    # ── UI構築 ────────────────────────────────────────────

    def _build(self):
        hdr = tk.Frame(self.root, bg=HDR_BG, height=50)
        hdr.pack(fill='x'); hdr.pack_propagate(False)
        lf = tk.Frame(hdr, bg=HDR_BG); lf.pack(side='left', padx=16)
        tk.Label(lf, text="Claude", bg=HDR_BG, fg=HDR_FG,
                 font=('Helvetica',14,'bold')).pack(side='left')
        tk.Label(lf, text=".", bg=HDR_BG, fg=ACCENT,
                 font=('Helvetica',14,'bold')).pack(side='left')
        self.title_lbl = tk.Label(lf, text="Usage", bg=HDR_BG, fg=HDR_FG,
                                   font=('Helvetica',14,'bold'))
        self.title_lbl.pack(side='left')

        rf = tk.Frame(hdr, bg=HDR_BG); rf.pack(side='right', padx=12)
        self.settings_btn = tk.Button(rf, text="⚙", bg=HDR_BG, fg='#888',
            relief='flat', bd=0, font=('Helvetica',14), cursor='hand2',
            activebackground=HDR_BG, activeforeground=ACCENT,
            command=self.show_settings)
        self.settings_btn.pack(side='left', padx=3)
        self.refresh_btn = tk.Button(rf, text="↻", bg=HDR_BG, fg='#888',
            relief='flat', bd=0, font=('Helvetica',16), cursor='hand2',
            activebackground=HDR_BG, activeforeground=ACCENT,
            command=self.manual_refresh)
        self.refresh_btn.pack(side='left', padx=3)

        sb = tk.Frame(self.root, bg='#111122', height=28)
        sb.pack(fill='x'); sb.pack_propagate(False)
        self.sdot = tk.Label(sb, text="●", bg='#111122', fg='#444466', font=('Helvetica',8))
        self.sdot.pack(side='left', padx=(12,4))
        self.slbl = tk.Label(sb, text="起動中...", bg='#111122', fg='#888899', font=('Helvetica',9))
        self.slbl.pack(side='left')
        self.ts_lbl = tk.Label(sb, text="", bg='#111122', fg='#444455', font=('Helvetica',9))
        self.ts_lbl.pack(side='right', padx=12)

        cont = tk.Frame(self.root, bg=BG); cont.pack(fill='both', expand=True)
        self.cv = tk.Canvas(cont, bg=BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(cont, orient='vertical', command=self.cv.yview,
                                  bg=BG2, troughcolor=BG2)
        self.cv.configure(yscrollcommand=scrollbar.set)
        self.cv.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.fr = tk.Frame(self.cv, bg=BG)
        self.cw = self.cv.create_window((0,0), window=self.fr, anchor='nw')
        self.cv.bind('<Configure>', lambda e: self.cv.itemconfig(self.cw, width=e.width))
        self.fr.bind('<Configure>', lambda e: self.cv.configure(scrollregion=self.cv.bbox('all')))
        self.cv.bind_all('<MouseWheel>', lambda e: self.cv.yview_scroll(int(-1*(e.delta/120)),'units'))

        self._show_loading("起動中...")

    def _clear(self):
        for w in self.fr.winfo_children(): w.destroy()
        self.cv.yview_moveto(0)

    def set_status(self, msg, kind=None):
        fg, dot = STATUS_COLORS.get(kind, STATUS_COLORS[None])
        self.slbl.config(text=msg, fg=fg)
        self.sdot.config(fg=dot)

    # ── 各画面 ────────────────────────────────────────────

    def _show_loading(self, msg="データ取得中..."):
        self._clear()
        self.set_status(msg)
        pad = tk.Frame(self.fr, bg=BG); pad.pack(fill='both', padx=24, pady=60)
        tk.Label(pad, text="⏳", bg=BG, font=('',42)).pack(pady=(0,12))
        tk.Label(pad, text=msg, bg=BG, fg=TEXT2, font=('Helvetica',11)).pack()

    def show_login_prompt(self):
        self._clear()
        state["current_page"] = "login"
        self.set_status("ブラウザでログインしてください", "login")
        self.show()

        pad = tk.Frame(self.fr, bg=BG); pad.pack(fill='both', padx=24, pady=20)
        tk.Label(pad, text="🔐", bg=BG, font=('',44)).pack(pady=(0,8))
        tk.Label(pad, text="ログインが必要です", bg=BG, fg=TEXT,
                 font=('Helvetica',15,'bold')).pack()
        tk.Label(pad, text="自動で開いたブラウザでログインしてください", bg=BG, fg=TEXT2,
                 font=('Helvetica',10)).pack(pady=(4,14))

        # ガイドカード
        card = tk.Frame(pad, bg=BLUE_L, highlightbackground='#b8d0f0', highlightthickness=1)
        card.pack(fill='x')
        for num, txt in [
            ("①", "ブラウザが自動で開きます"),
            ("②", "Googleまたはメールでログイン"),
            ("③", "ログイン完了後、下の「ログイン完了」ボタンを押してください"),
        ]:
            row = tk.Frame(card, bg=BLUE_L); row.pack(fill='x', padx=14, pady=5)
            tk.Label(row, text=num, bg=BLUE_L, fg='#1a4080',
                     font=('Helvetica',10,'bold'), width=2).pack(side='left', anchor='n', pady=1)
            tk.Label(row, text=txt, bg=BLUE_L, fg='#1a3060',
                     font=('Helvetica',10), anchor='w', justify='left',
                     wraplength=310).pack(side='left', padx=6)

        # ── ログイン完了ボタン（大きく目立つ）──
        btn_f = tk.Frame(pad, bg=BG); btn_f.pack(fill='x', pady=(18, 4))
        self.login_done_btn = tk.Button(
            btn_f,
            text="✓  ログイン完了",
            bg=GREEN, fg='white',
            relief='flat', bd=0,
            font=('Helvetica', 13, 'bold'),
            cursor='hand2',
            activebackground='#178034',
            activeforeground='white',
            padx=20, pady=12,
            command=self._on_login_done_btn
        )
        self.login_done_btn.pack(fill='x')

        tk.Label(pad, text="ログインが完了したらこのボタンを押してください",
                 bg=BG, fg=TEXT2, font=('Helvetica',9)).pack(pady=(6,0))
        tk.Label(pad, text="※ ログイン情報はこのPCにのみ保存されます",
                 bg=BG, fg='#aaaaaa', font=('Helvetica',8)).pack(pady=(4,0))

    def _on_login_done_btn(self):
        """ログイン完了ボタン押下"""
        if hasattr(self, 'login_done_btn'):
            self.login_done_btn.config(
                text="処理中...", bg='#aaaaaa', state='disabled')
        self.set_status("ログイン確認中...", "fetching")
        # スクレイパーに通知
        scraper.notify_login_done()

    # ── メインデータ表示 ──────────────────────────────────

    def show_data(self, data):
        if state["current_page"] == "settings":
            self._last_data = data
            return

        self._clear()
        state["current_page"] = "main"
        self.title_lbl.config(text="Usage")
        self._last_data = data

        user     = data.get('user', {})
        session  = data.get('session')
        weekly   = data.get('weekly')
        extra    = data.get('extra')
        has_data = bool(session or weekly or extra)

        self.set_status("接続済み · 1分ごとに自動更新" if has_data else "データ解析中...",
                        "ok" if has_data else "warn")
        ts = data.get('ts')
        if ts:
            self.ts_lbl.config(
                text=f"更新: {datetime.fromtimestamp(ts/1000).strftime('%H:%M:%S')}")

        # ユーザーバー
        if user.get('name') or user.get('email'):
            ub = tk.Frame(self.fr, bg='#111122', height=44)
            ub.pack(fill='x'); ub.pack_propagate(False)
            ui = tk.Frame(ub, bg='#111122')
            ui.pack(fill='both', expand=True, padx=14)
            av = tk.Frame(ui, bg=ACCENT, width=28, height=28)
            av.pack(side='left', pady=8); av.pack_propagate(False)
            tk.Label(av,
                text=(user.get('name') or user.get('email','?'))[0].upper(),
                bg=ACCENT, fg='white', font=('Helvetica',12,'bold')).pack(expand=True)
            nm = user.get('name') or user.get('email','').split('@')[0]
            tk.Label(ui, text=nm, bg='#111122', fg='white',
                     font=('Helvetica',10,'bold')).pack(side='left', padx=8)
            if user.get('plan'):
                pf = tk.Frame(ui, bg='#2a1808',
                              highlightbackground='#6a3818', highlightthickness=1)
                pf.pack(side='right')
                tk.Label(pf, text=user['plan'].upper(), bg='#2a1808', fg=ACCENT,
                         font=('Helvetica',8,'bold'), padx=7, pady=2).pack()

        self._section("プラン使用制限")
        if session:
            self._bar_card("現在のセッション",
                           session.get('pct',0), session.get('resetText',''), BLUE)
        else:
            self._nodata("セッションデータなし")

        tk.Frame(self.fr, bg=BG, height=2).pack()
        tk.Label(self.fr, text="週間制限", bg=BG, fg=TEXT,
                 font=('Helvetica',11,'bold'), anchor='w').pack(fill='x', padx=20, pady=(10,0))
        if weekly:
            rt = weekly.get('resetText','')
            if rt and 'リセット' not in rt and 'reset' not in rt.lower():
                rt += " にリセット"
            self._bar_card("すべてのモデル", weekly.get('pct',0), rt, BLUE)
        else:
            self._nodata("週間制限データなし")

        self._section("追加使用量")
        if extra:
            self._bar_card(f"{extra.get('used','$0.00')} 使用",
                           extra.get('pct',0), "Apr 1 にリセット",
                           ORANGE if extra.get('pct',0) > 0 else '#aaaaaa')
            if extra.get('limit'):
                self._val_row(extra['limit'], "月間利用上限額", btn="上限を調整")
            if extra.get('balance'):
                bc = GREEN if extra['balance'] not in ('$0.00','$0') else TEXT2
                self._val_row(extra['balance'], "現在の残高", vc=bc, btn="追加購入")
        else:
            self._nodata("追加使用量データなし")

        if not has_data:
            w = tk.Frame(self.fr, bg='#fff8f0',
                         highlightbackground='#f0c080', highlightthickness=1)
            w.pack(fill='x', padx=20, pady=12)
            tk.Label(w, text="⚠ データを取得できませんでした", bg='#fff8f0', fg=ORANGE,
                     font=('Helvetica',9,'bold'), anchor='w', padx=12, pady=6).pack(fill='x')
            tk.Label(w, text="↻ ボタンで再試行してください", bg='#fff8f0', fg=TEXT2,
                     font=('Helvetica',9), anchor='w', padx=12, pady=4).pack(fill='x')

        tk.Frame(self.fr, bg=BG, height=20).pack()

    # ── 設定画面 ──────────────────────────────────────────

    def show_settings(self):
        self._clear()
        state["current_page"] = "settings"
        self.title_lbl.config(text="Usage  /  設定")
        self.set_status("設定", None)

        pad = tk.Frame(self.fr, bg=BG); pad.pack(fill='both')
        back_row = tk.Frame(pad, bg=BG2); back_row.pack(fill='x')
        tk.Button(back_row, text="← 戻る", bg=BG2, fg=BLUE, relief='flat', bd=0,
                  font=('Helvetica',10), cursor='hand2',
                  activebackground=BG2, activeforeground=BLUE,
                  command=self._back_to_main).pack(side='left', padx=14, pady=8)
        tk.Frame(pad, bg=BORDER, height=1).pack(fill='x')

        self._sect(pad, "アカウント")

        data = self._last_data or {}
        user  = data.get('user', {})
        name  = user.get('name')  or '未取得'
        email = user.get('email') or '未取得'
        plan  = user.get('plan')

        ucard = tk.Frame(pad, bg=BG); ucard.pack(fill='x', padx=20, pady=12)
        av = tk.Frame(ucard, bg=ACCENT, width=46, height=46)
        av.pack(side='left'); av.pack_propagate(False)
        init = (name if name != '未取得' else email if email != '未取得' else '?')[0].upper()
        tk.Label(av, text=init, bg=ACCENT, fg='white',
                 font=('Helvetica',20,'bold')).pack(expand=True)
        info = tk.Frame(ucard, bg=BG); info.pack(side='left', padx=12, fill='x', expand=True)
        tk.Label(info, text=name, bg=BG, fg=TEXT,
                 font=('Helvetica',12,'bold'), anchor='w').pack(fill='x')
        tk.Label(info, text=email, bg=BG, fg=TEXT2,
                 font=('Helvetica',10), anchor='w').pack(fill='x')
        if plan:
            pf = tk.Frame(info, bg='#fff0e8',
                          highlightbackground='#f0c090', highlightthickness=1)
            pf.pack(anchor='w', pady=(4,0))
            tk.Label(pf, text=plan.upper(), bg='#fff0e8', fg=ACCENT,
                     font=('Helvetica',9,'bold'), padx=7, pady=2).pack()

        tk.Frame(pad, bg=BORDER, height=1).pack(fill='x', padx=20, pady=(4,0))

        self._sect(pad, "アカウント操作")
        self._settings_action(pad,
            icon="🔄", title="アカウントを切り替える",
            desc="ログアウトして別のアカウントでログインし直します",
            color=BLUE, cmd=self._switch_account)
        self._settings_action(pad,
            icon="🚪", title="ログアウト",
            desc="保存されたログイン情報を削除します\n次回起動時に再ログインが必要です",
            color=RED, cmd=self._do_logout)

        self._sect(pad, "アプリ情報")
        info_f = tk.Frame(pad, bg=BG); info_f.pack(fill='x', padx=20, pady=8)
        for k, v in [("バージョン", "5.0"),
                     ("更新間隔", "1分ごと"),
                     ("プロファイル", "~/.claude-monitor/profile/")]:
            row = tk.Frame(info_f, bg=BG); row.pack(fill='x', pady=3)
            tk.Label(row, text=k, bg=BG, fg=TEXT2, font=('Helvetica',9),
                     width=14, anchor='w').pack(side='left')
            tk.Label(row, text=v, bg=BG, fg=TEXT, font=('Helvetica',9),
                     anchor='w').pack(side='left')

        tk.Frame(pad, bg=BG, height=30).pack()

    def _sect(self, parent, title):
        f = tk.Frame(parent, bg=BG2); f.pack(fill='x', pady=(8,0))
        tk.Label(f, text=title, bg=BG2, fg=TEXT2,
                 font=('Helvetica',9,'bold'), anchor='w',
                 padx=20, pady=5).pack(fill='x')
        tk.Frame(parent, bg=BORDER, height=1).pack(fill='x')

    def _settings_action(self, parent, icon, title, desc, color, cmd):
        outer = tk.Frame(parent, bg=BG, cursor='hand2'); outer.pack(fill='x')
        inner = tk.Frame(outer, bg=BG); inner.pack(fill='x', padx=20, pady=10)
        icon_l = tk.Label(inner, text=icon, bg=BG, font=('',18))
        icon_l.pack(side='left', padx=(0,10))
        txt = tk.Frame(inner, bg=BG); txt.pack(side='left', fill='x', expand=True)
        tl = tk.Label(txt, text=title, bg=BG, fg=color,
                      font=('Helvetica',11,'bold'), anchor='w'); tl.pack(fill='x')
        dl = tk.Label(txt, text=desc, bg=BG, fg=TEXT2,
                      font=('Helvetica',9), anchor='w',
                      justify='left', wraplength=300); dl.pack(fill='x')
        def enter(e):
            for w in [outer,inner,icon_l,txt,tl,dl]: w.config(bg=BG2)
        def leave(e):
            for w in [outer,inner,icon_l,txt,tl,dl]: w.config(bg=BG)
        for w in [outer,inner,icon_l,txt,tl,dl]:
            w.bind('<Button-1>', lambda e,c=cmd: c())
            w.bind('<Enter>', enter); w.bind('<Leave>', leave)
        tk.Frame(parent, bg=BORDER, height=1).pack(fill='x', padx=20)

    def _back_to_main(self):
        self.title_lbl.config(text="Usage")
        state["current_page"] = "main"
        if self._last_data:
            self.show_data(self._last_data)
        else:
            self._show_loading("データ取得中...")

    def _switch_account(self):
        if not messagebox.askyesno("アカウント切り替え",
                "現在のログイン情報を削除して\n別のアカウントでログインしますか？",
                parent=self.root):
            return
        self._clear(); self._show_loading("ログアウト中...")
        def do():
            scraper.logout()
            time.sleep(1)
            self.root.after(0, self._restart_scraper)
        threading.Thread(target=do, daemon=True).start()

    def _do_logout(self):
        if not messagebox.askyesno("ログアウト",
                "ログアウトしますか？\n次回起動時に再ログインが必要です。",
                parent=self.root):
            return
        self._clear(); self._show_loading("ログアウト中...")
        def do():
            scraper.logout()
            self.root.after(0, self._show_after_logout)
        threading.Thread(target=do, daemon=True).start()

    def _show_after_logout(self):
        self._clear()
        state["current_page"] = "main"
        self.title_lbl.config(text="Usage")
        self.set_status("ログアウト完了", "warn")
        pad = tk.Frame(self.fr, bg=BG); pad.pack(fill='both', padx=24, pady=60)
        tk.Label(pad, text="✓", bg=BG, fg=GREEN, font=('',52)).pack()
        tk.Label(pad, text="ログアウトしました", bg=BG, fg=TEXT,
                 font=('Helvetica',14,'bold')).pack(pady=(8,4))
        tk.Label(pad, text="アプリを再起動すると再ログインできます", bg=BG, fg=TEXT2,
                 font=('Helvetica',10)).pack()
        tk.Button(pad, text="アプリを終了", bg=RED, fg='white',
                  relief='flat', bd=0, font=('Helvetica',11,'bold'),
                  cursor='hand2', activebackground='#c02020',
                  padx=20, pady=10,
                  command=lambda: os._exit(0)).pack(pady=24)

    def _restart_scraper(self):
        self._last_data = None
        state["current_page"] = "main"
        self.title_lbl.config(text="Usage")
        self._start_scraper()

    # ── UIパーツ ──────────────────────────────────────────

    def _section(self, title):
        tk.Frame(self.fr, bg=BORDER, height=1).pack(fill='x', pady=(14,0))
        tf = tk.Frame(self.fr, bg=BG2); tf.pack(fill='x')
        tk.Label(tf, text=title, bg=BG2, fg=TEXT,
                 font=('Helvetica',12,'bold'), anchor='w',
                 padx=20, pady=8).pack(fill='x')
        tk.Frame(self.fr, bg=BORDER, height=1).pack(fill='x')

    def _bar_card(self, label, pct, sub, color):
        pct = max(0, min(100, pct or 0))
        card = tk.Frame(self.fr, bg=BG); card.pack(fill='x', padx=20, pady=10)
        top = tk.Frame(card, bg=BG); top.pack(fill='x', pady=(0,2))
        tk.Label(top, text=label, bg=BG, fg=TEXT,
                 font=('Helvetica',11,'bold'), anchor='w').pack(side='left')
        pc = RED if pct >= 80 else (ORANGE if pct >= 60 else TEXT2)
        tk.Label(top, text=f"{pct:.0f}% 使用済み", bg=BG, fg=pc,
                 font=('Helvetica',10)).pack(side='right')
        if sub:
            tk.Label(card, text=sub, bg=BG, fg=TEXT2,
                     font=('Helvetica',9), anchor='w').pack(fill='x', pady=(0,4))
        track = tk.Canvas(card, height=12, bg='#e8e8e8', highlightthickness=0, bd=0)
        track.pack(fill='x')
        def draw(e=None, c=track, p=pct, col=color):
            c.delete('all'); w = c.winfo_width() or 400
            c.create_rectangle(0,0,w,12, fill='#e0e0e0', outline='')
            if p > 0:
                c.create_rectangle(0,0,max(12,int(w*p/100)),12,fill=col,outline='')
        track.bind('<Configure>', draw)
        self.root.after(80, draw)
        tk.Frame(self.fr, bg=BORDER, height=1).pack(fill='x', pady=(8,0))

    def _val_row(self, value, sub, vc=TEXT, btn=None):
        row = tk.Frame(self.fr, bg=BG); row.pack(fill='x', padx=20, pady=8)
        lf = tk.Frame(row, bg=BG); lf.pack(side='left', fill='x', expand=True)
        tk.Label(lf, text=value, bg=BG, fg=vc,
                 font=('Helvetica',13,'bold'), anchor='w').pack(fill='x')
        tk.Label(lf, text=sub, bg=BG, fg=TEXT2,
                 font=('Helvetica',9), anchor='w').pack(fill='x')
        if btn:
            tk.Button(row, text=btn, bg=BG, fg=BLUE, relief='groove', bd=1,
                      font=('Helvetica',9), cursor='hand2',
                      activebackground=BLUE_L, padx=8, pady=4).pack(side='right')
        tk.Frame(self.fr, bg=BORDER, height=1).pack(fill='x')

    def _nodata(self, msg):
        tk.Label(self.fr, text=f"  {msg}", bg=BG, fg=TEXT2,
                 font=('Helvetica',9), anchor='w').pack(fill='x', padx=20, pady=6)

    # ── スクレイパー ──────────────────────────────────────

    def _start_scraper(self):
        scraper.on_data_update  = lambda d: self.root.after(0, lambda: self.show_data(d))
        scraper.on_login_needed = lambda:   self.root.after(0, self.show_login_prompt)
        scraper.on_login_done   = lambda:   self.root.after(0, lambda: self._show_loading("データ取得中..."))
        scraper.on_status       = lambda m, k=None: self.root.after(0, lambda: self.set_status(m, k))
        scraper.start(refresh_interval=60)

    def manual_refresh(self):
        self.refresh_btn.config(fg=ACCENT)
        self.root.after(1500, lambda: self.refresh_btn.config(fg='#888'))
        self.set_status("更新中...", "fetching")
        scraper.request_refresh()

    def hide(self):
        self.root.withdraw(); state["visible"] = False

    def show(self):
        self.root.deiconify(); self.root.lift(); state["visible"] = True

    def toggle(self):
        self.hide() if state["visible"] else self.show()

    def _start_tray(self):
        try:
            from PIL import Image, ImageDraw
            import pystray
            def mki(sz=64):
                img = Image.new('RGBA',(sz,sz),(0,0,0,0))
                d = ImageDraw.Draw(img)
                d.ellipse([2,2,sz-2,sz-2], fill=(217,119,87,255))
                r=sz//2-10; cx,cy=sz//2,sz//2
                d.arc([cx-r,cy-r,cx+r,cy+r],40,320,fill='white',width=max(4,sz//10))
                return img
            menu = pystray.Menu(
                pystray.MenuItem("表示/非表示", lambda i,it: self.root.after(0,self.toggle), default=True),
                pystray.MenuItem("今すぐ更新",  lambda i,it: self.root.after(0,self.manual_refresh)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", lambda i,it: (scraper.stop(), i.stop(), self.root.after(0,self.root.destroy))),
            )
            icon = pystray.Icon("cu", mki(), "Claude Usage", menu)
            threading.Thread(target=icon.run, daemon=True).start()
        except ImportError:
            pass


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
