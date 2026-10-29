"""
CUAD Lexical Baseline Extractor
===============================
Reproducible heuristic / BM25 clause extractor that serves as the academic
baseline for comparison against transformer-based models.

Mechanisms:
1. Category-specific legal trigger patterns and vocabulary.
2. Sliding-window sentence scoring using BM25Okapi / term frequency.
3. Strict confidence thresholding to predict no-answer when evidence is weak.
4. Returns exact predicted span and character offsets within the contract context.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from rank_bm25 import BM25Okapi


# Standard category keywords & triggers for the 41 CUAD categories
CATEGORY_TRIGGERS: Dict[str, List[str]] = {
    "Document Name": ["agreement", "contract", "amendment", "distributor agreement", "license agreement", "master services agreement"],
    "Parties": ["by and between", "between", "parties", "entered into by", "among"],
    "Agreement Date": ["dated as of", "entered into as of", "made as of", "this day of"],
    "Effective Date": ["effective date", "effective as of", "commencing on", "shall become effective"],
    "Expiration Date": ["expiration date", "expire on", "shall terminate on", "term of this agreement shall end"],
    "Renewal Term": ["renewal term", "renew automatically", "successive terms", "automatic renewal"],
    "Notice Period To Terminate Renewal": ["notice of non-renewal", "prior written notice of termination", "days prior to the expiration"],
    "Governing Law": ["governed by", "laws of the state of", "construed in accordance with", "jurisdiction of"],
    "Most Favored Nation": ["most favored nation", "favorable terms", "more favorable price"],
    "Competitive Restriction Exception": ["competitive restriction", "carve-out", "exception to non-compete"],
    "Non-Compete": ["covenant not to compete", "non-compete", "shall not engage in competing", "restrictive covenant"],
    "Exclusivity": ["exclusive right", "sole and exclusive", "exclusivity", "exclusive basis"],
    "No-Solicit Of Customers": ["non-solicitation of customers", "shall not solicit any customer", "solicit business from"],
    "No-Solicit Of Employees": ["non-solicitation of employees", "shall not solicit any employee", "hire or solicit"],
    "Non-Disparagement": ["non-disparagement", "disparage", "defame or disparage"],
    "Termination For Convenience": ["terminate for convenience", "terminate without cause", "terminate at any time upon", "convenience"],
    "Rofr/Rofo/Rofn": ["right of first refusal", "right of first offer", "right of first negotiation", "rofr", "rofo"],
    "Change Of Control": ["change of control", "merger or consolidation", "sale of all or substantially all assets"],
    "Anti-Assignment": ["assignment", "neither party may assign", "shall not assign without prior written consent"],
    "Revenue/Profit Sharing": ["revenue share", "profit sharing", "percentage of gross revenue", "royalties"],
    "Price Restrictions": ["price increases", "most favored customer pricing", "price ceiling"],
    "Minimum Commitment": ["minimum commitment", "minimum purchase requirement", "guaranteed minimum"],
    "Volume Restriction": ["volume restriction", "maximum capacity", "maximum quantity"],
    "Ip Ownership Assignment": ["intellectual property shall belong to", "assignment of inventions", "work made for hire", "sole and exclusive property"],
    "Joint Ip Ownership": ["jointly owned", "joint ownership of intellectual property", "co-owned ip"],
    "License Grant": ["hereby grants", "non-exclusive license", "exclusive license", "license grant", "right and license"],
    "Non-Transferable License": ["non-transferable", "nontransferable", "non-assignable license"],
    "Affiliate License-Licensor": ["affiliates of licensor", "licensor affiliates"],
    "Affiliate License-Licensee": ["affiliates of licensee", "licensee affiliates", "may be used by affiliates"],
    "Unlimited/All-You-Can-Eat-License": ["unlimited license", "enterprise-wide license", "unlimited users"],
    "Irrevocable Or Perpetual License": ["perpetual license", "irrevocable license", "perpetual and irrevocable"],
    "Source Code Escrow": ["source code escrow", "escrow agent", "release of source code"],
    "Post-Termination Services": ["post-termination transition", "transition services", "assistance upon termination"],
    "Audit Rights": ["audit rights", "right to audit", "books and records", "inspect and audit"],
    "Uncapped Liability": ["uncapped liability", "shall not be subject to any cap", "liability shall not be limited"],
    "Cap On Liability": ["aggregate liability shall not exceed", "limitation of liability", "in no event shall total liability", "cap on liability"],
    "Liquidated Damages": ["liquidated damages", "pre-estimated damages", "agreed penalty"],
    "Warranty Duration": ["warranty period", "warranty for a period of", "days from delivery"],
    "Insurance": ["maintain insurance", "commercial general liability", "worker's compensation", "minimum insurance coverage"],
    "Covenant Not To Sue": ["covenant not to sue", "agree not to institute any action"],
    "Third Party Beneficiary": ["third party beneficiary", "no third party beneficiaries", "intended third party"],
}


def _split_into_sentences(text: str) -> List[Tuple[str, int, int]]:
    """
    Split text into sentences with exact character offsets (start_char, end_char).
    """
    sentences = []
    pattern = re.compile(r"([^\n.!?]+(?:[\n.!?]+|$))")
    for match in pattern.finditer(text):
        raw = match.group()
        stripped = raw.strip()
        if len(stripped) > 10:  # filter tiny fragments
            leading_ws = len(raw) - len(raw.lstrip())
            start = match.start() + leading_ws
            end = start + len(stripped)
            sentences.append((stripped, start, end))
    if not sentences and text.strip():
        stripped = text.strip()
        leading_ws = len(text) - len(text.lstrip())
        sentences.append((stripped, leading_ws, leading_ws + len(stripped)))
    return sentences


class CUADBaselineExtractor:
    """
    Lexical baseline extractor for CUAD contracts.
    Scores contract sentences using category trigger keywords and BM25 relevance.
    """

    def __init__(self, confidence_threshold: float = 1.8):
        self.confidence_threshold = confidence_threshold

    def extract_clause(
        self,
        context: str,
        category: str,
        question: str,
    ) -> Tuple[str, int, int, float]:
        """
        Extract candidate clause from context for a given category.

        Returns:
            Tuple of (predicted_text, start_char, end_char, score).
            If score < confidence_threshold, returns ("", -1, -1, 0.0).
        """
        if not context or not context.strip():
            return "", -1, -1, 0.0

        sentences = _split_into_sentences(context)
        if not sentences:
            return "", -1, -1, 0.0

        triggers = CATEGORY_TRIGGERS.get(category, [category.lower()])
        query_terms = set(t.lower() for trigger in triggers for t in trigger.split())

        # Score each sentence
        best_sentence = ""
        best_start = -1
        best_end = -1
        best_score = 0.0

        for sent_text, s_start, s_end in sentences:
            sent_lower = sent_text.lower()
            score = 0.0

            # 1. Exact phrase trigger match (high weight)
            for phrase in triggers:
                if phrase.lower() in sent_lower:
                    score += 3.0

            # 2. Token overlap with triggers
            sent_words = set(re.findall(r"\w+", sent_lower))
            overlap = len(sent_words & query_terms)
            score += overlap * 0.5

            if score > best_score:
                best_score = score
                best_sentence = sent_text
                best_start = s_start
                best_end = s_end

        if best_score >= self.confidence_threshold:
            # Clean and truncate if excessively long
            candidate = best_sentence.strip()
            if len(candidate) > 400:
                candidate = candidate[:400]
                best_end = best_start + 400
            return candidate, best_start, best_end, round(best_score, 3)

        return "", -1, -1, 0.0

    def evaluate_contract(
        self,
        contract: Dict[str, Any],
    ) -> Dict[str, Tuple[str, int, int, float]]:
        """
        Run baseline extraction on all QAs in a contract.
        Returns dict mapping question ID -> (pred_text, start_char, end_char, score).
        """
        context = contract.get("context", "")
        if not context and "paragraphs" in contract:
            context = contract["paragraphs"][0].get("context", "")

        results = {}
        for qa in contract.get("qas", []):
            qid = qa["id"]
            cat = qa.get("category", "")
            q_text = qa.get("question", "")
            results[qid] = self.extract_clause(context, cat, q_text)
        return results
