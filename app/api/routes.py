from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from google import genai

from app.core.database import get_db
from app.core.security import get_current_admin, SecurityService
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.document import DocumentIngestRequest, DocumentIngestResponse
from app.schemas.admin import TenantRegisterRequest, TenantRegisterResponse
from app.models.university import University, AdminUser
from app.models.document import DocumentChunk
from app.services.vector_store import VectorStoreService

router = APIRouter()
client = genai.Client(api_key=settings.GEMINI_API_KEY)

@router.post("/auth/register-tenant", response_model=TenantRegisterResponse, tags=["Authentication"])
async def register_new_tenant(request: TenantRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Provisions a new university tenant and securely hashes the primary admin credentials.
    """
    # Check if domain or username already exists
    uni_check = await db.execute(select(University).filter_by(domain=request.domain))
    if uni_check.scalars().first():
        raise HTTPException(status_code=400, detail="A university with this domain already exists.")

    admin_check = await db.execute(select(AdminUser).filter_by(username=request.admin_username))
    if admin_check.scalars().first():
        raise HTTPException(status_code=400, detail="Username is already taken.")

    # 1. Create the University Tenant
    new_uni = University(
        name=request.university_name,
        domain=request.domain,
        primary_color=request.primary_color,
        secondary_color=request.secondary_color
    )
    db.add(new_uni)
    await db.flush() # Secure the new_uni.id before committing

    # 2. Create the Admin User with safely hashed password
    hashed_pwd = SecurityService.hash_password(request.admin_password)
    new_admin = AdminUser(
        university_id=new_uni.id,
        username=request.admin_username,
        email=request.admin_email,
        hashed_password=hashed_pwd
    )
    db.add(new_admin)
    await db.commit()

    return TenantRegisterResponse(
        university_id=new_uni.id,
        admin_id=new_admin.id,
        message=f"Successfully provisioned institutional tenant for {request.university_name}."
    )

@router.post("/auth/login", tags=["Authentication"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Verifies user credentials against the database and issues a secure JWT token containing tenant constraints.
    """
    # Query database for the admin user
    result = await db.execute(select(AdminUser).filter_by(username=form_data.username))
    admin = result.scalars().first()
    
    # Secure verification step
    if not admin or not SecurityService.verify_password(form_data.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # The JWT token now embeds the specific university_id to guarantee data isolation
    access_token = SecurityService.create_access_token(
        data={"sub": admin.username, "role": "admin", "university_id": admin.university_id}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# ... Keep your existing /knowledge/ingest and /chat/ask routes operational below ...