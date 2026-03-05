"""
Claude Usage Scraper v6
ヘッドレスを廃止 → 画面外に隠した有頭ブラウザで動作（ボット検知回避）
"""
import threading, time, os, re, shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

USAGE_URL   = "https://claude.ai/settings/usage"
PROFILE_DIR = str(Path.home() / ".claude-monitor" / "profile")

on_data_update  = None
on_login_needed = None
on_login_done   = None
on_status       = None

_state = {
    "running": False,
    "force_refresh": False,
    "manual_login_done": False,
    "context": None,
}

def _log(msg, kind=None):
    print(f"[Scraper] {msg}")
    if on_status:
        on_status(msg, kind)

def _on_claude_ai(url):
    if not url or "claude.ai" not in url:
        return False
    bad = ["login", "oauth", "auth/", "signin", "accounts.google", "appleid.apple"]
    return not any(x in url for x in bad)

def _make_context(pw, for_login=False):
    """
    常に有頭で起動。
    - ログインフロー: 通常サイズ（ユーザーが操作できる）
    - バックグラウンド: 画面外に移動 + 最小化
    """
    os.makedirs(PROFILE_DIR, exist_ok=True)

    args = [
        "--no-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
    ]

    if not for_login:
        # バックグラウンド動作: 画面の外側に配置
        args += [
            "--window-position=-32000,-32000",
            "--window-size=1,1",
        ]

    return pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,  # 常にFalse
        args=args,
        ignore_default_args=["--enable-automation"],
        viewport={"width": 1280, "height": 800} if for_login else {"width": 1280, "height": 800},
        locale="ja-JP",
    )

def _wait_for_login(ctx, timeout=600):
    """ログイン完了を待つ（手動ボタン or URLで検知）"""
    _state["manual_login_done"] = False
    start = time.time()

    while time.time() - start < timeout:
        if not _state["running"]:
            return False
        if _state["manual_login_done"]:
            _log("手動でログイン完了を通知されました", "ok")
            return True
        try:
            for p in ctx.pages:
                try:
                    if _on_claude_ai(p.url):
                        body = p.inner_text("body") or ""
                        # ログインページより多いコンテンツがあればOK
                        if len(body) > 500:
                            _log(f"ログイン確認: {p.url[:60]}", "ok")
                            return True
                except:
                    pass
        except:
            pass
        time.sleep(1.5)

    return False

