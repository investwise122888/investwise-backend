"""
One‑time script to seed fundamentals from CSV into Firestore.
Run after deploying Phase B code and ensuring CSV is in backend folder.
"""

import csv
import os
from app.database import db
from pathlib import Path

CSV_PATH = Path(__file__).parent / "fundamentals.csv"

def seed_fundamentals():
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found.")
        return
    
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row['symbol'].strip().upper()
            # Compute fundamentals pass
            pe = float(row['pe_ratio'])
            eps_years = [float(row['eps_y1']), float(row['eps_y2']), float(row['eps_y3'])]
            eps_positive_count = sum(1 for e in eps_years if e > 0)
            debt_eq = float(row['debt_to_equity'])
            sector_avg_pe = float(row['sector_avg_pe'])
            
            pe_pass = pe < sector_avg_pe * 1.3
            eps_pass = eps_positive_count >= 2
            debt_pass = debt_eq < 1.5
            fundamentals_pass = pe_pass and eps_pass and debt_pass
            
            doc_data = {
                "symbol": symbol,
                "pe_ratio": pe,
                "eps_y1": eps_years[0],
                "eps_y2": eps_years[1],
                "eps_y3": eps_years[2],
                "eps_positive_years": eps_positive_count,
                "debt_to_equity": debt_eq,
                "dividend_yield": float(row['dividend_yield']),
                "sector": row['sector'],
                "sector_avg_pe": sector_avg_pe,
                "fundamentals_pass": fundamentals_pass,
                "pe_pass": pe_pass,
                "eps_pass": eps_pass,
                "debt_pass": debt_pass
            }
            db.collection("fundamentals").document(symbol).set(doc_data)
            print(f"Seeded {symbol}: fundamentals_pass={fundamentals_pass}")
    print("Fundamentals seeding complete.")

if __name__ == "__main__":
    seed_fundamentals()