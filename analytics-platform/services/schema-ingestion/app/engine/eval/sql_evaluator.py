import re

class SQLEvaluator:
    @staticmethod
    def evaluate(expected: str, generated: str) -> float:
        """
        Compare Expected SQL vs Generated SQL.
        Instead of exact match, compare clauses.
        """
        if not expected or not generated:
            return 0.0
            
        def extract_clauses(sql: str):
            sql = sql.upper().replace("\n", " ")
            sql = re.sub(r'\s+', ' ', sql)
            
            # Very basic tokenization for comparison
            tokens = {"SELECT": False, "WHERE": False, "GROUP BY": False, "ORDER BY": False, "LIMIT": False}
            for t in tokens:
                if t in sql:
                    tokens[t] = True
            
            # Table names and column names are harder without a parser, 
            # so we'll just tokenize the words and check Jaccard similarity of words.
            words = set(re.findall(r'\b\w+\b', sql))
            return tokens, words
            
        exp_tokens, exp_words = extract_clauses(expected)
        gen_tokens, gen_words = extract_clauses(generated)
        
        score = 0.0
        max_score = 2.0
        
        # 1. Clause structure
        if exp_tokens == gen_tokens:
            score += 1.0
            
        # 2. Word similarity (Jaccard)
        if exp_words and gen_words:
            intersect = exp_words.intersection(gen_words)
            union = exp_words.union(gen_words)
            score += len(intersect) / len(union)
        elif not exp_words and not gen_words:
            score += 1.0
            
        return score / max_score
