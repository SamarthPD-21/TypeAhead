import csv
import statistics

def validate_dataset(filename="search_queries.csv"):
    queries = set()
    frequencies = []
    top_20 = []
    total_rows = 0
    duplicates = 0
    
    print(f"Validating {filename}...")
    
    try:
        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader)
            if header != ['query', 'frequency']:
                print("Warning: Unexpected header:", header)
                
            for row in reader:
                if len(row) != 2:
                    continue
                    
                query = row[0]
                freq = int(row[1])
                
                total_rows += 1
                
                if query in queries:
                    duplicates += 1
                else:
                    queries.add(query)
                    
                frequencies.append(freq)
                
                if total_rows <= 20:
                    top_20.append((query, freq))
                    
    except FileNotFoundError:
        print(f"Error: {filename} not found.")
        return

    print("-" * 40)
    print("Dataset Validation Report")
    print("-" * 40)
    print(f"Total Rows Processed: {total_rows:,}")
    print(f"Unique Queries:       {len(queries):,}")
    print(f"Duplicate Queries:    {duplicates:,}")
    
    if total_rows > 0:
        print("\nFrequency Statistics:")
        print(f"  Max Frequency: {max(frequencies):,}")
        print(f"  Min Frequency: {min(frequencies):,}")
        print(f"  Mean Frequency: {statistics.mean(frequencies):,.2f}")
        print(f"  Median Frequency: {statistics.median(frequencies):,}")
        
        print("\nTop 20 Queries:")
        for i, (q, f) in enumerate(top_20, 1):
            print(f"  {i:>2}. {q:<35} ({f:,})")
    
    if duplicates == 0 and len(queries) == 500_000:
        print("\n✅ Dataset successfully generated and validated!")
    else:
        print("\n❌ Validation failed. Uniqueness or row count mismatch.")

if __name__ == "__main__":
    validate_dataset()
