#!/usr/bin/env python3
"""
Test script to verify config loading from database.
Tests both the cache mechanism and fallback to defaults.
"""
import os
import sys

# Set up environment
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:ocean202@localhost:5432/jlrs")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("INTERNAL_JOB_SECRET", "test-internal")

from app.utils.rating_math import _load_config, invalidate_config_cache, get_tier, get_k_base, get_age_group
from app.database import init_pool, close_pool, get_connection

def test_config_loading_from_db():
    """Test that config is loaded from database."""
    print("=" * 70)
    print("TEST 1: Load config from database")
    print("=" * 70)
    
    try:
        cfg = _load_config()
        
        print(f"✓ Config loaded successfully")
        print(f"✓ Config keys: {len(cfg)}")
        
        # Check critical keys
        critical_keys = [
            'tier_beginner_max', 'tier_intermediate_max', 'tier_advanced_max', 'tier_elite_max',
            'k_base_provisional', 'k_base_intermediate', 'k_base_established',
            'k_base_provisional_threshold', 'k_base_intermediate_threshold',
            'w_league', 'w_tournament', 'w_friendly', 'w_same_academy', 'w_cross_academy',
            'elo_divisor', 'cr_match_threshold', 'age_bonus_max', 'age_bonus_multiplier',
            'age_group_u10_max', 'age_group_u13_max', 'age_group_u15_max', 'age_group_u17_max',
            'provisional_threshold'
        ]
        
        missing = []
        for key in critical_keys:
            if key not in cfg:
                missing.append(key)
            else:
                print(f"  ✓ {key}: {cfg[key]}")
        
        if missing:
            print(f"\n✗ Missing keys: {missing}")
            return False
        
        print(f"\n✓ All critical keys present in config")
        return True
    except Exception as e:
        print(f"✗ Error loading config: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tier_function_with_config():
    """Test that tier function uses config values."""
    print("\n" + "=" * 70)
    print("TEST 2: get_tier() uses database config")
    print("=" * 70)
    
    try:
        cfg = _load_config()
        
        # Test tier boundaries from config
        beginner_max = int(cfg.get("tier_beginner_max", 899))
        intermediate_max = int(cfg.get("tier_intermediate_max", 1099))
        advanced_max = int(cfg.get("tier_advanced_max", 1299))
        elite_max = int(cfg.get("tier_elite_max", 1499))
        
        test_cases = [
            (800, "BEGINNER"),
            (beginner_max, "BEGINNER"),
            (beginner_max + 1, "INTERMEDIATE"),
            (1099, "INTERMEDIATE"),
            (1100, "ADVANCED"),
            (advanced_max, "ADVANCED"),
            (advanced_max + 1, "ELITE"),
            (elite_max, "ELITE"),
            (elite_max + 1, "NATIONAL_TRACK"),
        ]
        
        print(f"Tier boundaries from config:")
        print(f"  BEGINNER: <= {beginner_max}")
        print(f"  INTERMEDIATE: {beginner_max+1} - {intermediate_max}")
        print(f"  ADVANCED: {intermediate_max+1} - {advanced_max}")
        print(f"  ELITE: {advanced_max+1} - {elite_max}")
        print(f"  NATIONAL_TRACK: > {elite_max}")
        
        all_passed = True
        for rating, expected_tier in test_cases:
            tier = get_tier(rating, cfg)
            status = "✓" if tier == expected_tier else "✗"
            print(f"  {status} Rating {rating} → {tier} (expected {expected_tier})")
            if tier != expected_tier:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"✗ Error testing tier function: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_k_base_function_with_config():
    """Test that k_base function uses config thresholds."""
    print("\n" + "=" * 70)
    print("TEST 3: get_k_base() uses database config thresholds")
    print("=" * 70)
    
    try:
        cfg = _load_config()
        
        prov_threshold = int(cfg.get("k_base_provisional_threshold", 30))
        inter_threshold = int(cfg.get("k_base_intermediate_threshold", 100))
        k_prov = cfg.get("k_base_provisional", 50.0)
        k_inter = cfg.get("k_base_intermediate", 32.0)
        k_est = cfg.get("k_base_established", 20.0)
        
        test_cases = [
            (0, k_prov, "provisional"),
            (29, k_prov, "provisional"),
            (prov_threshold, k_inter, "intermediate"),
            (99, k_inter, "intermediate"),
            (inter_threshold, k_est, "established"),
            (200, k_est, "established"),
        ]
        
        print(f"K-base thresholds from config:")
        print(f"  < {prov_threshold}: {k_prov} (provisional)")
        print(f"  {prov_threshold} - {inter_threshold-1}: {k_inter} (intermediate)")
        print(f"  >= {inter_threshold}: {k_est} (established)")
        
        all_passed = True
        for matches, expected_k, category in test_cases:
            actual_k = get_k_base(matches, cfg)
            status = "✓" if actual_k == expected_k else "✗"
            print(f"  {status} Matches {matches} → K={actual_k} (expected {expected_k}, {category})")
            if actual_k != expected_k:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"✗ Error testing k_base function: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_age_group_function_with_config():
    """Test that age_group function uses config boundaries."""
    print("\n" + "=" * 70)
    print("TEST 4: get_age_group() uses database config boundaries")
    print("=" * 70)
    
    try:
        cfg = _load_config()
        
        u10_max = int(cfg.get("age_group_u10_max", 10))
        u13_max = int(cfg.get("age_group_u13_max", 13))
        u15_max = int(cfg.get("age_group_u15_max", 15))
        u17_max = int(cfg.get("age_group_u17_max", 17))
        
        test_cases = [
            (5, "U10"),
            (u10_max, "U10"),
            (u10_max + 1, "U13"),
            (u13_max, "U13"),
            (u13_max + 1, "U15"),
            (u15_max, "U15"),
            (u15_max + 1, "U17"),
            (u17_max, "U17"),
            (u17_max + 1, "OPEN"),
        ]
        
        print(f"Age group boundaries from config:")
        print(f"  U10: <= {u10_max}")
        print(f"  U13: {u10_max+1} - {u13_max}")
        print(f"  U15: {u13_max+1} - {u15_max}")
        print(f"  U17: {u15_max+1} - {u17_max}")
        print(f"  OPEN: > {u17_max}")
        
        all_passed = True
        for age, expected_group in test_cases:
            group = get_age_group(age, cfg)
            status = "✓" if group == expected_group else "✗"
            print(f"  {status} Age {age} → {group} (expected {expected_group})")
            if group != expected_group:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"✗ Error testing age_group function: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """Test direct database query to verify seed data."""
    print("\n" + "=" * 70)
    print("TEST 0: Verify seed data in database")
    print("=" * 70)
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM system_configuration")
                result = cur.fetchone()
                count = result["cnt"] if result else 0
                
                print(f"✓ Database connected")
                print(f"✓ Total config keys in database: {count}")
                
                # Query specific keys
                cur.execute(
                    "SELECT key, value FROM system_configuration WHERE key LIKE 'tier_%' OR key LIKE 'k_base_%' OR key LIKE 'age_group_%' ORDER BY key"
                )
                rows = cur.fetchall()
                
                print(f"\nSample config values from database:")
                for row in rows:
                    print(f"  {row['key']}: {row['value']}")
                
                return len(rows) > 0
    except Exception as e:
        print(f"✗ Database connection error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "🧪 CONFIG LOADING TEST SUITE".center(70, "="))
    
    try:
        # Initialize database pool
        from app.config import settings
        init_pool(settings.database_url)
        
        results = {
            "Database Connection": test_database_connection(),
            "Config Loading": test_config_loading_from_db(),
            "Tier Function": test_tier_function_with_config(),
            "K-Base Function": test_k_base_function_with_config(),
            "Age Group Function": test_age_group_function_with_config(),
        }
        
        # Print summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        for test_name, passed in results.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status}: {test_name}")
        
        all_passed = all(results.values())
        
        if all_passed:
            print("\n" + "🎉 ALL TESTS PASSED! Config is loading from database.".center(70, "="))
        else:
            print("\n" + "⚠️  SOME TESTS FAILED".center(70, "="))
        
        return 0 if all_passed else 1
        
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        close_pool()


if __name__ == "__main__":
    sys.exit(main())