def _scrape(page):
    result = {
        "user": {}, "session": None, "weekly": None, "extra": None,
        "ts": int(time.time() * 1000)
    }

    # ページロードを待つ
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass

    try:
        page.wait_for_selector('[role="progressbar"]', timeout=15000)
        time.sleep(2)
    except PWTimeout:
        _log("progressbar なし、テキスト解析を試みます")

    # デバッグ: URLとbodyを確認
    current_url = page.url
    _log(f"スクレイプ中: {current_url[:60]}")

    body = ""
    try:
        body = page.inner_text("body") or ""
    except:
        pass

    _log(f"ページ文字数: {len(body)}")

    # ログインページに飛ばされていないか確認
    if not _on_claude_ai(current_url):
        _log(f"ログインページにリダイレクト: {current_url}", "error")
        return None  # Noneを返してセッション切れを通知

    try:
        js = page.evaluate("""() => {
            const r = {session:null, weekly:null, extra:null};
            const bars = [...document.querySelectorAll('[role="progressbar"]')];
            bars.forEach(el => {
                let pct = 0;
                const ws = el.style?.width || '';
                if (ws.includes('%')) pct = parseFloat(ws);
                else {
                    const vn = parseFloat(el.getAttribute('aria-valuenow')||'0');
                    const vm = parseFloat(el.getAttribute('aria-valuemax')||'100');
                    pct = vm>0 ? vn/vm*100 : 0;
                }
                let node = el.parentElement;
                for (let d=0; d<14; d++) {
                    if (!node) break;
                    const txt = (node.innerText||'').trim();
                    if (txt.length<5){node=node.parentElement;continue;}
                    if (!r.session && (txt.includes('セッション')||txt.includes('Session')||txt.includes('session'))) {
                        const pm=txt.match(/(\\d+(?:\\.\\d+)?)\\s*%/);
                        const rm=txt.match(/\\d+時間\\d+分後にリセット|\\d+時間後にリセット|\\d+分後にリセット|Resets in [^\\n]+/);
                        r.session={pct:pm?parseFloat(pm[1]):Math.round(pct),resetText:rm?rm[0]:null};break;
                    }
                    if (!r.weekly && (txt.includes('週間')||txt.includes('すべてのモデル')||txt.includes('All models')||txt.includes('weekly'))) {
                        const pm=txt.match(/(\\d+(?:\\.\\d+)?)\\s*%/);
                        const rm=txt.match(/\\d{1,2}:\\d{2}\\s*\\([月火水木金土日]\\)|[月火水木金土日]曜日/);
                        r.weekly={pct:pm?parseFloat(pm[1]):Math.round(pct),resetText:rm?rm[0]:null};break;
                    }
                    if (!r.extra && (txt.includes('追加使用量')||txt.includes('extra')||txt.includes('Additional'))) {
                        const pm=txt.match(/(\\d+(?:\\.\\d+)?)\\s*%/);
                        const um=txt.match(/\\$(\\d+\\.\\d+)\\s*使用/);
                        const lm=txt.match(/\\$(\\d+(?:\\.\\d+)?)\\s*(?:月間利用上限|上限)/);
                        const bm=txt.match(/\\$(\\d+\\.\\d+)\\s*(?:現在の残高|残高)/);
                        r.extra={pct:pm?parseFloat(pm[1]):Math.round(pct),
                                 used:um?'$'+um[1]:'$0.00',
                                 limit:lm?'$'+lm[1]:null,
                                 balance:bm?'$'+bm[1]:null};break;
                    }
                    node=node.parentElement;
                }
            });
            return r;
        }""")
        if js:
            result.update({k: v for k, v in js.items() if v is not None})
    except Exception as e:
        _log(f"JS解析エラー: {e}")

    # テキストフォールバック
    if not result["session"]:
        m = re.search(r'現在のセッション[\s\S]{0,300}?(\d+(?:\.\d+)?)\s*%', body)
        rm = re.search(r'(\d+時間\d+分後にリセット|\d+時間後にリセット|\d+分後にリセット)', body)
        if m: result["session"] = {"pct": float(m.group(1)), "resetText": rm.group(1) if rm else None}

    if not result["weekly"]:
        m = re.search(r'(?:すべてのモデル|週間制限)[\s\S]{0,300}?(\d+(?:\.\d+)?)\s*%', body)
        rm = re.search(r'(\d{1,2}:\d{2}\s*\([月火水木金土日]\))', body)
        if m: result["weekly"] = {"pct": float(m.group(1)), "resetText": rm.group(1) if rm else None}

    if not result["extra"]:
        sec = re.search(r'追加使用量[\s\S]{0,600}', body)
        if sec:
            t = sec.group(0)
            um = re.search(r'\$([\d.]+)\s*使用', t)
            lm = re.search(r'\$([\d]+)\s*月間利用上限', t)
            bm = re.search(r'\$([\d.]+)\s*現在の残高', t)
            pm = re.search(r'(\d+(?:\.\d+)?)\s*%', t)
            result["extra"] = {
                "pct":     float(pm.group(1)) if pm else 0,
                "used":    f'${um.group(1)}' if um else '$0.00',
                "limit":   f'${lm.group(1)}' if lm else None,
                "balance": f'${bm.group(1)}' if bm else None,
            }

    # ユーザー情報
    try:
        for ep in ['/api/account', '/api/organizations/me']:
            d = page.evaluate(f"""async () => {{
                try {{ const r=await fetch('{ep}',{{credentials:'include'}});
                       if(r.ok) return r.json(); }} catch{{}} return null;
            }}""")
            if d:
                u = d.get('account') or d.get('user') or d
                result["user"]["name"]  = u.get('name') or u.get('display_name')
                result["user"]["email"] = u.get('email')
                p = d.get('plan') or u.get('plan') or u.get('account_type')
                result["user"]["plan"]  = p if isinstance(p, str) else (p or {}).get('name') if p else None
                if result["user"].get("name") or result["user"].get("email"):
                    break
    except:
        pass

    return result


