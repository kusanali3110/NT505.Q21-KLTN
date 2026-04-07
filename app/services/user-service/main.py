import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine, func, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "user-service"
    database_url: str = Field(validation_alias="DATABASE_URL")
    jwt_secret: str = Field(validation_alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_minutes: int = Field(default=60, validation_alias="ACCESS_TOKEN_MINUTES")
    smtp_host: str = Field(default="127.0.0.1", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, validation_alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, validation_alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    admin_default_email: str | None = Field(default=None, validation_alias="ADMIN_DEFAULT_EMAIL")
    admin_default_password: str | None = Field(default=None, validation_alias="ADMIN_DEFAULT_PASSWORD")
    frontend_url: str = Field(default="http://localhost:3000", validation_alias="FRONTEND_URL")


settings = Settings()
app = FastAPI(title="user-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=True)  # optional display name
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    is_verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RegisterBody(BaseModel):
    email: str          # Accept any string — allows local domains like admin@local
    password: str
    role: str = "user"
    username: str | None = None


class LoginBody(BaseModel):
    email: str
    password: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(data: Dict[str, Any], secret: str, algorithm: str, minutes: int) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload.update({"exp": expire})
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, secret: str, algorithm: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

def send_verification_email(to_email: str, verify_link: str) -> None:
    if not settings.smtp_host or settings.smtp_host == "127.0.0.1" and not settings.smtp_port:
        logger.info("SMTP host not fully configured, skipping actual email send.")
        return

    msg = MIMEMultipart()
    msg['From'] = settings.smtp_user or "noreply@NT505.Q21-KLTN"
    msg['To'] = to_email
    msg['Subject'] = "Verify your NT505.Q21-KLTN account"

    body = f"""
    <p>Hello,</p>
    <p>Please click the link below to verify your email address. It will expire in 10 minutes.</p>
    <p><a href="{verify_link}">{verify_link}</a></p>
    """
    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        server.ehlo()
        if settings.smtp_user and settings.smtp_password:
            try:
                server.starttls()
            except Exception:
                pass
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(msg['From'], to_email, msg.as_string())
        server.quit()
        logger.info(f"Sent verification email to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> dict:
    try:
        return decode_token(credentials.credentials, settings.jwt_secret, settings.jwt_algorithm)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


@app.on_event("startup")
def startup() -> None:
    # Retry logic for database connection
    max_retries = 10
    retry_interval = 3
    for i in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database connected and tables created.")
            break
        except Exception as e:
            if i < max_retries - 1:
                logger.error(f"Database connection failed (attempt {i+1}/{max_retries}): {e}. Retrying in {retry_interval}s...")
                time.sleep(retry_interval)
            else:
                logger.error(f"Max retries reached. Could not connect to database: {e}")
                raise

    if settings.admin_default_email and settings.admin_default_password:
        db = SessionLocal()
        try:
            admin_user = db.execute(select(User).where(User.email == settings.admin_default_email)).scalar_one_or_none()
            if not admin_user:
                logger.info(f"Bootstrapping admin user {settings.admin_default_email}...")
                user = User(
                    email=settings.admin_default_email,
                    username="Admin",
                    password_hash=hash_password(settings.admin_default_password),
                    role="admin",
                    is_verified=True,
                )
                db.add(user)
                db.commit()
        finally:
            db.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.post("/auth/register")
def register(body: RegisterBody, db: Session = Depends(get_db)) -> dict:
    existing = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if existing:
        if existing.is_verified:
            raise HTTPException(status_code=400, detail="Email already exists")
        else:
            existing.password_hash = hash_password(body.password)
            existing.username = body.username or body.email.split("@")[0]
            existing.role = body.role
            user = existing
    else:
        user = User(
            email=body.email,
            username=body.username or body.email.split("@")[0],
            password_hash=hash_password(body.password),
            role=body.role,
            is_verified=False,
        )
        db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"email": user.email, "type": "verify"}, settings.jwt_secret, settings.jwt_algorithm, 10)
    verify_link = f"{settings.frontend_url}/verify-email?token={token}"
    # logger.info(f"\n---- EMAIL VERIFICATION MOCK ----\nTo: {user.email}\nSubject: Verify your email\nLink: {verify_link}\n---------------------------------\n")

    # Send real email
    send_verification_email(user.email, verify_link)

    return {"id": user.id, "email": user.email, "username": user.username, "role": user.role, "message": "Verification email sent"}

@app.get("/auth/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)) -> dict:
    try:
        payload = decode_token(token, settings.jwt_secret, settings.jwt_algorithm)
        if payload.get("type") != "verify":
            raise HTTPException(status_code=400, detail="Invalid token type")
        email = payload.get("email")
    except ValueError:
        raise HTTPException(status_code=400, detail="Token expired or invalid. Please register again.")
        
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_verified = True
    db.commit()
    return {"status": "success", "message": "Email verified"}


@app.post("/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)) -> dict:
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if not user:
        # Try matching by username too
        user = db.execute(select(User).where(User.username == body.email)).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified")
    token = create_access_token(
        {"sub": str(user.id), "email": user.email, "username": user.username, "role": user.role},
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.access_token_minutes,
    )
    return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/login/form", include_in_schema=False)
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> dict:
    """OAuth2 form-compatible login (username field = email or username)."""
    body = LoginBody(email=form.username, password=form.password)
    return login(body, db)


@app.get("/me")
def me(current_user: Annotated[dict, Depends(get_current_user)], db: Session = Depends(get_db)) -> dict:
    user = db.get(User, int(current_user["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }

class UpdateRoleBody(BaseModel):
    role: str

@app.get("/")
def list_users(current_user: Annotated[dict, Depends(get_current_user)], db: Session = Depends(get_db)) -> list[dict]:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    rows = db.execute(select(User).order_by(User.id)).scalars().all()
    return [{
        "id": u.id, "email": u.email, "username": u.username, "role": u.role,
        "is_verified": u.is_verified, "created_at": u.created_at.isoformat() if u.created_at else None
    } for u in rows]

@app.patch("/{user_id}/role")
def update_role(user_id: int, body: UpdateRoleBody, current_user: Annotated[dict, Depends(get_current_user)], db: Session = Depends(get_db)) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = body.role
    db.commit()
    return {"id": user.id, "role": user.role}
