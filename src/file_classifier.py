"""PDF 分類（現状はキーワード判定。将来 AI 分類へ差し替える拡張ポイント）

新しい分類器は Classifier を継承して classify() を実装し、
main.py の build_classifier() で差し替える。
"""

from abc import ABC, abstractmethod

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "DX": ["DX", "デジタルトランスフォーメーション", "デジタル化"],
    "AI": ["AI", "人工知能", "機械学習", "生成AI", "深層学習"],
    "量子": ["量子"],
    "半導体": ["半導体"],
    "医療": ["医療", "臨床", "医薬", "ヘルスケア"],
    "創薬": ["創薬", "医薬品"],
    "GX": ["GX", "グリーン", "脱炭素", "カーボンニュートラル", "水素"],
    "宇宙": ["宇宙", "衛星"],
    "農業": ["農業", "農林", "食料"],
    "産学連携": ["産学連携", "産学官", "共同研究"],
}


class Classifier(ABC):
    @abstractmethod
    def classify(self, text: str) -> list[str]:
        """テキスト（リンク文字列・ファイル名・将来は PDF 本文）から分類タグを返す。"""


class KeywordClassifier(Classifier):
    def __init__(self, keywords: dict[str, list[str]] | None = None):
        self.keywords = keywords or CATEGORY_KEYWORDS

    def classify(self, text: str) -> list[str]:
        upper = text.upper()
        return [cat for cat, words in self.keywords.items()
                if any(w.upper() in upper for w in words)]
