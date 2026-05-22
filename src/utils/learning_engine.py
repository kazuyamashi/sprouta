import random

class LearningEngine:
    HIRAGANA = {
        'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
        'か': 'ka', 'き': 'ki', 'く': 'ku', 'け': 'ke', 'こ': 'ko',
        'さ': 'sa', 'し': 'shi', 'す': 'su', 'せ': 'se', 'そ': 'so',
        'た': 'ta', 'ち': 'chi', 'つ': 'tsu', 'て': 'te', 'と': 'to',
        'な': 'na', 'に': 'ni', 'ぬ': 'nu', 'ね': 'ne', 'の': 'no',
        'は': 'ha', 'ひ': 'hi', 'ふ': 'fu', 'へ': 'he', 'ほ': 'ho',
        'ま': 'ma', 'み': 'mi', 'む': 'mu', 'め': 'me', 'も': 'mo',
        'や': 'ya', 'ゆ': 'yu', 'よ': 'yo',
        'ら': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
        'わ': 'wa', 'を': 'wo', 'ん': 'n'
    }
    
    KATAKANA = {
        'ア': 'a', 'イ': 'i', 'ウ': 'u', 'エ': 'e', 'オ': 'o',
        'カ': 'ka', 'キ': 'ki', 'ク': 'ku', 'ケ': 'ke', 'コ': 'ko',
        'サ': 'sa', 'シ': 'shi', 'ス': 'su', 'セ': 'se', 'ソ': 'so',
        'タ': 'ta', 'チ': 'chi', 'ツ': 'tsu', 'テ': 'te', 'ト': 'to',
        'ナ': 'na', 'ニ': 'ni', 'ヌ': 'nu', 'ネ': 'ne', 'の': 'no',
        'ハ': 'ha', 'ヒ': 'hi', 'フ': 'fu', 'ヘ': 'he', 'ホ': 'ho',
        'マ': 'ma', 'ミ': 'mi', 'ム': 'mu', 'メ': 'me', 'も': 'mo',
        'ヤ': 'ya', 'ユ': 'yu', 'ヨ': 'yo',
        'ラ': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
        'ワ': 'wa', 'ヲ': 'wo', 'ン': 'n'
    }
    
    ALPHABET = {
        'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e', 'F': 'f', 'G': 'g',
        'H': 'h', 'I': 'i', 'J': 'j', 'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n',
        'O': 'o', 'P': 'p', 'Q': 'q', 'R': 'r', 'S': 's', 'T': 't', 'U': 'u',
        'V': 'v', 'W': 'w', 'X': 'x', 'Y': 'y', 'Z': 'z'
    }

    # 音声モード用の単語リスト (2〜4文字)
    HIRAGANA_WORDS = [
        "いぬ", "ねこ", "さかな", "とけい", "くるま", "さくら", "みかん", "りんご", 
        "えんぴつ", "つくえ", "いちご", "おかし", "すいか", "きりん", "とり", "こども", "はさみ", "ふうせん",
        "あい", "うえ", "おとこ", "かさ", "きのこ", "くつ", "けむり", "こいぬ", "さる", "しろ", "せんせい", "そら",
        "たまご", "ちず", "つき", "てがみ", "とまと", "なつ", "にんじん", "ねずみ", "のり", "はな", "ひこうき",
        "ふね", "へび", "ほし", "まくら", "みず", "むし", "めがね", "もも", "やさい", "ゆき", "よる",
        "らいおん", "りす", "るす", "れいぞうこ", "ろうそく", "わに"
    ]
    
    KATAKANA_WORDS = [
        "カメラ", "テレビ", "ピアノ", "バナナ", "ノート", "コップ", "クラス", "トイレ",
        "シャツ", "パン", "スキー", "テニス", "ギター", "ドア", "ラジオ"
    ]
    
    ALPHABET_WORDS = [
        "APPLE", "DOG", "CAT", "FISH", "BOOK", "CAR", "MILK", "SUN", 
        "MOON", "TREE", "CAKE", "BALL", "BIRD", "FIRE", "KING"
    ]

    def __init__(self, module_type):
        self.module_type = module_type
        if module_type == "ひらがな":
            self.chars = self.HIRAGANA
            self.words = self.HIRAGANA_WORDS
        elif module_type == "カタカナ":
            self.chars = self.KATAKANA
            self.words = self.KATAKANA_WORDS
        else:
            self.chars = self.ALPHABET
            self.words = self.ALPHABET_WORDS

    def get_question(self, is_word_mode=False):
        if is_word_mode:
            # 単語モード
            target = random.choice(self.words)
            # 選択肢は単語リストからランダムに
            choices = random.sample([w for w in self.words if w != target], 3)
            choices.append(target)
            random.shuffle(choices)
            # 正解の読み（小文字化）
            correct_answer = target.lower()
            return target, correct_answer, choices
        else:
            # 1文字モード
            char = random.choice(list(self.chars.keys()))
            correct_answer = self.chars[char]
            all_answers = list(self.chars.values())
            choices = random.sample([a for a in all_answers if a != correct_answer], 3)
            choices.append(correct_answer)
            random.shuffle(choices)
            return char, correct_answer, choices
