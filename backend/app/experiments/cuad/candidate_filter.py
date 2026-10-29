"""
CUAD Candidate Window Prefilter
===============================
Reduces sliding-window inference time on long legal contracts by filtering
unlikely windows before running heavy transformer self-attention.

Mechanism:
1. Scores each window using term overlap with category prompt and trigger phrases.
2. Ranks windows and selects top-K candidates (e.g. K=3 to 5).
3. Always preserves exact token offsets and window indices.
4. Allows comparing filtered vs unfiltered inference to measure speedup vs recall tradeoff.
"""

import re
from typing import List, Dict, Any, Tuple
from .baseline_extractor import CATEGORY_TRIGGERS


class CandidateWindowPrefilter:
    """
    Selects top-K candidate windows for a given category question.
    """

    def __init__(self, top_k_windows: int = 4):
        self.top_k_windows = top_k_windows

    def filter_windows(
        self,
        question: str,
        category: str,
        window_texts: List[str],
    ) -> List[int]:
        """
        Rank windows by relevance to category and question.
        Returns sorted list of window indices (up to top_k_windows).
        """
        num_windows = len(window_texts)
        if num_windows <= self.top_k_windows:
            return list(range(num_windows))

        triggers = CATEGORY_TRIGGERS.get(category, [category.lower()])
        q_terms = set(re.findall(r"\w+", question.lower()))
        trigger_terms = set(t.lower() for trig in triggers for t in trig.split())
        combined_terms = q_terms | trigger_terms

        scores = []
        for idx, w_text in enumerate(window_texts):
            w_lower = w_text.lower()
            score = 0.0

            # 1. Exact phrase trigger match (+3.0)
            for phrase in triggers:
                if phrase.lower() in w_lower:
                    score += 3.0

            # 2. Token overlap (+0.2 per distinct match)
            w_tokens = set(re.findall(r"\w+", w_lower))
            overlap = len(w_tokens & combined_terms)
            score += overlap * 0.2

            scores.append((idx, score))

        # Sort descending by score
        scores.sort(key=lambda x: x[1], reverse=True)

        selected_indices = [idx for idx, _ in scores[:self.top_k_windows]]
        # Return in chronological order to maintain contract sequence
        return sorted(selected_indices)
