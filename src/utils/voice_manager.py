import speech_recognition as sr

class VoiceManager:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # 感度の調整
        self.recognizer.energy_threshold = 100
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.1
        self.recognizer.dynamic_energy_ratio = 1.2
        self.recognizer.pause_threshold = 1.2      # 0.5 -> 1.2 (言葉の途中で切れないよう長めに待機)
        self.recognizer.non_speaking_duration = 0.5 # 0.2 -> 0.5 (発話前の沈黙許容時間を延長)
        self.device_index = None
        self.current_mic_name = "デフォルトマイク"
        self.microphone = sr.Microphone()

    @staticmethod
    def list_microphones():
        return sr.Microphone.list_microphone_names()

    def set_device(self, index, name=None):
        """マイクのデバイスインデックスと名前を設定します。"""
        self.device_index = index
        if name:
            self.current_mic_name = name
        self.microphone = sr.Microphone(device_index=self.device_index)

    def listen(self, language="ja-JP"):
        with self.microphone as source:
            print(f"DEBUG: マイク入力待ち... (言語: {language}, マイク: {self.current_mic_name})")
            # ノイズ学習を安定させるために少し時間を取る
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                # 録音上限を8秒に延長
                audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=8)

                print("DEBUG: 音声を解析中...")
                
                # show_all=True にして、Googleが返すすべての候補を取得
                response = self.recognizer.recognize_google(audio, language=language, show_all=True)
                
                if not response or 'alternative' not in response:
                    return []
                
                # 候補リストを小文字化して返す
                return [alt['transcript'].lower() for alt in response['alternative']]
                
            except sr.UnknownValueError:
                return ["UNKNOWN"]
            except Exception as e:
                print(f"ERROR in VoiceManager: {e}")
                return [f"ERROR: {str(e)}"]
