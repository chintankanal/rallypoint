#!/usr/bin/env python3
"""
Direct test of config loading in the router logic.
"""
import os
import sys

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:ocean202@localhost:5432/jlrs")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("INTERNAL_JOB_SECRET", "test-internal")

from app.database import init_pool, close_pool, get_connection
from app.config import settings

def test_config_loading_in_router():
    """Test that the config router reads from database."""
    print("=" * 70)
    print("TEST: Config router loads from database")
    print("=" * 70)
    
    try:
        init_pool(settings.database_url)
        
        # Simulate what the router does
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key, value, description FROM system_configuration ORDER BY key"
                )
                rows = [dict(r) for r in cur.fetchall()]
        
        print(f"\n✓ Retrieved {len(rows)} config entries from database")
        
        # Filter by some public keys that should be visible
        public_keys = {
            "k_base_provisional",
            "k_base_established",
            "w_league",
            "w_tournament",
            "w_friendly",
            "tier_beginner_max",
            "tier_intermediate_max",
            "tier_advanced_max",
            "tier_elite_max",
        }
        
        config_dict = {r['key']: r for r in rows}
        
        print(f"\nConfig values from database (sample):")
        found_count = 0
        for row in rows[:15]:  # Show first 15
            print(f"  {row['key']}: {row['value']}")
            print(f"    → {row['description']}")
            found_count += 1
        
        if found_count < len(rows):
            print(f"  ... and {len(rows) - found_count} more")
        
        # Verify critical values
        print(f"\nVerifying critical database values:")
        critical_checks = {
            'tier_beginner_max': '899',
            'tier_intermediate_max': '1099',
            'k_base_provisional': '50',
            'w_league': '1.0',
            'w_tournament': '1.2',
        }
        
        all_correct = True
        for key, expected_value in critical_checks.items():
            if key in config_dict:
                actual_value = config_dict[key]['value']
                status = "✓" if actual_value == expected_value else "✗"
                print(f"  {status} {key}: {actual_value} (expected {expected_value})")
                if actual_value != expected_value:
                    all_correct = False
            else:
                print(f"  ✗ {key}: NOT FOUND")
                all_correct = False
        
        return all_correct
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_pool()


def test_rating_functions_use_db_config():
    """Test that rating functions use database config, not hardcoded defaults."""
    print("\n" + "=" * 70)
    print("TEST: Rating functions use database config")
    print("=" * 70)
    
    try:
        init_pool(settings.database_url)
        
        from app.utils.rating_math import _load_config, get_tier
        
        # Load config from database
        cfg = _load_config()
        
        print(f"\n✓ Loaded {len(cfg)} config values from database")
        
        # Verify config values are from database (not defaults)
        db_tier_max = cfg.get('tier_beginner_max', 0)
        expected_db_value = 899.0
        
        if db_tier_max == expected_db_value:
            print(f"✓ tier_beginner_max from database: {db_tier_max}")
        else:
            print(f"✗ tier_beginner_max mismatch: got {db_tier_max}, expected {expected_db_value}")
            return False
        
        # Test that get_tier uses the database config
        test_rating = 900  # Should be INTERMEDIATE (>899)
        tier = get_tier(test_rating, cfg)
        
        if tier == "INTERMEDIATE":
            print(f"✓ Rating {test_rating} correctly classified as {tier} using database tier_beginner_max={db_tier_max}")
            return True
        else:
            print(f"✗ Rating {test_rating} incorrectly classified as {tier}, expected INTERMEDIATE")
            return False
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_pool()


def main():
    """Run all tests."""
    print("\n" + "📊 CONFIG DATABASE LOADING TEST".center(70, "="))
    
    try:
        results = {
            "Config Router Database Access": test_config_loading_in_router(),
            "Rating Functions Use DB Config": test_rating_functions_use_db_config(),
        }
        
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        for test_name, passed in results.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status}: {test_name}")
        
        all_passed = all(results.values())
        
        if all_passed:
            print("\n" + "✅ CONFIG SUCCESSFULLY LOADING FROM DATABASE!".center(70, "="))
            return 0
        else:
            print("\n" + "❌ SOME TESTS FAILED".center(70, "="))
            return 1
        
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
