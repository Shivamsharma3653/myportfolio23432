from backend.flood_analysis import analyze_flood

result = analyze_flood(
    before_start="2024-06-15",
    before_end="2024-07-15",
    after_start="2024-07-15",
    after_end="2024-08-15"
)

print(result)