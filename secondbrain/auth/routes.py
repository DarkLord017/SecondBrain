from fastapi import APIRouter, HTTPException

from secondbrain.auth import service
from secondbrain.auth.schemas import LoginRequest, SignupRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=201)
async def signup(req: SignupRequest):
    try:
        return await service.signup(req.email, req.password)
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/login", response_model=UserOut)
async def login(req: LoginRequest):
    try:
        return await service.login(req.email, req.password)
    except PermissionError:
        raise HTTPException(401, "invalid credentials")
    except service.ProfileSyncError:
        raise HTTPException(503, "server error, please try again later")
