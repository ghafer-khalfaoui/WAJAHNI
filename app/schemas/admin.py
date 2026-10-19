from pydantic import BaseModel, EmailStr

class TenantRegisterRequest(BaseModel):
    # University Details
    university_name: str
    domain: str  # e.g., "gju.edu.jo"
    primary_color: str = "#003366"
    secondary_color: str = "#e6f2ff"
    
    # Primary Admin Details
    admin_username: str
    admin_email: EmailStr
    admin_password: str

class TenantRegisterResponse(BaseModel):
    university_id: int
    admin_id: int
    status: str = "success"
    message: str