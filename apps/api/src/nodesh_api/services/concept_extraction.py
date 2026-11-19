"""Deterministic keyword and repeated-phrase extraction with TF-IDF scoring."""

from collections import Counter
from dataclasses import dataclass
import math
import re

WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_'-]*")
CLAUSE_SPLIT_PATTERN = re.compile(r"[\n\r.,;:?!|/•\(\)\[\]\"'«»—–]+|\s+[-*]\s+")

KNOWN_ACRONYMS = {
    "ai", "ml", "dl", "nlp", "ui", "ux", "ci", "cd", "qa", "os", "ip", "db",
    "vr", "ar", "rl", "nn", "cv", "llm", "api", "sql", "hr", "tfidf", "bert",
    "ner", "iot", "gpu", "cpu", "ram", "gui", "cli", "svm", "knn", "rnn", "cnn",
    "lstm", "gru", "gan", "rag",
}

STOP_WORDS = {
    "a", "about", "after", "all", "also", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "being", "between", "but", "by", "can", "could", "did",
    "do", "does", "each", "for", "from", "had", "has", "have", "he", "her", "here",
    "hers", "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "just",
    "may", "more", "most", "my", "no", "not", "of", "on", "one", "only", "or", "our",
    "out", "over", "she", "so", "some", "such", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "up", "use", "used", "using", "very", "was", "we", "were", "what", "when", "which",
    "who", "will", "with", "would", "you", "your",
    # Extended stop words
    "however", "therefore", "thus", "often", "still", "rather", "already", "either",
    "neither", "whether", "another", "every", "both", "many", "much", "own", "other",
    "same", "new", "first", "last", "long", "great", "little", "right", "well", "even",
    "back", "should", "need", "must", "might", "get", "got", "make", "made", "take",
    "give", "come", "want", "seem", "keep", "let", "say", "said", "tell", "thing",
    "way", "day", "time", "year", "work", "connect", "connects", "support", "supports",
    "map", "maps", "link", "links", "build", "built", "develop", "developed", "create", "created",
    # Relational verbs & predicates (should not form noun-phrase concepts)
    "utilize", "utilizes", "utilized", "utilizing",
    "power", "powers", "powered", "powering",
    "produce", "produces", "produced", "producing",
    "generate", "generates", "generated", "generating",
    "extract", "extracts", "extracted", "extracting",
    "improve", "improves", "improved", "improving",
    "optimize", "optimizes", "optimized", "optimizing",
    "enhance", "enhances", "enhanced", "enhancing",
    "accelerate", "accelerates", "accelerated", "accelerating",
    "include", "includes", "included", "including",
    "consist", "consists", "consisted", "consisting",
    "contain", "contains", "contained", "containing",
    "enable", "enables", "enabled", "enabling",
    "provide", "provides", "provided", "providing",
    "require", "requires", "required", "requiring",
    "lead", "leads", "led", "leading",
    "cause", "causes", "caused", "causing",
    "allow", "allows", "allowed", "allowing",
    "serve", "serves", "served", "serving",
    "integrate", "integrates", "integrated", "integrating",
    "deploy", "deploys", "deployed", "deploying",
    "execute", "executes", "executed", "executing",
    "implement", "implements", "implemented", "implementing",
    "evaluate", "evaluates", "evaluated", "evaluating",
    "benchmark", "benchmarks", "benchmarked", "benchmarking",
    "measure", "measures", "measured", "measuring",
    "compare", "compares", "compared", "comparing",
    "analyze", "analyzes", "analyzed", "analyzing",
    # Academic & publication metadata
    "issn", "isbn", "doi", "volume", "issue", "vol", "no", "pp", "page", "pages",
    "journal", "published", "conference", "proceedings", "publisher", "editor",
    "editorial", "review", "paper", "article", "author", "authors", "copyright",
    "rights", "reserved", "impact", "factor", "sjif", "ugc", "index", "indexed",
    "citation", "citations", "et", "al", "figure", "fig", "table", "tab", "section", "sec",
    # Web & protocol tokens
    "http", "https", "www", "com", "org", "net", "edu", "gov", "io", "html", "url", "link",
    "ijsrem", "ijrem",
    # Publication months
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "january", "february", "march", "april", "june", "july", "august", "september",
    "october", "november", "december",
    # Administrative & boilerplate resume words
    "cgpa", "semester", "curriculum", "vitae", "resume", "declaration", "hobbies",
    "dob", "sinhgad", "secondary",
}