def notify_login_done():
    _state["manual_login_done"] = True


def _run(interval):
    with sync_playwright() as pw:

        # ── 起動時: 既存セッション確認（画面外で隠して実行）──
        _log("起動中... 既存セッションを確認しています")
        ctx = _make_context(pw, for_login=False)
        _state["context"] = ctx
        page = ctx.new_page()

        already_logged_in = False
        try:
            page.goto(USAGE_URL, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)
            if _on_claude_ai(page.url):
                body = page.inner_text("body") or ""
                _log(f"初回URL: {page.url[:60]}, body長: {len(body)}")
                if len(body) > 500:
                    already_logged_in = True
                    _log("既存セッション確認 ✓", "ok")
        except Exception as e:
            _log(f"初回確認エラー: {e}", "error")

        try:
            ctx.close()
        except:
            pass

        if not already_logged_in:
            # ── ログインフロー（通常サイズのウィンドウ）──
            _log("ログインが必要です", "login")
            ctx = _make_context(pw, for_login=True)
            _state["context"] = ctx

            if on_login_needed:
                on_login_needed()

            page = ctx.new_page()
            try:
                page.goto("https://claude.ai/login", timeout=20000)
            except:
                pass

            ok = _wait_for_login(ctx, timeout=600)

            try:
                ctx.close()
            except:
                pass

            if not ok:
                _log("ログインタイムアウト", "error")
                return

        _log("バックグラウンドモードで起動中...", None)
        if on_login_done:
            on_login_done()

        time.sleep(1)

        # ── バックグラウンド（画面外）でメインループ ──
        ctx = _make_context(pw, for_login=False)
        page = ctx.new_page()
        _state["context"] = ctx

        last_fetch = 0

        while _state["running"]:
            now   = time.time()
            force = _state.get("force_refresh", False)

            if force or (now - last_fetch) >= interval:
                _state["force_refresh"] = False
                _log("使用量を取得中...", "fetching")
                try:
                    page.goto(USAGE_URL, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)

                    data = _scrape(page)

                    if data is None:
                        # セッション切れ
                        _log("セッション切れ、再ログインします", "error")
                        try: ctx.close()
                        except: pass
                        ctx2 = _make_context(pw, for_login=True)
                        _state["context"] = ctx2
                        if on_login_needed:
                            on_login_needed()
                        p2 = ctx2.new_page()
                        try:
                            p2.goto("https://claude.ai/login", timeout=20000)
                        except:
                            pass
                        ok = _wait_for_login(ctx2, timeout=600)
                        try: ctx2.close()
                        except: pass
                        if not ok:
                            _log("再ログイン失敗", "error"); break
                        if on_login_done: on_login_done()
                        ctx = _make_context(pw, for_login=False)
                        page = ctx.new_page()
                        _state["context"] = ctx
                        continue

                    last_fetch = time.time()
                    has = bool(data.get("session") or data.get("weekly") or data.get("extra"))
                    _log("取得完了 ✓" if has else "取得済み（データ解析中）",
                         "ok" if has else "warn")
                    if on_data_update:
                        on_data_update(data)

                except Exception as e:
                    _log(f"エラー: {e}", "error")

            time.sleep(2)

        try: ctx.close()
        except: pass


def start(refresh_interval=60):
    if _state["running"]: return
    _state["running"] = True
    threading.Thread(target=_run, args=(refresh_interval,), daemon=True).start()

def stop():
    _state["running"] = False

def request_refresh():
    _state["force_refresh"] = True

def logout():
    stop()
    time.sleep(1)
    try:
        ctx = _state.get("context")
        if ctx:
            try: ctx.close()
            except: pass
    except: pass
    time.sleep(0.5)
    if os.path.exists(PROFILE_DIR):
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)
    _log("ログアウト完了", "warn")
