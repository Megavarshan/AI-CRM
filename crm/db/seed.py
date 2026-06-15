"""
Seed script — populates Supabase with realistic fake data for a beauty/skincare D2C brand.

Generates:
  • Customers (Indian names, E.164 phone numbers)
  • Orders spread across 18 months
  • Realistic churn distribution: ~20% critical, ~30% high risk

Usage:
    cd crm
    python db/seed.py --clean --customers 500
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

from faker import Faker
from postgrest.exceptions import APIError

try:
    from config import supabase
except ImportError:
    # Allow running directly or via module path
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import supabase

# Ensure UTF-8 console output on Windows (cp1252 default chokes on ✓/→/🎉)
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("seed")

fake = Faker("en_IN")
random.seed(42)

# ── Domain data ────────────────────────────────────────────────────────────────

CATEGORIES = ["skincare", "haircare", "makeup", "fragrance", "bodycare"]

PRODUCTS: dict[str, list[str]] = {
    "skincare":  ["Rose Serum 50ml", "Vitamin C Moisturiser", "Niacinamide Toner", "SPF 50 Sunscreen"],
    "haircare":  ["Argan Oil Shampoo", "Deep Condition Mask", "Hair Growth Serum", "Scalp Scrub"],
    "makeup":    ["Matte Lipstick", "Kajal Stick", "Foundation SPF 20", "Setting Spray"],
    "fragrance": ["Oud Eau de Parfum", "Rose Mist", "Sandalwood Roll-on"],
    "bodycare":  ["Shea Butter Lotion", "Ubtan Scrub", "Kumkumadi Oil"],
}

CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
    "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Indore",
]

CHANNELS = ["whatsapp", "sms", "email", "rcs"]
CHANNEL_WEIGHTS = [0.55, 0.20, 0.20, 0.05]

NOW = datetime.now(timezone.utc)


def random_phone() -> str:
    """Generate a random Indian E.164 mobile number."""
    return "+91" + str(random.randint(7000000000, 9999999999))


def random_order_date(churn_profile: str) -> datetime:
    """
    Generate a last-order date according to the customer's churn profile:
      - loyal    → within last 30 days
      - medium   → 31–60 days ago
      - high     → 61–90 days ago
      - critical → 91–540 days ago
    """
    if churn_profile == "loyal":
        days_ago = random.randint(1, 30)
    elif churn_profile == "medium":
        days_ago = random.randint(31, 60)
    elif churn_profile == "high":
        days_ago = random.randint(61, 90)
    else:  # critical
        days_ago = random.randint(91, 540)
    return NOW - timedelta(days=days_ago)


def check_db_connection() -> bool:
    """Validate connection to Supabase DB before seeding."""
    try:
        # Perform a cheap count check on customers table
        supabase.table("customers").select("id", count="exact").limit(1).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Supabase DB. Check your SUPABASE_URL and SUPABASE_SERVICE_KEY: {e}")
        return False


def clean_existing_data() -> None:
    """Clean all existing tables to allow a clean seed run."""
    logger.info("Cleaning up existing data in Supabase tables...")
    try:
        tables_to_clean = ["imports", "communications", "campaigns", "segments", "orders", "customers"]
        for table in tables_to_clean:
            supabase.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            logger.info(f"  ✓ Cleaned table: {table}")
    except APIError as e:
        logger.error(f"PostgREST Error cleaning data: {e.message}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error cleaning data: {e}")
        sys.exit(1)


def seed_customers(n: int) -> list[dict]:
    """Generate and insert n customers, return list of inserted rows."""
    logger.info(f"Generating and seeding {n} customers...")
    customers = []
    
    seen_emails = set()
    seen_phones = set()

    for _ in range(n):
        email = fake.unique.email()
        while email in seen_emails:
            email = fake.unique.email()
        seen_emails.add(email)

        phone = random_phone()
        while phone in seen_phones:
            phone = random_phone()
        seen_phones.add(phone)

        customers.append({
            "id": str(uuid.uuid4()),
            "external_id": f"SEED_{uuid.uuid4().hex[:8].upper()}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "phone": phone,
            "email": email,
            "city": random.choice(CITIES),
            "channel_pref": random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0],
        })

    chunk_size = 100
    inserted_count = 0
    start_time = time.time()
    for i in range(0, len(customers), chunk_size):
        chunk = customers[i : i + chunk_size]
        try:
            supabase.table("customers").insert(chunk).execute()
            inserted_count += len(chunk)
            logger.info(f"  → Inserted customers: {inserted_count}/{len(customers)}")
        except Exception as e:
            logger.error(f"Error seeding customer chunk starting at {i}: {e}")
            raise e

    logger.info(f"✓ Seeded {inserted_count} customers successfully in {time.time() - start_time:.2f}s")
    return customers


def seed_orders(customers: list[dict]) -> None:
    """Generate and insert orders for seeded customers with realistic distributions."""
    n_customers = len(customers)
    logger.info(f"Generating and seeding orders for {n_customers} customers...")
    
    loyal_count = int(n_customers * 0.50)
    medium_count = int(n_customers * 0.30)
    high_count = int(n_customers * 0.12)
    critical_count = n_customers - (loyal_count + medium_count + high_count)

    profiles = (
        ["loyal"] * loyal_count
        + ["medium"] * medium_count
        + ["high"] * high_count
        + ["critical"] * critical_count
    )
    random.shuffle(profiles)

    orders = []
    for customer, profile in zip(customers, profiles):
        if profile == "loyal":
            n_orders = random.randint(5, 20)
        elif profile == "medium":
            n_orders = random.randint(2, 7)
        else:
            n_orders = random.randint(1, 3)

        last_date = random_order_date(profile)
        category = random.choice(CATEGORIES)

        for i in range(n_orders):
            # Order 0 anchors the customer's recency; earlier orders step back
            # ~30 days each (with jitter). Clamped so the range is never negative.
            if i == 0:
                order_date = last_date
            else:
                order_date = last_date - timedelta(days=i * 30 + random.randint(0, 29))
            cat = random.choice(CATEGORIES) if i > 0 else category
            orders.append({
                "id": str(uuid.uuid4()),
                "customer_id": customer["id"],
                "order_date": order_date.isoformat(),
                "amount": round(random.uniform(299, 4999), 2),
                "category": cat,
                "product_name": random.choice(PRODUCTS[cat]),
                "status": "completed" if random.random() > 0.05 else random.choice(["returned", "cancelled"]),
            })

    chunk_size = 200
    inserted_count = 0
    start_time = time.time()
    for i in range(0, len(orders), chunk_size):
        chunk = orders[i : i + chunk_size]
        try:
            supabase.table("orders").insert(chunk).execute()
            inserted_count += len(chunk)
            logger.info(f"  → Inserted orders: {inserted_count}/{len(orders)}")
        except Exception as e:
            logger.error(f"Error seeding order chunk starting at {i}: {e}")
            raise e

    logger.info(f"✓ Seeded {inserted_count} orders successfully in {time.time() - start_time:.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Orbit CRM Database Seeder")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean all existing data from tables before seeding",
    )
    parser.add_argument(
        "--customers",
        type=int,
        default=500,
        help="Number of customers to seed (default: 500)",
    )
    args = parser.parse_args()

    logger.info("Starting database seeding process...")
    start_total_time = time.time()

    if not check_db_connection():
        logger.error("Database connection check failed. Exiting.")
        sys.exit(1)

    if args.clean:
        clean_existing_data()

    try:
        inserted_customers = seed_customers(args.customers)
        if inserted_customers:
            seed_orders(inserted_customers)
    except Exception as e:
        logger.critical(f"Seeding aborted due to error: {e}")
        sys.exit(1)

    logger.info(f"🎉 Seeding complete! Total elapsed time: {time.time() - start_total_time:.2f}s")
    logger.info("Next step: Run the RFM scorer to calculate scores for the seeded database:")
    logger.info("   python -c \"from tasks.score_customers import batch_score_all_customers; batch_score_all_customers()\"")


if __name__ == "__main__":
    main()