@dataclass(frozen=True)
class ConceptCandidate:
    name: str
    normalized_name: str
    occurrence_count: int
    score: float
    tfidf_score: float = 0.0


def normalize_word(word: str) -> str:
    normalized = word.lower().strip("'-_")
    if normalized.endswith("s") and len(normalized) > 4 and normalized not in KNOWN_ACRONYMS:
        return normalized[:-1]
    return normalized


def is_meaningful(word: str) -> bool:
    if not word or word in STOP_WORDS or word.isnumeric():
        return False
    if word in KNOWN_ACRONYMS:
        return True
    return len(word) >= 3


def unwrap_soft_newlines(text: str) -> str:
    """Unwrap soft newlines within paragraphs while keeping bullet points and paragraph breaks."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = re.split(r"\n\s*\n+", normalized)
    unwrapped_paras: list[str] = []
    for p in paragraphs:
        lines = [line.strip() for line in p.split("\n") if line.strip()]
        if any(re.match(r"^[-*•\d+.]\s+", line) for line in lines):
            unwrapped_paras.append("\n".join(lines))
        else:
            unwrapped_paras.append(" ".join(lines))
    return "\n\n".join(unwrapped_paras)


def extract_context_blocks(text: str) -> list[str]:
    """Break text into contextual chunks (paragraphs, bullet points, or sliding windows)."""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_blocks = [block.strip() for block in re.split(r"\n\s*\n+", cleaned) if block.strip()]
    if not raw_blocks:
        return [text] if text.strip() else []

    blocks: list[str] = []
    for block in raw_blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) > 1 and any(re.match(r"^[-*•\d+.]\s+", line) for line in lines):
            blocks.extend(lines)
        else:
            words = block.split()
            if len(words) > 80:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", block) if s.strip()]
                chunk: list[str] = []
                chunk_len = 0
                for s in sentences:
                    s_words = len(s.split())
                    if chunk_len + s_words > 50 and chunk:
                        blocks.append(" ".join(chunk))
                        chunk = [s]
                        chunk_len = s_words
                    else:
                        chunk.append(s)
                        chunk_len += s_words
                if chunk:
                    blocks.append(" ".join(chunk))
            else:
                blocks.append(block)
    return blocks


def compute_tf(count: int) -> float:
    return 1.0 + math.log(count) if count > 0 else 0.0


def compute_idf(doc_freq: int, total_docs: int) -> float:
    """Okapi BM25 smoothed IDF to properly penalize ubiquitous terms."""
    val = (total_docs - doc_freq + 0.5) / (doc_freq + 0.5)
    return math.log(max(val, 0.0) + 1.0) + 0.05


def extract_concepts(
    text: str,
    *,
    limit: int = 20,
    corpus_texts: list[str] | None = None,
    use_tfidf: bool = False,
) -> list[ConceptCandidate]:
    """Return the highest-signal keywords and repeated adjacent phrases.

    Optionally scores and ranks candidates using TF-IDF across document blocks
    and workspace corpus texts.
    """
    unwrapped = unwrap_soft_newlines(text)
    clauses = [c.strip() for c in CLAUSE_SPLIT_PATTERN.split(unwrapped) if c.strip()]

    word_counts: Counter[str] = Counter()
    phrase_counts: Counter[str] = Counter()
    trigram_counts: Counter[str] = Counter()

    for clause in clauses:
        raw_tokens = WORD_PATTERN.findall(clause)
        content_tokens = [
            normalize_word(w) if is_meaningful(normalize_word(w)) else None
            for w in raw_tokens
        ]

        for i, token in enumerate(content_tokens):
            if token is not None:
                word_counts[token] += 1
            if i + 1 < len(content_tokens) and token is not None and content_tokens[i + 1] is not None:
                phrase_counts[f"{token} {content_tokens[i + 1]}"] += 1
            if (
                i + 2 < len(content_tokens)
                and token is not None
                and content_tokens[i + 1] is not None
                and content_tokens[i + 2] is not None
            ):
                trigram_counts[f"{token} {content_tokens[i + 1]} {content_tokens[i + 2]}"] += 1

    # Trigram candidates (count >= 2)
    candidate_dict: dict[str, tuple[int, float]] = {
        tg: (count, float(count * 5))
        for tg, count in trigram_counts.items()
        if count >= 2
    }

    # Bigram candidates (count >= 2) with subsumption check against trigrams
    for bg, count in phrase_counts.items():
        if count >= 2:
            subsumed = False
            for tg, (tg_count, _) in list(candidate_dict.items()):
                tg_words = tg.split()
                if len(tg_words) == 3 and (bg == f"{tg_words[0]} {tg_words[1]}" or bg == f"{tg_words[1]} {tg_words[2]}"):
                    if abs(tg_count - count) <= 1:
                        subsumed = True
                        break
            if not subsumed:
                candidate_dict[bg] = (count, float(count * 3))

    # Unigram candidates with subsumption check against multi-word phrases
    for ug, count in word_counts.items():
        subsumed = False
        for p, (p_count, _) in list(candidate_dict.items()):
            if ug in p.split():
                if abs(p_count - count) <= 1:
                    subsumed = True
                    break
        if not subsumed:
            candidate_dict[ug] = (count, float(count))

    candidates: list[ConceptCandidate] = [
        ConceptCandidate(
            name=norm_name,
            normalized_name=norm_name,
            occurrence_count=count,
            score=score,
        )
        for norm_name, (count, score) in candidate_dict.items()
    ]

    if use_tfidf:
        blocks = extract_context_blocks(text)
        k_blocks = max(len(blocks), 1)

        scored_candidates: list[ConceptCandidate] = []
        for candidate in candidates:
            c_words = candidate.normalized_name.split()
            block_df = sum(
                1 for b in blocks if all(w in b.lower() for w in c_words)
            )
            block_idf = compute_idf(block_df, k_blocks)
            tf = compute_tf(candidate.occurrence_count)

            phrase_words = len(c_words)
            phrase_boost = 1.8 if phrase_words == 3 else (1.4 if phrase_words == 2 else 1.0)

            corpus_idf = 1.0
            if corpus_texts and len(corpus_texts) > 1:
                n_corpus = len(corpus_texts)
                corpus_df = sum(
                    1 for doc in corpus_texts if all(w in doc.lower() for w in c_words)
                )
                corpus_idf = math.log(1.0 + (n_corpus / (1.0 + corpus_df))) + 0.5

            tfidf = round(tf * block_idf * corpus_idf * phrase_boost, 3)
            scored_candidates.append(
                ConceptCandidate(
                    name=candidate.name,
                    normalized_name=candidate.normalized_name,
                    occurrence_count=candidate.occurrence_count,
                    score=candidate.score,
                    tfidf_score=tfidf,
                )
            )
        candidates = scored_candidates
        candidates.sort(
            key=lambda c: (-c.tfidf_score, -c.score, -c.occurrence_count, c.name)
        )
    else:
        # Default frequency-based ranking for baseline consistency
        candidates.sort(
            key=lambda candidate: (-candidate.score, -candidate.occurrence_count, candidate.name)
        )

    # Deduplicate: remove single-word concepts that are component words
    # of a higher-scoring multi-word phrase
    phrase_components: set[str] = set()
    deduped: list[ConceptCandidate] = []
    for candidate in candidates:
        if " " in candidate.normalized_name:
            phrase_components.update(candidate.normalized_name.split())
            deduped.append(candidate)
        else:
            if candidate.normalized_name not in phrase_components:
                deduped.append(candidate)

    return deduped[:limit]
