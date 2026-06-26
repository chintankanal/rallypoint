#!/usr/bin/env python3
"""
Test the /api/v1/config endpoint to verify it returns database values.
"""
import os
import sys

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:ocean202@localhost:5432/jlrs")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("INTERNAL_JOB_SECRET", "test-internal")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

import asyncio
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_pool, close_pool, get_connection
from app.config import settings
from jose import jwt

async def test_config_endpoint():
    """Test that /api/v1/config returns values from database."""
    print("=" * 70)
    print("TEST: /api/v1/config endpoint returns database values")
    print("=" * 70)
    
    try:
        init_pool(settings.database_url)
        
        # Get or create a test admin user and JWT token
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get or create admin user
                cur.execute("SELECT user_id, name FROM users WHERE role = 'ADMIN' LIMIT 1")
                user = cur.fetchone()
                
                if not user:
                    print("Creating test admin user...")
                    import uuid
                    user_id = str(uuid.uuid4())
                    cur.execute(
                        """INSERT INTO users (user_id, name, phone, email, password_hash, role, status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (user_id, "Test Admin", "+919999999999", "admin@test.com", "hashed", "ADMIN", "ACTIVE")
                    )
                    user = {"user_id": user_id, "name": "Test Admin"}
        
        # Create JWT token
        user_id = user["user_id"]
        payload = {
            "sub": user_id,
            "role": "ADMIN",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
        
        client = TestClient(app)
        
        # Test with authentication
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/config", headers=headers)
        
        print(f"\nResponse status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"✗ Failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        data = response.json()
        items = data.get("items", [])
        
        print(f"✓ Got {len(items)} config items from API")
        
        # Check for critical keys
        critical_keys = {
            'tier_beginner_max': '899',
            'tier_intermediate_max': '1099',
            'tier_advanced_max': '1299',
            'tier_elite_max': '1499',
            'k_base_provisional': '50',
            'k_base_intermediate': '32',
            'k_base_established': '20',
            'k_max': '60',
            'w_league': '1.0',
            'w_tournament': '1.2',
            'w_friendly': '0.5',
            'w_same_academy': '0.8',
            'w_cross_academy': '1.2',
            'elo_divisor': '400',
            'cr_match_threshold': '30',
            'age_bonus_max': '10',
            'age_bonus_multiplier': '2',
        }
        
        config_dict = {item['key']: item['value'] for item in items}
        
        all_found = True
        print(f"\nDatabase values from /api/v1/config:")
        for key, expected_value in critical_keys.items():
            if key in config_dict:
                actual_value = config_dict[key]
                status = "✓" if actual_value == expected_value else "✗"
                print(f"  {status} {key}: {actual_value} (expected {expected_value})")
                if actual_value != expected_value:
                    all_found = False
            else:
                print(f"  ✗ {key}: NOT FOUND")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_pool()

def main():
    """Run the test."""
    try:
        result = asyncio.run(test_config_endpoint())
        
        if result:
            print("\n" + "✓ Config endpoint test PASSED".center(70, "="))
            return 0
        else:
            print("\n" + "✗ Config endpoint test FAILED".center(70, "="))
            return 1
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
