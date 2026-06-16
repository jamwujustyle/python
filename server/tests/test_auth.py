import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.user.models import User, UserRole
from app.core.security import get_password_hash
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    """Test user registration."""
    payload = {
        "email": "user@example.com",
        "password": "securepassword123",
        "first_name": "John",
        "last_name": "Doe",
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["email"] == "user@example.com"
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["role"] == "user"
    assert data["is_verified"] is False
    assert "id" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    """Test registration with an email that already exists."""
    payload = {
        "email": "duplicate@example.com",
        "password": "securepassword123",
    }
    # First signup
    res1 = await client.post("/auth/signup", json=payload)
    assert res1.status_code == 201
    
    # Second signup
    res2 = await client.post("/auth/signup", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_verification_flow(client: AsyncClient):
    """Test user account verification flow using generated verification code."""
    # 1. Sign up user
    payload = {
        "email": "verify@example.com",
        "password": "securepassword123",
    }
    signup_res = await client.post("/auth/signup", json=payload)
    assert signup_res.status_code == 201
    
    # 2. Retrieve the verification code from DB
    async with TestingSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == "verify@example.com")
        )
        user = result.scalar_one()
        code = user.verification_code
        assert code is not None
        
    # 3. Verify the user
    verify_payload = {
        "email": "verify@example.com",
        "code": code,
    }
    verify_res = await client.post("/auth/verify", json=verify_payload)
    assert verify_res.status_code == 200
    assert verify_res.json()["is_verified"] is True


@pytest.mark.asyncio
async def test_login_and_refresh(client: AsyncClient):
    """Test user login and token refresh flows."""
    # 1. Register & verify user
    payload = {
        "email": "auth@example.com",
        "password": "securepassword123",
    }
    await client.post("/auth/signup", json=payload)
    
    async with TestingSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == "auth@example.com")
        )
        user = result.scalar_one()
        user.is_verified = True
        await db.commit()
        
    # 2. Login
    login_payload = {
        "email": "auth@example.com",
        "password": "securepassword123",
    }
    login_res = await client.post("/auth/login", json=login_payload)
    assert login_res.status_code == 200
    
    tokens = login_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    
    # 3. Refresh Access Token
    refresh_payload = {
        "refresh_token": tokens["refresh_token"],
    }
    refresh_res = await client.post("/auth/refresh", json=refresh_payload)
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()


