import flet as ft
from database.db_manager import init_db
from utils.learning_engine import LearningEngine
from utils.voice_manager import VoiceManager
import sqlite3
import random
import asyncio
import threading
import pykakasi
import time
import os
import sys

class SproutaApp:
    # デバッグログの有効/無効を切り替えるフラグ
    DEBUG = True

    def log(self, message):
        if self.DEBUG:
            print(f"[DEBUG] {message}")

    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Sprouta - たのしくおべんきょう"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        
        # Flet 0.84.0 (1.0) の新しいウィンドウ設定API
        self.page.window.width = 1200
        self.page.window.height = 1000
        self.page.window.min_width = 800
        self.page.window_min_height = 600
        self.page.padding = 30
        self.page.bgcolor = "#F0F4F8"
        
        # 漢字をひらがなに変換するための設定
        self.kks = pykakasi.kakasi()
        
        self.current_user_id = None
        self.current_user_name = None
        self.current_module = None
        self.current_input_method = None
        self.voice_attempts = 0
        self.engine = None
        self.voice_manager = VoiceManager()
        self.is_voice_mode_active = False
        
        # オーディオファイルのパス設定 (assets/sounds/*.mp3)
        self.audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "sounds")
        
        self.voice_lock = threading.Lock()
        self.ui_lock = threading.Lock()
        self.is_listening = False
        self.is_handling_answer = False
        self.voice_timer = None
        self.session_id = 0 # 画面遷移を管理するためのセッションID
        
        self.log("アプリケーションを初期化中...")
        init_db()
        # Persistent DB connection for performance
        self.db_conn = sqlite3.connect("sprouta.db", check_same_thread=False)
        self.log("データベースに接続しました。")
        
        # 非同期で初期画面を表示
        asyncio.create_task(self.setup_app())

    async def setup_app(self):
        await self.show_profile_selection()

    async def play_sound(self, sound_name):
        """macOSのafplayコマンドを使用して非同期で音を鳴らす"""
        sound_path = os.path.join(self.audio_dir, f"{sound_name}.mp3")
        if sys.platform == "darwin" and os.path.exists(sound_path):
            try:
                # 非同期でコマンド実行（完了を待たないのでGUIが止まらない）
                await asyncio.create_subprocess_exec("afplay", sound_path)
            except Exception as e:
                self.log(f"音声再生エラー: {e}")

    async def speak_text(self, text):
        """macOSのsayコマンドを使用してテキストをゆっくり2回読み上げる"""
        if sys.platform == "darwin":
            try:
                # 日本語読み上げに特化した声を指定
                voice = "Kyoko"
                
                # 'へ' が正しく発音されない問題への対策（読みを固定）
                speech_text = text.replace("へ", "he")
                
                # 速度を落として読み上げる
                await asyncio.create_subprocess_exec("say", "-v", voice, "-r", "120", speech_text)
                await asyncio.sleep(1.2)
                await asyncio.create_subprocess_exec("say", "-v", voice, "-r", "120", speech_text)
            except Exception as e:
                self.log(f"音声合成エラー: {e}")

    async def show_profile_selection(self):
        self.log("プロフィール選択画面を表示します。")
        self.is_voice_mode_active = False
        self.page.clean()
        
        header = ft.Column([
            ft.Text("🌱 Sprouta 🌿", size=60, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
            ft.Text("たのしく おべんきょう しよう！", size=24, weight=ft.FontWeight.W_500, color="#555555"),
            ft.Container(height=20),
            ft.Text("だれが おべんきょう する？", size=32, weight=ft.FontWeight.BOLD, color="#333333")
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        profiles_row = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=40, wrap=True)
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id, name, avatar FROM users")
        users = cursor.fetchall()
        
        for user_id, name, avatar in users:
            profiles_row.controls.append(self.create_profile_card(user_id, name, avatar))
            
        profiles_row.controls.append(
            ft.Column([
                ft.Container(
                    content=ft.Icon(ft.Icons.ADD, size=60, color=ft.Colors.BLUE_400),
                    width=140, height=140, border_radius=70, bgcolor=ft.Colors.WHITE,
                    alignment=ft.Alignment.CENTER, 
                    on_click=lambda _: asyncio.create_task(self.show_add_profile()), 
                    ink=True,
                    shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK_12)
                ),
                ft.Text("あたらしくつくる", size=18, weight=ft.FontWeight.W_500)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
        
        self.page.add(
            ft.Container(
                content=ft.Column([
                    header,
                    ft.Container(height=60),
                    profiles_row,
                    ft.Container(expand=True),
                    ft.Row([ft.Text("🐘🦒🦓", size=40)], alignment=ft.MainAxisAlignment.CENTER)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, expand=True),
                padding=50,
                expand=True
            )
        )
        self.page.update()

    def create_profile_card(self, user_id, name, avatar):
        emoji = avatar if avatar else "👤"
        return ft.Column([
            ft.Container(
                content=ft.Text(emoji, size=70),
                width=140, height=140, border_radius=70, bgcolor=ft.Colors.WHITE,
                alignment=ft.Alignment.CENTER, 
                on_click=lambda _: asyncio.create_task(self.start_learning(user_id, name)),
                ink=True,
                shadow=ft.BoxShadow(
                    blur_radius=15, 
                    color=ft.Colors.BLACK_12,
                    offset=ft.Offset(0, 5)
                )
            ),
            ft.Text(name, size=22, weight=ft.FontWeight.BOLD)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    async def show_add_profile(self):
        self.log("プロフィール作成ダイアログを開きます。")
        name_input = ft.TextField(label="おなまえ", width=300, border_radius=15)
        
        # 選択可能な絵文字リスト
        avatars = ["🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐸", "🐷", "🐧"]
        selected_avatar = {"value": avatars[0]}

        avatar_row = ft.Row(wrap=True, width=300, alignment=ft.MainAxisAlignment.CENTER)
        
        def on_avatar_click(e, av):
            selected_avatar["value"] = av
            for ctrl in avatar_row.controls:
                ctrl.bgcolor = ft.Colors.TRANSPARENT
            e.control.bgcolor = ft.Colors.BLUE_100
            self.page.update()

        for av in avatars:
            avatar_row.controls.append(
                ft.Container(
                    content=ft.Text(av, size=30),
                    on_click=lambda e, a=av: on_avatar_click(e, a),
                    padding=5,
                    border_radius=10,
                    bgcolor=ft.Colors.BLUE_100 if av == selected_avatar["value"] else ft.Colors.TRANSPARENT
                )
            )

        async def close_dlg(e):
            dialog.open = False
            self.page.update()

        async def save_profile(e):
            if name_input.value:
                self.log(f"新しいプロフィールを保存中: {name_input.value} (Avatar: {selected_avatar['value']})")
                cursor = self.db_conn.cursor()
                cursor.execute("INSERT INTO users (name, avatar) VALUES (?, ?)", (name_input.value, selected_avatar["value"]))
                self.db_conn.commit()
                dialog.open = False
                self.page.update()
                await self.show_profile_selection()

        dialog = ft.AlertDialog(
            title=ft.Text("あたらしいプロフィール"),
            content=ft.Column([
                name_input,
                ft.Text("アバターをえらんでね"),
                avatar_row
            ], tight=True, spacing=10),
            actions=[
                ft.TextButton("キャンセル", on_click=close_dlg),
                ft.Button("保存", on_click=save_profile, bgcolor=ft.Colors.ORANGE_400, color=ft.Colors.WHITE)
            ]
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    async def start_learning(self, user_id, name):
        self.current_user_id = user_id
        self.current_user_name = name
        await self.show_main_dashboard()

    async def show_main_dashboard(self):
        self.is_voice_mode_active = False
        self.page.clean()
        
        # ユーザー情報の取得（スター数など）
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT stars, avatar FROM users WHERE id = ?", (self.current_user_id,))
        stars, avatar = cursor.fetchone()

        welcome_row = ft.Row([
            ft.Row([
                ft.Container(content=ft.Text(avatar, size=40), bgcolor=ft.Colors.WHITE, border_radius=20, padding=5),
                ft.Column([
                    ft.Text(f"こんにちは、{self.current_user_name}ちゃん！", size=24, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.Row([ft.Icon(ft.Icons.STAR, color=ft.Colors.AMBER, size=20), ft.Text(f"{stars} こ あつめたよ！", size=16, weight=ft.FontWeight.W_500)]),
                        ft.VerticalDivider(width=10),
                        ft.TextButton("シール帳をみる 📒", on_click=lambda _: asyncio.create_task(self.show_sticker_book()))
                    ])
                ], spacing=0)
            ]),
            ft.IconButton(icon=ft.Icons.SETTINGS, icon_size=30, on_click=lambda _: asyncio.create_task(self.show_parental_dashboard()), tooltip="ほごしゃメニュー")
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        modules = ft.Row([
            self.create_module_card("ひらがな", "#FF9AA2", "あ", "🐱"),
            self.create_module_card("カタカナ", "#B5EAD7", "ア", "🐶"),
            self.create_module_card("アルファベッド", "#FFDAC1", "ABC", "🦊"),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=30, wrap=True)
        
        decoration_row = ft.Row([
            ft.Text("🐘", size=40), ft.Text("🦒", size=40), ft.Text("🦓", size=40), ft.Text("🐆", size=40)
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=20)

        self.page.add(
            ft.Container(
                content=ft.Column([
                    welcome_row,
                    ft.Container(height=40),
                    ft.Row([ft.Text("なにをおべんきょうする？", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_GREY_700)], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(height=20),
                    modules,
                    ft.Container(height=40),
                    decoration_row,
                    ft.Container(expand=True),
                    ft.Row([ft.Text("応援してるよ！頑張ろうね 🌟", size=16, color=ft.Colors.GREY_500)], alignment=ft.MainAxisAlignment.CENTER)
                ], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                expand=True
            )
        )
        self.page.update()

    def create_module_card(self, title, color_hex, display_text, animal_emoji):
        return ft.Container(
            content=ft.Column([
                ft.Text(animal_emoji, size=50),
                ft.Text(display_text, size=60, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(title, size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=240,
            height=280,
            bgcolor=color_hex,
            border_radius=35,
            on_click=lambda _: asyncio.create_task(self.start_learning_session(title)),
            ink=True,
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(blur_radius=15, color=ft.Colors.BLACK_12, offset=ft.Offset(0, 10))
        )

    async def show_sticker_book(self):
        self.page.clean()
        
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT stars FROM users WHERE id = ?", (self.current_user_id,))
        stars = cursor.fetchone()[0]
        
        # 10スターごとに1つのシールを獲得
        sticker_list = ["🦁", "🐯", "🦒", "🐘", "🦓", "🐼", "🐨", "🐰", "🦊", "🐶", "🐱", "🐭", "🐹", "🐻"]
        earned_count = min(stars // 10, len(sticker_list))
        
        sticker_grid = ft.GridView(
            expand=True,
            runs_count=5,
            max_extent=120,
            child_aspect_ratio=1.0,
            spacing=20,
            run_spacing=20,
        )
        
        for i in range(len(sticker_list)):
            if i < earned_count:
                # 獲得済みシール
                sticker_grid.controls.append(
                    ft.Container(
                        content=ft.Text(sticker_list[i], size=50),
                        bgcolor=ft.Colors.AMBER_100,
                        border_radius=20,
                        alignment=ft.Alignment.CENTER,
                        shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.BLACK_12)
                    )
                )
            else:
                # 未獲得シール
                sticker_grid.controls.append(
                    ft.Container(
                        content=ft.Icon(ft.Icons.LOCK, color=ft.Colors.GREY_400, size=30),
                        bgcolor=ft.Colors.GREY_200,
                        border_radius=20,
                        alignment=ft.Alignment.CENTER,
                        tooltip="あとちょっとで もらえるよ！"
                    )
                )
        
        self.page.add(
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: asyncio.create_task(self.show_main_dashboard())),
                        ft.Text("シール帳 📒", size=32, weight=ft.FontWeight.BOLD)
                    ]),
                    ft.Container(height=20),
                    ft.Text(f"いままで あつめた スター: {stars} こ", size=20, weight=ft.FontWeight.W_500),
                    ft.Text(f"あと {10 - (stars % 10)} こで つぎのシールが もらえるよ！", size=16, color=ft.Colors.BLUE_GREY_400),
                    ft.Container(height=20),
                    sticker_grid
                ], expand=True),
                padding=20,
                expand=True
            )
        )
        self.page.update()

    async def start_learning_session(self, module_type):
        self.session_id += 1 
        self.engine = LearningEngine(module_type)
        self.current_module = module_type
        await self.show_input_method_selection()

    async def show_input_method_selection(self):
        self.page.clean()
        header = ft.Text("どうやって こたえる？", size=40, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_GREY_800)
        
        methods = ft.Row([
            self.create_method_card_async("ボタンでえらぶ", ft.Icons.TOUCH_APP, "#FFC8A2", "click"),
            self.create_method_card_async("キーボードでうつ", ft.Icons.KEYBOARD, "#D4F1F4", "keyboard"),
            self.create_method_card_async("こえでいう", ft.Icons.MIC, "#E2F0CB", "voice"),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=25, wrap=True)
        
        methods_listening = ft.Row([
            self.create_method_card_async("音をきく\n(1文字)", ft.Icons.VOLUME_UP, "#F9D1D1", "listening"),
            self.create_method_card_async("音をきく\n(単語)", ft.Icons.HEADSET, "#E1CCEC", "listening_word"),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=25, wrap=True)
        
        self.page.add(
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: asyncio.create_task(self.show_main_dashboard()))
                    ], alignment=ft.MainAxisAlignment.START),
                    ft.Row([header], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(height=40),
                    methods,
                    ft.Container(height=20),
                    methods_listening,
                    ft.Container(expand=True),
                    ft.Row([ft.Text("👂 よくきいて、こたえてね 👂", size=16, color=ft.Colors.GREY_500)], alignment=ft.MainAxisAlignment.CENTER)
                ], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                expand=True
            )
        )
        self.page.update()

    def create_method_card_async(self, title, icon, color_hex, method_key):
        return ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=60, color=ft.Colors.BLUE_GREY_700),
                ft.Text(title, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_GREY_700, text_align=ft.TextAlign.CENTER)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=220,
            height=200,
            bgcolor=color_hex,
            border_radius=30,
            on_click=lambda _: asyncio.create_task(self.start_learning_with_method(method_key)),
            ink=True,
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK_12, offset=ft.Offset(0, 5))
        )

    async def start_learning_with_method(self, method):
        self.current_input_method = method
        self.voice_attempts = 0
        if method == "voice":
            self.is_voice_mode_active = True
            await self.voice_learning_loop()
        else:
            await self.show_learning_screen()

    async def voice_learning_loop(self):
        """非同期かつ直列な音声学習ループ (単語モード)"""
        self.log("=== 音声モードループ（非同期・単語対応）を開始 ===")
        # UIの骨組み作成
        self.page.clean()
        self.feedback_emoji = ft.Text("🧐", size=80)
        self.current_char_text = ft.Text("", size=100, weight=ft.FontWeight.BOLD, color="#333333")
        self.voice_status = ft.Text("じゅんび中...", size=20, color=ft.Colors.BLUE_700, weight=ft.FontWeight.BOLD)
        
        # 認識されたテキストを表示するエリア
        self.recognized_text_display = ft.Text("", size=24, color=ft.Colors.ORANGE_700, weight=ft.FontWeight.W_500)
        
        # 使用中のマイク名を表示
        self.mic_info_text = ft.Text(f"🎤 マイク: {self.voice_manager.current_mic_name}", size=12, color=ft.Colors.GREY_500)
        
        char_display = ft.Container(content=self.current_char_text, bgcolor=ft.Colors.WHITE, width=400, height=250, border_radius=30, alignment=ft.Alignment.CENTER)
        self.page.add(ft.Column([ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: asyncio.create_task(self.stop_voice_mode())), ft.Text(f"{self.current_module}をまなぼう！", size=24, weight=ft.FontWeight.BOLD)]),
                                ft.Row([self.feedback_emoji], alignment=ft.MainAxisAlignment.CENTER), char_display, ft.Container(height=30),
                                ft.Row([ft.Text("いまの声: ", size=16), self.recognized_text_display], alignment=ft.MainAxisAlignment.CENTER),
                                ft.Row([self.voice_status], alignment=ft.MainAxisAlignment.CENTER),
                                ft.Row([self.mic_info_text], alignment=ft.MainAxisAlignment.CENTER)], 
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True, scroll=ft.ScrollMode.AUTO))
        self.page.update()

        while self.is_voice_mode_active:
            # 単語モードで問題取得
            char, correct_answer, choices = self.engine.get_question(is_word_mode=True)
            self.voice_attempts = 0
            
            # 正解の正規化（ひらがな化）
            target_hira = "".join([item['hira'] for item in self.kks.convert(char)])
            
            while self.voice_attempts < 2:
                if not self.is_voice_mode_active: return
                
                # 問題の描画
                self.current_char_text.value = char
                self.feedback_emoji.value = "🧐"
                self.feedback_emoji.color = ft.Colors.BLACK
                self.voice_status.value = "きいてるよ... 🗣️ (単語をいってね)"
                self.recognized_text_display.value = "" 
                self.page.update()

                # 音声入力を受け付けた際の音を鳴らす
                await self.play_sound("ninshiki")
                
                # 音声認識 (候補リストを受け取る)
                lang = "ja-JP" if "カナ" in self.current_module or "ひら" in self.current_module else "en-US"
                results_list = await asyncio.to_thread(self.voice_manager.listen, language=lang)
                
                if not self.is_voice_mode_active: return

                # 解析開始
                self.voice_status.value = "かんがえ中... 🤔"
                
                if results_list and len(results_list) > 0:
                    first_guess = results_list[0]
                    self.recognized_text_display.value = f"「{first_guess}」"
                    print(f"[VOICE] ききとった言葉: 【 {first_guess} 】")
                else:
                    self.recognized_text_display.value = "（聞き取れませんでした）"
                
                self.page.update()
                
                is_correct = False
                matched_result = "UNKNOWN"
                
                for raw_result in results_list:
                    # 入力結果の正規化
                    converted = self.kks.convert(raw_result)
                    result_hira = "".join([item['hira'] for item in converted])
                    clean_result = result_hira.strip().replace(" ", "").replace("　", "").replace("。", "").replace("、", "").replace("ー", "").replace("っ", "")
                    
                    self.log(f"=== 単語照合: 正解='{target_hira}' vs 入力='{clean_result}' (元: {raw_result}) ===")
                    
                    if "カナ" in self.current_module or "ひら" in self.current_module:
                        # 日本語モジュール: 全文字が一致するかチェック
                        if clean_result == target_hira:
                            is_correct = True
                            matched_result = clean_result
                            break
                    else:
                        # アルファベット: 全文字が一致するかチェック
                        if clean_result.lower() == correct_answer.lower():
                            is_correct = True
                            matched_result = clean_result
                            break
                    
                    if matched_result == "UNKNOWN":
                        matched_result = clean_result

                # 結果の反映
                if is_correct:
                    await self.play_sound("seikai")
                    self.feedback_emoji.value = "🎯"
                    self.feedback_emoji.color = ft.Colors.GREEN_400
                    await self.show_sync_snackbar_async("せいかい！ ✨", ft.Colors.GREEN_400)
                    self.voice_status.value = "せいかい！ 🎉"
                else:
                    await self.play_sound("hazure")
                    self.feedback_emoji.value = "❌"
                    self.feedback_emoji.color = ft.Colors.RED_400
                    if self.voice_attempts == 0:
                        text = f"おしい！ '{matched_result}' かな？ もういちど！"
                        await self.show_sync_snackbar_async(text, ft.Colors.ORANGE_400)
                        self.voice_status.value = "もういちど！ 💪"
                    else:
                        text = f"正解は '{char}' でした。"
                        await self.show_sync_snackbar_async(text, ft.Colors.RED_400)
                        self.voice_status.value = "つぎにいこう！ 🔜"
                
                self.page.update()
                self.log_result(char, matched_result, is_correct, "voice")
                if is_correct:
                    cursor = self.db_conn.cursor()
                    cursor.execute("UPDATE users SET stars = stars + 1 WHERE id = ?", (self.current_user_id,))
                    self.db_conn.commit()
                    await asyncio.sleep(2.0)
                    break
                
                self.voice_attempts += 1
                await asyncio.sleep(2.0)
            
            if is_correct or self.voice_attempts >= 2:
                continue 

    async def stop_voice_mode(self):
        self.log("音声モードを終了します。")
        self.is_voice_mode_active = False
        await self.show_input_method_selection()

    async def show_sync_snackbar_async(self, text, color):
        for ctrl in self.page.overlay[:]:
            if isinstance(ctrl, ft.SnackBar):
                try: self.page.overlay.remove(ctrl)
                except: pass
        sb = ft.SnackBar(content=ft.Text(text, size=20, weight=ft.FontWeight.BOLD), bgcolor=color, duration=1500)
        self.page.overlay.append(sb)
        sb.open = True
        self.page.update()

    async def show_learning_screen(self, char=None, choices=None):
        self.page.clean()
        if not char:
            # 音声モード(voice)および「音をきく（単語）」モードは単語モードにする
            is_word = (self.current_input_method in ["voice", "listening_word"])
            char, self.correct_answer, choices = self.engine.get_question(is_word_mode=is_word)
        self.current_char = char
        self.feedback_emoji = ft.Text("🧐", size=80)
        
        # 音をきくモード（1文字/単語）なら「？」にする
        display_char = "？" if self.current_input_method in ["listening", "listening_word"] else char
        
        char_display = ft.Container(content=ft.Text(display_char, size=150, weight=ft.FontWeight.BOLD, color="#333333"),
                                    bgcolor=ft.Colors.WHITE, width=400, height=300, border_radius=30, alignment=ft.Alignment.CENTER)
        
        input_controls = []
        if self.current_input_method in ["listening", "listening_word"]:
            # 正解以外の文字からランダムに2つ選ぶ
            if self.current_input_method == "listening":
                all_options = list(self.engine.chars.keys())
            else:
                all_options = self.engine.words
                
            other_options = [c for c in all_options if c != char]
            choices_3 = random.sample(other_options, min(len(other_options), 2))
            choices_3.append(char)
            random.shuffle(choices_3)
            
            choices_row = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=20)
            for choice in choices_3:
                # 文字サイズを単語の長さに合わせて調整
                font_size = 50 if len(choice) <= 1 else 30
                choices_row.controls.append(
                    ft.Button(
                        content=ft.Text(choice, size=font_size, weight=ft.FontWeight.BOLD),
                        on_click=lambda e, c=choice: asyncio.create_task(self.handle_answer_async(char, c, c == char, self.current_input_method)),
                        width=200 if len(choice) > 1 else 150, 
                        height=120,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=20),
                            bgcolor=ft.Colors.PURPLE_100 if self.current_input_method == "listening" else ft.Colors.INDIGO_100,
                            color=ft.Colors.BLACK87
                        )
                    )
                )
            replay_btn = ft.IconButton(icon=ft.Icons.REPLAY, icon_size=40, on_click=lambda _: asyncio.create_task(self.speak_text(char)))
            input_controls.append(ft.Column([choices_row, ft.Row([replay_btn], alignment=ft.MainAxisAlignment.CENTER)], horizontal_alignment=ft.CrossAxisAlignment.CENTER))
        elif self.current_input_method == "click":
            row = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=20)
            for c in choices:
                row.controls.append(ft.Button(content=ft.Text(c, size=30), on_click=lambda e, sel=c: asyncio.create_task(self.handle_answer_async(char, sel, sel==self.correct_answer, "click")), width=100))
            input_controls.append(row)
        elif self.current_input_method == "keyboard":
            answer_input = ft.TextField(label="キーボードでいれてみてね", width=300, on_submit=lambda e: asyncio.create_task(self.handle_answer_async(char, e.control.value, e.control.value.lower() == self.correct_answer, "keyboard")), autofocus=True)
            input_controls.append(ft.Row([answer_input], alignment=ft.MainAxisAlignment.CENTER))

        self.page.add(ft.Column([ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: asyncio.create_task(self.show_input_method_selection())),
                                        ft.Text(f"{self.current_module}をまなぼう！", size=24, weight=ft.FontWeight.BOLD)]),
                                ft.Row([self.feedback_emoji], alignment=ft.MainAxisAlignment.CENTER), char_display, ft.Container(height=30), *input_controls],
                               horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True, scroll=ft.ScrollMode.AUTO))
        self.page.update()
        if self.current_input_method in ["listening", "listening_word"]: asyncio.create_task(self.speak_text(char))

    async def handle_answer_async(self, char, answer, is_correct, method):
        self.log_result(char, answer, is_correct, method)
        if is_correct:
            await self.play_sound("seikai")
            cursor = self.db_conn.cursor()
            cursor.execute("UPDATE users SET stars = stars + 1 WHERE id = ?", (self.current_user_id,))
            self.db_conn.commit()
            self.feedback_emoji.value, self.feedback_emoji.color = "🎯", ft.Colors.GREEN_400
            await self.show_sync_snackbar_async("せいかい！ ✨", ft.Colors.GREEN_400)
        else:
            await self.play_sound("hazure")
            self.feedback_emoji.value, self.feedback_emoji.color = "❌", ft.Colors.RED_400
            await self.show_sync_snackbar_async(f"おしい！ '{answer}' だったね。", ft.Colors.RED_400)
        self.page.update()
        await asyncio.sleep(2.0)
        await self.show_learning_screen()

    def log_result(self, question, answer, is_correct, method):
        cursor = self.db_conn.cursor()
        cursor.execute('INSERT INTO logs (user_id, module, question, answer, is_correct, input_method) VALUES (?, ?, ?, ?, ?, ?)',
                       (self.current_user_id, self.current_module, question, answer, is_correct, method))
        self.db_conn.commit()

    async def show_parental_dashboard(self):
        self.log("保護者ダッシュボードを表示します。")
        self.page.clean()
        
        async def reset_user_data(e):
            async def confirm_reset(e):
                cursor = self.db_conn.cursor()
                cursor.execute("DELETE FROM logs WHERE user_id = ?", (self.current_user_id,))
                cursor.execute("UPDATE users SET stars = 0 WHERE id = ?", (self.current_user_id,))
                self.db_conn.commit()
                confirm_dialog.open = False
                self.page.update()
                await self.show_parental_dashboard()

            confirm_dialog = ft.AlertDialog(
                title=ft.Text("データのりせっと"), content=ft.Text("記録をぜんぶ消してもいいですか？"),
                actions=[ft.TextButton("キャンセル", on_click=lambda _: [setattr(confirm_dialog, "open", False), self.page.update()]),
                         ft.Button("消去する", on_click=confirm_reset, bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE)]
            )
            self.page.overlay.append(confirm_dialog)
            confirm_dialog.open = True
            self.page.update()

        async def edit_user_name(e):
            name_input = ft.TextField(label="あたらしいおなまえ", value=self.current_user_name, width=300, border_radius=15)
            async def save_new_name(e):
                if name_input.value:
                    cursor = self.db_conn.cursor()
                    cursor.execute("UPDATE users SET name = ? WHERE id = ?", (name_input.value, self.current_user_id))
                    self.db_conn.commit()
                    self.current_user_name = name_input.value
                    edit_dialog.open = False
                    self.page.update()
                    await self.show_parental_dashboard()
            edit_dialog = ft.AlertDialog(
                title=ft.Text("なまえをかえる"), content=name_input,
                actions=[ft.TextButton("キャンセル", on_click=lambda _: [setattr(edit_dialog, "open", False), self.page.update()]),
                         ft.Button("保存", on_click=save_new_name, bgcolor=ft.Colors.ORANGE_400, color=ft.Colors.WHITE)]
            )
            self.page.overlay.append(edit_dialog)
            edit_dialog.open = True
            self.page.update()

        async def delete_user(e):
            async def confirm_delete(e):
                cursor = self.db_conn.cursor()
                cursor.execute("DELETE FROM logs WHERE user_id = ?", (self.current_user_id,))
                cursor.execute("DELETE FROM rewards WHERE user_id = ?", (self.current_user_id,))
                cursor.execute("DELETE FROM users WHERE id = ?", (self.current_user_id,))
                self.db_conn.commit()
                delete_dialog.open = False
                self.page.update()
                await self.show_profile_selection()

            delete_dialog = ft.AlertDialog(
                title=ft.Text("ユーザーのさくじょ"), content=ft.Text("プロフィールをぜんぶ消してもいいですか？"),
                actions=[ft.TextButton("キャンセル", on_click=lambda _: [setattr(delete_dialog, "open", False), self.page.update()]),
                         ft.Button("削除する", on_click=confirm_delete, bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE)]
            )
            self.page.overlay.append(delete_dialog)
            delete_dialog.open = True
            self.page.update()

        cursor = self.db_conn.cursor()
        # 各モジュールごとの基本統計
        cursor.execute("SELECT module, COUNT(*), SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) FROM logs WHERE user_id = ? GROUP BY module", (self.current_user_id,))
        stats = cursor.fetchall()
        
        # モジュールごとに文字正答率データを取得する関数
        def get_char_stats(module_name):
            cursor.execute("""
                SELECT question, COUNT(*) as total, SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) as correct
                FROM logs 
                WHERE user_id = ? AND module = ?
                GROUP BY question 
                ORDER BY (CAST(SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)) ASC, total DESC
                LIMIT 10
            """, (self.current_user_id, module_name))
            return cursor.fetchall()

        hira_stats = get_char_stats("ひらがな")
        kana_stats = get_char_stats("カタカナ")
        alpha_stats = get_char_stats("アルファベッド")

        cursor.execute("SELECT name, stars FROM users WHERE id = ?", (self.current_user_id,))
        user_info = cursor.fetchone()
        
        # モジュール別統計のリスト（上部に表示）
        summary_list = ft.Column(spacing=10)
        for module, total, correct in stats:
            accuracy = (correct / total * 100) if total > 0 else 0
            summary_list.controls.append(ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon(ft.Icons.AUTO_GRAPH, color=ft.Colors.BLUE_400),
                    title=ft.Text(f"{module}", weight=ft.FontWeight.BOLD), 
                    subtitle=ft.Text(f"ぜんたいの正答率: {accuracy:.1f}% ({correct}/{total})"),
                ),
                bgcolor=ft.Colors.BLUE_50, border_radius=15, padding=5))

        # 各モジュールのランキングリストを作成する関数
        def create_ranking_view(data, empty_text):
            if not data:
                return ft.Container(content=ft.Text(empty_text, size=16), padding=20)
            
            view = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO)
            for char, total, correct in data:
                accuracy = (correct / total * 100)
                view.controls.append(
                    ft.Container(
                        content=ft.ListTile(
                            leading=ft.Text(char, size=24, weight=ft.FontWeight.BOLD),
                            title=ft.Text(f"せいとうりつ: {accuracy:.1f}%"),
                            subtitle=ft.Text(f"せいかい: {correct} / もんだい: {total}"),
                            trailing=ft.Icon(ft.Icons.WARNING, color=ft.Colors.RED_400 if accuracy < 50 else ft.Colors.ORANGE_400)
                        ),
                        bgcolor=ft.Colors.RED_50 if accuracy < 50 else ft.Colors.ORANGE_50,
                        border_radius=10,
                        padding=5
                    )
                )
            return view

        # 各カテゴリのランキングを表示するためのコンテナ
        rankings_container = ft.Container(content=create_ranking_view(hira_stats, "ひらがなのデータがまだないよ"), expand=True)

        def switch_category(e, data, empty_text):
            rankings_container.content = create_ranking_view(data, empty_text)
            self.page.update()

        stats_view = ft.Column([
            ft.Text("📊 おべんきょうのきろく", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
            summary_list,
            ft.Container(height=20),
            ft.Text("⚠️ にがてなランキング (ワースト10)", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700),
            ft.Row([
                ft.Button("ひらがな", on_click=lambda e: switch_category(e, hira_stats, "ひらがなのデータがまだないよ")),
                ft.Button("カタカナ", on_click=lambda e: switch_category(e, kana_stats, "カタカナのデータがまだないよ")),
                ft.Button("アルファベット", on_click=lambda e: switch_category(e, alpha_stats, "アルファベットのデータがまだないよ")),
            ], alignment=ft.MainAxisAlignment.CENTER),
            rankings_container
        ], expand=True, spacing=10)
        
        mic_names = self.voice_manager.list_microphones()
        mic_options = [ft.dropdown.Option(key=str(i), text=name) for i, name in enumerate(mic_names)]
        
        async def on_mic_change(e):
            idx = int(e.control.value)
            name = mic_names[idx]
            self.voice_manager.set_device(idx, name)
            self.log(f"マイクを '{name}' に設定しました。")

        mic_dropdown = ft.Dropdown(
            label="マイクをえらぶ", 
            options=mic_options, 
            value=str(self.voice_manager.device_index) if self.voice_manager.device_index is not None else None,
            on_select=on_mic_change, 
            width=400
        )

        user_detail = ft.Column([
            ft.Text("👤 ユーザーじょうほう", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
            ft.Container(
                content=ft.ListTile(
                    title=ft.Text(user_info[0], weight=ft.FontWeight.BOLD, size=20), 
                    subtitle=ft.Text(f"スター: {user_info[1]} ⭐", size=16)
                ), 
                bgcolor=ft.Colors.GREEN_50, 
                border_radius=15,
                padding=10
            ),
            ft.Container(height=10), 
            mic_dropdown, 
            ft.Container(height=20),
            ft.Row([
                ft.Button("なまえをかえる", on_click=edit_user_name), 
                ft.Button("きろくをリセット", on_click=reset_user_data)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            ft.Button("ユーザーをさくじょする", on_click=delete_user, style=ft.ButtonStyle(color=ft.Colors.RED_600))
        ], expand=True, spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        self.page.add(
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: asyncio.create_task(self.show_main_dashboard())), 
                        ft.Text("ほごしゃメニュー 🛡️", size=24, weight=ft.FontWeight.BOLD)
                    ], alignment=ft.MainAxisAlignment.START),
                    ft.Row([
                        ft.Container(
                            content=stats_view, 
                            expand=True, 
                            bgcolor=ft.Colors.WHITE, 
                            border_radius=20,
                            padding=20,
                            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK_12)
                        ),
                        ft.Container(
                            content=user_detail, 
                            expand=True, 
                            bgcolor=ft.Colors.WHITE, 
                            border_radius=20,
                            padding=20,
                            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK_12)
                        )
                    ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START)
                ], expand=True, spacing=20),
                padding=20,
                expand=True
            )
        )
        self.page.update()

async def main(page: ft.Page):
    SproutaApp(page)

if __name__ == "__main__":
    ft.run(main)
