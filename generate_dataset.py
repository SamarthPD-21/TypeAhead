import csv
import random
import numpy as np

# Seed for reproducibility
random.seed(42)
np.random.seed(42)

CATEGORIES = {
    "Technology": ["laptop", "computer", "keyboard", "mouse", "monitor", "router", "gpu", "cpu", "motherboard", "ssd"],
    "Smartphones": ["iphone", "samsung galaxy", "google pixel", "oneplus", "xiaomi", "motorola", "iphone 15", "iphone 14", "iphone 13", "samsung s24", "samsung s23"],
    "Programming": ["python", "javascript", "java", "c++", "c#", "golang", "rust", "ruby", "php", "swift", "kotlin", "typescript", "html", "css", "react", "angular", "vue", "node js", "django", "flask", "spring boot", "pandas", "numpy"],
    "AI_ML": ["machine learning", "artificial intelligence", "deep learning", "neural networks", "chatgpt", "openai", "claude", "gemini", "llama", "stable diffusion", "midjourney", "nlp", "computer vision", "tensorflow", "pytorch", "scikit learn"],
    "Movies": ["the godfather", "the dark knight", "pulp fiction", "inception", "the matrix", "goodfellas", "interstellar", "parasite", "avengers", "star wars", "spider man", "batman", "oppenheimer", "barbie", "dune", "avatar"],
    "TV_Shows": ["breaking bad", "game of thrones", "the wire", "the sopranos", "stranger things", "the office", "friends", "seinfeld", "succession", "the bear", "true detective", "fargo", "better call saul"],
    "Music": ["taylor swift", "drake", "the weeknd", "bad bunny", "ed sheeran", "justin bieber", "ariana grande", "eminem", "post malone", "bts", "coldplay", "imagine dragons", "billie eilish", "dua lipa", "kanye west", "kendrick lamar", "beyonce", "rihanna"],
    "Sports": ["football", "basketball", "soccer", "baseball", "tennis", "golf", "cricket", "rugby", "hockey", "boxing", "ufc", "f1", "olympics", "world cup", "super bowl", "nba finals", "champions league", "premier league"],
    "Travel": ["flights", "hotels", "car rental", "vacation packages", "paris", "london", "new york", "tokyo", "rome", "bali", "hawaii", "maldives", "cancun", "dubai", "disney world", "cruises", "airbnb", "hostels"],
    "Food": ["pizza", "sushi", "burger", "pasta", "tacos", "steak", "vegan", "vegetarian", "gluten free", "keto", "recipes", "restaurant near me", "delivery", "takeout", "breakfast", "lunch", "dinner", "brunch", "dessert", "coffee"],
    "Shopping": ["amazon", "walmart", "target", "best buy", "costco", "home depot", "ikea", "zara", "h&m", "nike", "adidas", "apple store", "shoes", "clothes", "furniture", "makeup", "skincare", "jewelry", "watches"],
    "Education": ["online courses", "college", "university", "scholarships", "student loans", "coursera", "udemy", "edx", "harvard", "mit", "stanford", "oxford", "cambridge", "sat", "act", "gre", "gmat", "toefl", "ielts", "learn english", "learn spanish", "math", "science", "history", "geography"],
    "Health": ["weight loss", "diet", "nutrition", "exercise", "workout", "gym", "yoga", "pilates", "meditation", "mental health", "therapy", "anxiety", "depression", "sleep", "vitamins", "supplements", "skincare routine", "hair loss", "back pain", "headache", "covid", "flu", "allergies", "doctor near me", "dentist near me"],
    "Finance": ["stock market", "crypto", "bitcoin", "ethereum", "investing", "trading", "forex", "options", "mutual funds", "etf", "401k", "ira", "roth ira", "taxes", "credit card", "loans", "mortgage", "interest rates", "insurance", "life insurance", "car insurance", "home insurance", "health insurance", "bank", "savings account", "checking account", "personal finance", "budgeting", "debt"]
}

PREFIXES = [
    "best ", "cheap ", "top ", "new ", "latest ", "affordable ", "premium ", "popular ",
    "how to use ", "where to buy ", "how to learn ", "what is ", "who is ", "why ",
    "reviews of ", "deals on ", "guide to ", "tutorial for ", "introduction to ",
    "history of ", "future of ", "cost of ", "price of ", "alternatives to "
]

SUFFIXES = [
    " near me", " tutorial", " course", " reviews", " price", " cost",
    " for beginners", " for experts", " online", " free", " download",
    " app", " software", " tools", " tips", " tricks", " examples",
    " 2024", " 2023", " vs ", " reddit", " quora", " youtube",
    " alternatives", " guide", " book", " pdf", " images", " videos"
]