@pytest.mark.asyncio
async def test_role_permissions(client: AsyncClient):
    """Test endpoint access controls based on user role."""
    # 1. Setup a standard user and an admin user in DB
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        
        reg_user = User(
            email="regular@example.com",
            hashed_password=user_pw,
            role=UserRole.USER,
            is_verified=True,
        )
        admin_user = User(
            email="admin_user@example.com",
            hashed_password=user_pw,
            role=UserRole.ADMIN,
            is_verified=True,
        )
        db.add_all([reg_user, admin_user])
        await db.commit()
        await db.refresh(reg_user)
        await db.refresh(admin_user)
        
        reg_id = reg_user.id
        admin_id = admin_user.id
        
    # 2. Get tokens for regular user
    reg_login = await client.post(
        "/auth/login",
        json={"email": "regular@example.com", "password": "password123"},
    )
    reg_token = reg_login.json()["access_token"]
    reg_headers = {"Authorization": f"Bearer {reg_token}"}
    
    # 3. Get tokens for admin user
    admin_login = await client.post(
        "/auth/login",
        json={"email": "admin_user@example.com", "password": "password123"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 4. Standard user accesses GET /me (Success)
    me_res = await client.get("/me", headers=reg_headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "regular@example.com"
    
    # 5. Standard user accesses GET /users (403 Forbidden)
    users_res = await client.get("/users", headers=reg_headers)
    assert users_res.status_code == 403
    
    # 6. Admin user accesses GET /users (200 OK)
    users_admin_res = await client.get("/users", headers=admin_headers)
    assert users_admin_res.status_code == 200
    assert len(users_admin_res.json()) >= 2
    
    # 7. Standard user updates their own profile (200 OK)
    patch_res = await client.patch(
        f"/users/{reg_id}",
        json={"first_name": "NewName"},
        headers=reg_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["first_name"] == "NewName"
    
    # 8. Standard user tries to update another user (403 Forbidden)
    patch_other = await client.patch(
        f"/users/{admin_id}",
        json={"first_name": "Hack"},
        headers=reg_headers,
    )
    assert patch_other.status_code == 403


@pytest.mark.asyncio
async def test_unverified_users_cleanup():
    """Test automatic cleanup of unverified users created > 2 days ago."""
    from datetime import datetime, timezone, timedelta
    from app.tasks import async_cleanup_unverified_users
    
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        
        # 1. Unverified user created 3 days ago (Should be deleted)
        old_unverified = User(
            email="old_unverified@example.com",
            hashed_password=user_pw,
            role=UserRole.USER,
            is_verified=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        
        # 2. Unverified user created recently (Should NOT be deleted)
        recent_unverified = User(
            email="recent_unverified@example.com",
            hashed_password=user_pw,
            role=UserRole.USER,
            is_verified=False,
            created_at=datetime.now(timezone.utc),
        )
        
        # 3. Verified user created 3 days ago (Should NOT be deleted)
        old_verified = User(
            email="old_verified@example.com",
            hashed_password=user_pw,
            role=UserRole.USER,
            is_verified=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        
        db.add_all([old_unverified, recent_unverified, old_verified])
        await db.commit()

    # Run the cleanup logic passing our testing db session
    async with TestingSessionLocal() as db:
        deleted_count = await async_cleanup_unverified_users(db)
        assert deleted_count == 1

    # Verify database state
    async with TestingSessionLocal() as db:
        # Check old_unverified is deleted
        result = await db.execute(select(User).where(User.email == "old_unverified@example.com"))
        assert result.scalar_one_or_none() is None
        
        # Check recent_unverified exists
        result = await db.execute(select(User).where(User.email == "recent_unverified@example.com"))
        assert result.scalar_one_or_none() is not None
        
        # Check old_verified exists
        result = await db.execute(select(User).where(User.email == "old_verified@example.com"))
        assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_promote_and_demote_endpoints(client: AsyncClient):
    """Test promotion to Admin and demotion to User endpoints."""
    # 1. Setup a standard user and an admin user in DB
    async with TestingSessionLocal() as db:
        user_pw = get_password_hash("password123")
        
        target_user = User(
            email="target@example.com",
            hashed_password=user_pw,
            role=UserRole.USER,
            is_verified=True,
        )
        admin_user = User(
            email="admin_promoter@example.com",
            hashed_password=user_pw,
            role=UserRole.ADMIN,
            is_verified=True,
        )
        db.add_all([target_user, admin_user])
        await db.commit()
        await db.refresh(target_user)
        await db.refresh(admin_user)
        
        target_id = target_user.id
        
    # 2. Get tokens for target user (standard)
    target_login = await client.post(
        "/auth/login",
        json={"email": "target@example.com", "password": "password123"},
    )
    target_token = target_login.json()["access_token"]
    target_headers = {"Authorization": f"Bearer {target_token}"}
    
    # 3. Get tokens for admin user
    admin_login = await client.post(
        "/auth/login",
        json={"email": "admin_promoter@example.com", "password": "password123"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 4. Standard user promotes themselves (200 OK)
    promote_success = await client.post(
        f"/users/{target_id}/promote",
        headers=target_headers,
    )
    assert promote_success.status_code == 200
    assert promote_success.json()["message"] == "promoted"
    
    # 5. Standard user demotes themselves back to user (200 OK)
    demote_success = await client.post(
        f"/users/{target_id}/demote",
        headers=target_headers,
    )
    assert demote_success.status_code == 200
    assert demote_success.json()["message"] == "demoted"
