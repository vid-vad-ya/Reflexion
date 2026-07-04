import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import create_access_token, get_current_user, encrypt_token
from app.database import get_session
from app.models import User

router = APIRouter()


@router.get("/github/login")
def github_login():
    """Redirect the user to the GitHub OAuth authorize screen."""
    client_id = settings.GITHUB_CLIENT_ID
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub Client ID is not configured on the backend.",
        )
    # Redirect URI is configured to hit the backend callback endpoint
    redirect_uri = "http://localhost:8000/api/v1/auth/github/callback"
    scope = "read:user user:email"
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
    )
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback(code: str, session: Session = Depends(get_session)):
    """Handle the OAuth callback from GitHub, exchange code, upsert user, and redirect."""
    client_id = settings.GITHUB_CLIENT_ID
    client_secret = settings.GITHUB_CLIENT_SECRET
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth credentials are not configured on the backend.",
        )

    async with httpx.AsyncClient() as client:
        # 1. Exchange authorization code for access token
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
        )
        if token_res.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange OAuth code with GitHub.",
            )

        token_data = token_res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            error_desc = token_data.get("error_description", "No access token returned.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GitHub OAuth error: {error_desc}",
            )

        # 2. Retrieve user profile
        user_res = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        if user_res.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve user profile from GitHub.",
            )

        profile = user_res.json()
        github_id = profile.get("id")
        username = profile.get("login")
        avatar_url = profile.get("avatar_url")
        email = profile.get("email")

        # 3. Retrieve primary verified email if email is not public in profile
        if not email:
            email_res = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            if email_res.status_code == 200:
                emails = email_res.json()
                for e in emails:
                    if e.get("primary") and e.get("verified"):
                        email = e.get("email")
                        break
                # Fallback to the first email if primary verified email is not found
                if not email and emails:
                    email = emails[0].get("email")

        if not github_id or not username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub profile is missing required login or ID fields.",
            )

        # 4. Encrypt the access token
        encrypted_token = encrypt_token(access_token)

        # 5. Database Upsert
        statement = select(User).where(User.github_id == github_id)
        db_user = session.exec(statement).first()

        if db_user:
            # Update existing user profile attributes
            db_user.username = username
            db_user.email = email
            db_user.avatar_url = avatar_url
            db_user.github_username = username
            db_user.github_avatar_url = avatar_url
            db_user.github_access_token = encrypted_token
            session.add(db_user)
        else:
            # Create a brand new user
            db_user = User(
                github_id=github_id,
                username=username,
                email=email,
                avatar_url=avatar_url,
                github_username=username,
                github_avatar_url=avatar_url,
                github_access_token=encrypted_token,
            )
            session.add(db_user)

        session.commit()
        session.refresh(db_user)

        # 6. Generate local backend JWT session token
        jwt_token = create_access_token(subject=str(db_user.id))

        # 7. Redirect to the frontend callback handler with the JWT
        frontend_callback_url = f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}"
        return RedirectResponse(frontend_callback_url)


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile details."""
    return {
        "id": str(current_user.id),
        "github_id": current_user.github_id,
        "username": current_user.username,
        "email": current_user.email,
        "avatar_url": current_user.avatar_url,
        "github_username": current_user.github_username,
        "github_avatar_url": current_user.github_avatar_url,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
    }