def generate_queries(target_count=500_000):
    queries = set()
    
    # 1. Base queries
    for cat, items in CATEGORIES.items():
        for item in items:
            queries.add(item)
            
    # 2. Base + 1 Suffix
    for cat, items in CATEGORIES.items():
        for item in items:
            for suffix in SUFFIXES:
                queries.add(item + suffix)
                
    # 3. 1 Prefix + Base
    for cat, items in CATEGORIES.items():
        for item in items:
            for prefix in PREFIXES:
                queries.add(prefix + item)
                
    # 4. Prefix + Base + Suffix
    for cat, items in CATEGORIES.items():
        for item in items:
            for prefix in PREFIXES:
                for suffix in SUFFIXES:
                    queries.add(prefix + item + suffix)
                    if len(queries) > target_count * 1.5:
                        break
                        
    # 5. Base + multiple suffixes (creating deeper prefix clusters)
    more_suffixes = [" part 1", " part 2", " download", " for mac", " for windows", " for linux"]
    for cat, items in CATEGORIES.items():
        for item in items:
            for s1 in SUFFIXES[:10]:
                for s2 in more_suffixes:
                    queries.add(item + s1 + s2)
                    
    # Generate some complex clusters (e.g. iphone 15 pro max case)
    iphone_models = ["iphone 13", "iphone 14", "iphone 15"]
    iphone_suffixes = ["", " pro", " pro max", " plus", " mini"]
    accessories = [" case", " charger", " cable", " screen protector", " battery", " camera", " colors", " price", " review"]
    for model in iphone_models:
        for suffix in iphone_suffixes:
            base = model + suffix
            queries.add(base)
            for acc in accessories:
                queries.add(base + acc)
                for ext in [" amazon", " best buy", " apple store", " near me"]:
                    queries.add(base + acc + ext)
                    
    python_topics = [" lists", " dictionaries", " loops", " functions", " classes", " decorators", " generators"]
    python_suffixes = [" tutorial", " examples", " exercises", " interview questions", " documentation"]
    for topic in python_topics:
        base = "python" + topic
        queries.add(base)
        for s in python_suffixes:
            queries.add(base + s)
            for ext in [" for beginners", " advanced", " pdf", " 2024"]:
                queries.add(base + s + ext)
                
    # Generate base + prefix1 + prefix2
    for cat, items in CATEGORIES.items():
        for item in items:
            for p1 in PREFIXES[:15]:
                for p2 in PREFIXES[15:]:
                    queries.add(p1 + p2 + item)
                    if len(queries) > target_count * 1.5: break

    # Generate more complex combinations
    for cat, items in CATEGORIES.items():
        for item in items:
            for p1 in PREFIXES[:10]:
                for s1 in SUFFIXES[:10]:
                    for s2 in SUFFIXES[10:20]:
                        queries.add(p1 + item + s1 + s2)
                        if len(queries) > target_count * 1.5: break

    queries_list = list(queries)
    random.shuffle(queries_list)
    return queries_list[:target_count]

def main():
    target_count = 500_000
    print(f"Generating {target_count} unique queries...")
    
    queries = generate_queries(target_count)
    
    # Ensure exactly target_count
    if len(queries) < target_count:
        print(f"Warning: Only generated {len(queries)} queries.")
    
    queries = queries[:target_count]
    
    print("Generating Zipf frequencies...")
    # Instead of np.random.zipf which is hard to control, we can explicitly generate 
    # frequencies based on Zipf's law: frequency proportional to 1 / rank^a
    a = 1.05
    max_freq = 1_000_000
    
    # Calculate frequencies directly from rank
    ranks = np.arange(1, target_count + 1)
    freqs = max_freq / (ranks ** a)
    freqs = np.maximum(freqs, 1).astype(int)
    
    # Sort frequencies descending
    freqs = sorted(freqs, reverse=True)
    
    # Sort queries so that shorter/simpler base queries tend to get higher frequencies,
    # but still keep some randomness.
    # We will score queries based on length (shorter = more popular) and whether they are pure base terms.
    base_terms = set(item for items in CATEGORIES.values() for item in items)
    
    def score_query(q):
        # Base terms get a huge boost
        score = 1000 if q in base_terms else 0
        # Shorter queries tend to be more frequent
        score -= len(q) 
        # Add random noise
        score += random.uniform(-10, 10)
        return score
        
    queries.sort(key=score_query, reverse=True)
    
    print("Writing to search_queries.csv...")
    with open('search_queries.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['query', 'frequency'])
        for i in range(len(queries)):
            writer.writerow([queries[i], int(freqs[i])])
            
    print("Done!")

if __name__ == "__main__":
    main()
